import json
from typing import Any, TypedDict

from app.core.settings import Settings
from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt
from app.services.opportunity_store import OpportunityRecord
from app.services.prompt_config_store import (
    FLOW_TASK_VACANCY_PROFILE_EXTRACT,
    build_prompt_text,
)


class SalaryRange(TypedDict):
    min: float | None
    max: float | None
    currency: str
    period: str
    text_original: str


class WorkConditions(TypedDict):
    modality: str
    schedule: str
    contract_type: str
    location: str
    salary: SalaryRange


class OpportunityProfile(TypedDict):
    summary: str
    seniority: str
    organizational_level: str
    funciones_responsabilidades: list[str]
    requisitos_obligatorios: list[str]
    requisitos_deseables: list[str]
    condiciones_trabajo: WorkConditions
    beneficios: list[str]
    confidence: str
    extraction_source: str


def _extract_json_object(raw_text: str) -> dict[str, object] | None:
    text = raw_text.strip()
    if not text:
        return None
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _clean_text(value: Any, *, max_chars: int = 300) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    compact = " ".join(text.split())
    return compact[:max_chars].rstrip()


def _clean_list(
    raw: Any,
    *,
    max_items: int | None = 12,
    max_chars: int = 180,
) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for value in raw:
        text = _clean_text(value, max_chars=max_chars)
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(text)
        if max_items and max_items > 0 and len(items) >= max_items:
            break
    return items


def _to_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    filtered = "".join(ch for ch in text if ch.isdigit() or ch in ",.-")
    if not filtered:
        return None
    if "." in filtered and "," in filtered:
        if filtered.rfind(",") > filtered.rfind("."):
            filtered = filtered.replace(".", "").replace(",", ".")
        else:
            filtered = filtered.replace(",", "")
    else:
        filtered = filtered.replace(",", ".")
    try:
        return float(filtered)
    except ValueError:
        return None


def _empty_salary() -> SalaryRange:
    return {
        "min": None,
        "max": None,
        "currency": "no_especificado",
        "period": "no_especificado",
        "text_original": "",
    }


def _normalize_salary(raw: Any) -> SalaryRange:
    salary = _empty_salary()
    if isinstance(raw, dict):
        source = raw
        salary["min"] = _to_number(source.get("min"))
        salary["max"] = _to_number(source.get("max"))
        currency = _clean_text(source.get("currency"), max_chars=20).upper()
        period = _clean_text(source.get("period"), max_chars=20).lower()
        salary["currency"] = currency if currency else "no_especificado"
        salary["period"] = period if period else "no_especificado"
        salary["text_original"] = _clean_text(source.get("text_original"), max_chars=220)
        return salary

    text_original = _clean_text(raw, max_chars=220)
    if text_original:
        salary["text_original"] = text_original
    return salary


def _empty_work_conditions() -> WorkConditions:
    return {
        "modality": "no_especificado",
        "schedule": "no_especificado",
        "contract_type": "no_especificado",
        "location": "no_especificado",
        "salary": _empty_salary(),
    }


def _normalize_work_conditions(raw: Any) -> WorkConditions:
    base = _empty_work_conditions()
    if not isinstance(raw, dict):
        return base
    source = raw
    modality = _clean_text(source.get("modality") or source.get("modalidad"), max_chars=60)
    schedule = _clean_text(source.get("schedule") or source.get("horario"), max_chars=80)
    contract_type = _clean_text(
        source.get("contract_type") or source.get("tipo_contrato") or source.get("contract"),
        max_chars=80,
    )
    location = _clean_text(source.get("location") or source.get("ubicacion"), max_chars=120)
    salary = _normalize_salary(source.get("salary"))
    if not salary["text_original"]:
        salary["text_original"] = _clean_text(
            source.get("salary_text") or source.get("salario"),
            max_chars=220,
        )
    base["modality"] = modality or base["modality"]
    base["schedule"] = schedule or base["schedule"]
    base["contract_type"] = contract_type or base["contract_type"]
    base["location"] = location or base["location"]
    base["salary"] = salary
    return base


def _derive_legacy_work_conditions(
    conditions: list[str],
    *,
    fallback_location: str = "",
) -> WorkConditions:
    base = _empty_work_conditions()
    joined = " ".join(conditions).lower()
    if "remote" in joined or "remoto" in joined:
        base["modality"] = "remote"
    elif "hybrid" in joined or "hibrid" in joined:
        base["modality"] = "hybrid"
    elif "presencial" in joined or "on-site" in joined or "onsite" in joined:
        base["modality"] = "onsite"
    if "fijo" in joined:
        base["schedule"] = "horario_fijo"
    elif "flex" in joined:
        base["schedule"] = "flexible"
    if "indefinido" in joined:
        base["contract_type"] = "indefinido"
    elif "fijo" in joined:
        base["contract_type"] = "fijo"
    elif "prestacion" in joined:
        base["contract_type"] = "prestacion_servicios"
    salary_line = next(
        (item for item in conditions if "salario" in item.lower() or "compens" in item.lower()),
        "",
    )
    if salary_line:
        base["salary"]["text_original"] = _clean_text(salary_line, max_chars=220)
    if fallback_location.strip():
        base["location"] = _clean_text(fallback_location, max_chars=120)
    return base


def _derive_seniority(raw_title: str, raw_text: str) -> str:
    text = f"{raw_title} {raw_text}".lower()
    if any(token in text for token in ("principal", "staff")):
        return "principal"
    if any(token in text for token in ("senior", "sr", "ssr")):
        return "senior"
    if any(token in text for token in ("semi senior", "semi-senior", "semisenior")):
        return "semi_senior"
    if any(token in text for token in ("junior", "jr")):
        return "junior"
    return "no_especificado"


def _derive_organizational_level(raw_title: str, raw_text: str) -> str:
    text = f"{raw_title} {raw_text}".lower()
    if any(token in text for token in ("director", "head", "vp", "vicepresident")):
        return "director"
    if any(token in text for token in ("manager", "gerente")):
        return "manager"
    if any(token in text for token in ("lead", "lider", "líder")):
        return "team_lead"
    if any(token in text for token in ("analyst", "designer", "developer", "engineer", "specialist")):
        return "individual_contributor"
    return "no_especificado"


def _default_profile() -> OpportunityProfile:
    return {
        "summary": "",
        "seniority": "no_especificado",
        "organizational_level": "no_especificado",
        "funciones_responsabilidades": [],
        "requisitos_obligatorios": [],
        "requisitos_deseables": [],
        "condiciones_trabajo": _empty_work_conditions(),
        "beneficios": [],
        "confidence": "low",
        "extraction_source": "none",
    }


def _normalize_profile(raw: dict[str, object]) -> OpportunityProfile:
    profile = _default_profile()
    profile["summary"] = _clean_text(raw.get("summary"), max_chars=420)
    profile["seniority"] = (
        _clean_text(raw.get("seniority"), max_chars=40).lower() or "no_especificado"
    )
    profile["organizational_level"] = (
        _clean_text(raw.get("organizational_level"), max_chars=60).lower() or "no_especificado"
    )
    profile["funciones_responsabilidades"] = _clean_list(
        raw.get("funciones_responsabilidades"),
        max_items=None,
    )
    profile["requisitos_obligatorios"] = _clean_list(
        raw.get("requisitos_obligatorios"),
        max_items=None,
    )
    profile["requisitos_deseables"] = _clean_list(
        raw.get("requisitos_deseables"),
        max_items=None,
    )
    profile["beneficios"] = _clean_list(raw.get("beneficios"), max_items=None)
    profile["condiciones_trabajo"] = _normalize_work_conditions(raw.get("condiciones_trabajo"))
    confidence = _clean_text(raw.get("confidence"), max_chars=20).lower()
    profile["confidence"] = confidence if confidence in {"low", "medium", "high"} else "medium"
    source = _clean_text(raw.get("extraction_source"), max_chars=30).lower()
    profile["extraction_source"] = source if source else "llm"
    if profile["seniority"] == "no_especificado":
        profile["seniority"] = _derive_seniority(
            _clean_text(raw.get("title"), max_chars=120),
            _clean_text(raw.get("description"), max_chars=400),
        )
    if profile["organizational_level"] == "no_especificado":
        profile["organizational_level"] = _derive_organizational_level(
            _clean_text(raw.get("title"), max_chars=120),
            _clean_text(raw.get("description"), max_chars=400),
        )
    return profile


def _line_bucket(
    raw_text: str,
    keywords: tuple[str, ...],
    *,
    max_items: int | None = 10,
) -> list[str]:
    lines = [line.strip(" -\t") for line in raw_text.splitlines() if line.strip()]
    picks: list[str] = []
    seen: set[str] = set()
    for line in lines:
        lower = line.lower()
        if not any(keyword in lower for keyword in keywords):
            continue
        compact = _clean_text(line, max_chars=200)
        if not compact:
            continue
        key = compact.lower()
        if key in seen:
            continue
        seen.add(key)
        picks.append(compact)
        if max_items and max_items > 0 and len(picks) >= max_items:
            break
    return picks


def _heuristic_profile(opportunity: OpportunityRecord) -> OpportunityProfile:
    raw_text = str(opportunity.get("snapshot_raw_text", "")).strip()
    text = " ".join(raw_text.split())
    profile = _default_profile()
    profile["summary"] = _clean_text(text, max_chars=420)
    profile["funciones_responsabilidades"] = _line_bucket(
        raw_text,
        ("responsabilidad", "funcion", "función", "rol", "you will", "tareas"),
        max_items=30,
    )
    profile["requisitos_obligatorios"] = _line_bucket(
        raw_text,
        ("requisito", "must", "obligatorio", "experiencia en", "dominio de"),
        max_items=40,
    )
    profile["requisitos_deseables"] = _line_bucket(
        raw_text,
        ("deseable", "nice to have", "plus", "ideal", "preferible"),
        max_items=30,
    )
    conditions = _line_bucket(
        raw_text,
        ("modalidad", "remoto", "hibrido", "presencial", "salario", "contrato", "horario", "ubicacion"),
        max_items=20,
    )
    profile["beneficios"] = _line_bucket(
        raw_text,
        ("beneficio", "ofrecemos", "benefits", "perks", "bono"),
        max_items=30,
    )
    profile["condiciones_trabajo"] = _derive_legacy_work_conditions(
        conditions,
        fallback_location=str(opportunity.get("location", "")),
    )
    profile["seniority"] = _derive_seniority(
        str(opportunity.get("title", "")),
        raw_text,
    )
    profile["organizational_level"] = _derive_organizational_level(
        str(opportunity.get("title", "")),
        raw_text,
    )
    if not profile["summary"]:
        profile["summary"] = _clean_text(opportunity.get("title"), max_chars=220)
    profile["confidence"] = "low"
    profile["extraction_source"] = "heuristic"
    return profile


def extract_structured_opportunity_profile(
    opportunity: OpportunityRecord,
    settings: Settings,
) -> OpportunityProfile:
    system_prompt = (
        "Eres un analista funcional de vacantes. "
        "Extraes requisitos y condiciones de forma estructurada sin inventar."
    )
    fallback_user_prompt = (
        "Extrae informacion clave de esta vacante y responde SOLO JSON valido.\n"
        "Formato exacto:\n"
        "{"
        "\"summary\":\"\","
        "\"seniority\":\"\","
        "\"organizational_level\":\"\","
        "\"funciones_responsabilidades\":[],"
        "\"requisitos_obligatorios\":[],"
        "\"requisitos_deseables\":[],"
        "\"condiciones_trabajo\":{"
        "\"modality\":\"\","
        "\"schedule\":\"\","
        "\"contract_type\":\"\","
        "\"location\":\"\","
        "\"salary\":{\"min\":null,\"max\":null,\"currency\":\"\",\"period\":\"\",\"text_original\":\"\"}"
        "},"
        "\"beneficios\":[],"
        "\"confidence\":\"low|medium|high\","
        "\"extraction_source\":\"llm\""
        "}\n"
        "Reglas:\n"
        "- No inventes datos ausentes.\n"
        "- Si no hay evidencia, deja listas vacias.\n"
        "- Separa requisitos obligatorios vs deseables.\n"
        "- En condiciones_trabajo usa no_especificado cuando no aparezca el dato.\n"
        "- No agregues campos fuera del esquema definido.\n\n"
        f"Vacante titulo: {opportunity.get('title', '')}\n"
        f"Empresa: {opportunity.get('company', '')}\n"
        f"Ubicacion: {opportunity.get('location', '')}\n"
        f"URL: {opportunity.get('source_url', '')}\n"
        f"Descripcion:\n{opportunity.get('snapshot_raw_text', '')}"
    )
    user_prompt = build_prompt_text(
        flow_key=FLOW_TASK_VACANCY_PROFILE_EXTRACT,
        context={
            "opportunity_title": str(opportunity.get("title", "")).strip(),
            "opportunity_company": str(opportunity.get("company", "")).strip(),
            "opportunity_location": str(opportunity.get("location", "")).strip(),
            "opportunity_url": str(opportunity.get("source_url", "")).strip(),
            "opportunity_raw_text": str(opportunity.get("snapshot_raw_text", "")).strip(),
        },
        fallback=fallback_user_prompt,
    )
    response_text = complete_prompt(
        system_prompt,
        user_prompt,
        settings,
        temperature=0.1,
        person_id=opportunity["person_id"],
        opportunity_id=opportunity["opportunity_id"],
        flow_key=FLOW_TASK_VACANCY_PROFILE_EXTRACT,
    )
    if not response_text or response_text == FALLBACK_MESSAGE:
        return _heuristic_profile(opportunity)
    parsed = _extract_json_object(response_text)
    if not parsed:
        return _heuristic_profile(opportunity)
    return _normalize_profile(parsed)
