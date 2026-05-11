from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt
from app.services.prompt_config_store import (
    FLOW_TASK_VACANCY_DIMENSIONS_EXTRACT,
    build_prompt_text,
)
from app.services.vacancy_blocks_contract import (
    VACANCY_BLOCK_KEYS,
    is_vacancy_blocks_contract,
    normalize_vacancy_blocks_contract,
)
from app.services.vacancy_dimensions_contract import (
    VacancyDimensionsContract,
    merge_quality_notes,
    normalize_vacancy_dimensions_contract,
)
from app.services.vacancy_v2_runtime_config import get_vacancy_v2_runtime_config


DIMENSIONS_KEYS = (
    "work_conditions",
    "responsibilities",
    "required_criteria",
    "desirable_criteria",
    "benefits",
    "about_the_company",
    "unclassified",
)

LEGACY_DIMENSIONS_KEYS = (
    "required_competencies",
    "desirable_competencies",
)


class VacancyDimensionsExtractionError(RuntimeError):
    pass


_PROFILE_OR_ROLE_CUES = (
    "busqueda de",
    "buscamos",
    "perfil ",
    "perfil estrategico",
    "capacidad de",
    "experiencia en",
    "experiencia comprobada",
    "conocimiento en",
    "con experiencia",
    "profesional en",
    "idealmente",
    "candidato ideal",
)

_RESPONSIBILITY_SCOPE_CUES = (
    "liderando",
    "liderar",
    "articular",
    "gestionar",
    "coordinar",
    "asegurar",
    "dirigir",
    "evolucion tecnologica",
    "transformacion digital",
)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


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


def _contract_candidate_from_llm(parsed: dict[str, object]) -> dict[str, object]:
    if "vacancy_dimensions" in parsed:
        return parsed
    if any(key in parsed for key in DIMENSIONS_KEYS + LEGACY_DIMENSIONS_KEYS):
        return {"vacancy_dimensions": parsed}
    return parsed


def _has_non_default_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, list):
        return any(_has_non_default_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_non_default_value(item) for item in value.values())
    return bool(value)


def _has_any_dimensions_content(contract: VacancyDimensionsContract) -> bool:
    payload = contract["vacancy_dimensions"]
    if payload["responsibilities"]:
        return True
    if payload["required_criteria"]:
        return True
    if payload["desirable_criteria"]:
        return True
    if payload["benefits"]:
        return True
    if payload["about_the_company"]:
        return True
    if payload["unclassified"]:
        return True
    return _has_non_default_value(payload["work_conditions"])


def _looks_like_profile_or_role_fragment(text: str) -> bool:
    normalized = " ".join(str(text).casefold().split())
    if not normalized:
        return False
    has_profile_cue = any(cue in normalized for cue in _PROFILE_OR_ROLE_CUES)
    has_scope_cue = any(cue in normalized for cue in _RESPONSIBILITY_SCOPE_CUES)
    return has_profile_cue and has_scope_cue


def _reclassify_about_fragments(contract: VacancyDimensionsContract) -> VacancyDimensionsContract:
    payload = contract["vacancy_dimensions"]
    about_items = payload["about_the_company"]
    if not about_items:
        return contract

    existing_required_signatures = {
        item["raw_text"].casefold() for item in payload["required_criteria"]
    }
    kept_about: list[dict[str, str]] = []
    moved_count = 0

    for item in about_items:
        raw_text = str(item.get("raw_text", "")).strip()
        if not _looks_like_profile_or_role_fragment(raw_text):
            kept_about.append(item)
            continue
        signature = raw_text.casefold()
        if signature not in existing_required_signatures:
            payload["required_criteria"].append({"raw_text": raw_text})
            existing_required_signatures.add(signature)
        moved_count += 1

    if moved_count:
        payload["about_the_company"] = kept_about
        contract["warnings"] = merge_quality_notes(
            contract.get("warnings", []),
            [
                "Step 3 reclassified one or more about_the_company fragments into required_criteria because they described the candidate profile or role scope."
            ],
        )
    return contract


def extract_vacancy_dimensions(
    opportunity: dict[str, Any],
    vacancy_blocks_artifact: dict[str, Any],
    settings: Any,
) -> VacancyDimensionsContract:
    if not isinstance(vacancy_blocks_artifact, dict) or not is_vacancy_blocks_contract(vacancy_blocks_artifact):
        raise VacancyDimensionsExtractionError(
            "Step 3 requires a valid vacancy_blocks.v2 artifact."
        )

    normalized_blocks = normalize_vacancy_blocks_contract(vacancy_blocks_artifact)
    if not any(normalized_blocks["vacancy_blocks"].get(key) for key in VACANCY_BLOCK_KEYS):
        raise VacancyDimensionsExtractionError(
            "Step 3 requires non-empty vacancy_blocks input."
        )

    opportunity_id = str(opportunity.get("opportunity_id", "")).strip()
    vacancy_id = normalized_blocks["vacancy_id"] or opportunity_id
    generated_at = _now_iso()
    blocks_json = json.dumps(normalized_blocks, ensure_ascii=False)

    system_prompt = (
        "You are a vacancy Step 3 normalizer. Return valid JSON only for vacancy_dimensions.v2. "
        "Keep work_conditions as a flat array of raw_text items. "
        "Do not classify work_conditions into salary, modality, location, contract_type, or other buckets. "
        "Do not generate ids, category labels, summaries, or semantic_queries. "
        "Do not invent semantic defaults. Preserve only information present in vacancy_blocks. "
        "When an atomic item depends on its parent sentence to remain understandable, preserve the minimum explicit context needed inside raw_text. "
        "Avoid orphan abstract items such as 'Ensure technical excellence' or 'Guarantee high-impact deliverables' when the original block already states the object or scope."
    )
    fallback_user_prompt = (
        "Transform vacancy_blocks.v2 into vacancy_dimensions.v2 and respond with valid JSON only. "
        "Root keys allowed: vacancy_dimensions, warnings, coverage_notes. "
        "Allowed keys inside vacancy_dimensions: work_conditions, responsibilities, required_criteria, "
        "desirable_criteria, benefits, about_the_company, unclassified. "
        "warnings and coverage_notes must stay at root level, never inside vacancy_dimensions. "
        "work_conditions must be a list of objects with raw_text only. "
        "All array items must be objects with raw_text only. "
        "Keep salary/compensation text in work_conditions as raw_text; Step 3.1 will normalize salary later. "
        "Keep benefits for non-compensation perks. "
        "Keep about_the_company only for real company context; if a block inherited from vacancy_blocks begins with the employer or a hiring phrase but actually describes the target profile, expected experience, leadership, or role scope, reclassify it into required_criteria or responsibilities based on its main meaning. "
        "When an atomic item would become too abstract on its own, keep the minimum explicit context already present in the same source block so the raw_text remains understandable. "
        "Do not leave orphan items such as 'Ensure technical excellence', 'Guarantee high-impact deliverables', 'Ensure profitability', or 'Coordinate stakeholders' when the original block states what they apply to. "
        "Use only context already present in vacancy_blocks; do not add new information or interpret hidden intent. "
        "If information cannot be transformed without loss, preserve it in unclassified and explain in coverage_notes. "
        "Do not invent keys and do not embed vacancy_blocks. "
        f"Vacancy title: {opportunity.get('title', '')}. "
        f"Company: {opportunity.get('company', '')}. "
        f"Location: {opportunity.get('location', '')}. "
        f"URL: {opportunity.get('source_url', '')}. "
        f"Input vacancy_blocks.v2: {blocks_json}"
    )
    user_prompt = build_prompt_text(
        flow_key=FLOW_TASK_VACANCY_DIMENSIONS_EXTRACT,
        context={
            "opportunity_title": str(opportunity.get("title", "")).strip(),
            "opportunity_company": str(opportunity.get("company", "")).strip(),
            "opportunity_location": str(opportunity.get("location", "")).strip(),
            "opportunity_url": str(opportunity.get("source_url", "")).strip(),
            "vacancy_blocks_json": blocks_json,
        },
        fallback=fallback_user_prompt,
    )

    runtime_config = get_vacancy_v2_runtime_config(settings)
    llm_temperature = float(runtime_config["step3"]["llm_temperature"])

    response_text = complete_prompt(
        system_prompt,
        user_prompt,
        settings,
        temperature=llm_temperature,
        person_id=str(opportunity.get("person_id", "")).strip(),
        opportunity_id=opportunity_id,
        flow_key=FLOW_TASK_VACANCY_DIMENSIONS_EXTRACT,
    )
    if not response_text or response_text == FALLBACK_MESSAGE:
        raise VacancyDimensionsExtractionError(
            "Step 3 LLM response unavailable; vacancy_dimensions extraction aborted."
        )

    parsed = _extract_json_object(response_text)
    if not parsed:
        raise VacancyDimensionsExtractionError(
            "Step 3 LLM response is not valid JSON; vacancy_dimensions extraction aborted."
        )

    candidate = _contract_candidate_from_llm(parsed)
    normalized = normalize_vacancy_dimensions_contract(candidate)
    normalized["vacancy_id"] = vacancy_id
    normalized["generated_at"] = generated_at
    normalized["warnings"] = merge_quality_notes(
        normalized_blocks.get("warnings", []),
        normalized.get("warnings", []),
    )
    normalized["coverage_notes"] = merge_quality_notes(
        normalized_blocks.get("coverage_notes", []),
        normalized.get("coverage_notes", []),
    )
    normalized = _reclassify_about_fragments(normalized)

    if _has_any_dimensions_content(normalized):
        return normalized

    raise VacancyDimensionsExtractionError(
        "Step 3 LLM response produced empty vacancy_dimensions; extraction aborted."
    )
