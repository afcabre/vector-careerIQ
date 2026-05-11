from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.candidate_preference_checks_contract import (
    CandidatePreferenceChecksContract,
    normalize_candidate_preference_checks_contract,
)
from app.services.candidate_preference_profile_contract import (
    is_candidate_preference_profile_contract,
    normalize_candidate_preference_profile_contract,
)
from app.services.vacancy_comparable_conditions_contract import (
    is_vacancy_comparable_conditions_contract,
    normalize_vacancy_comparable_conditions_contract,
)


class CandidatePreferenceChecksBuildError(RuntimeError):
    pass


STATE_MATCH = "🟢 Cumple"
STATE_PARTIAL = "🟡 Parcial"
STATE_UNKNOWN = "⚪ Sin informacion"
STATE_CONFLICT = "🔴 En conflicto"

_CITY_ALIASES = (
    ("bogot", "Bogota", "Colombia"),
    ("medell", "Medellin", "Colombia"),
    ("cali", "Cali", "Colombia"),
    ("barranquilla", "Barranquilla", "Colombia"),
    ("cartagena", "Cartagena", "Colombia"),
    ("bucaramanga", "Bucaramanga", "Colombia"),
    ("mexico city", "Ciudad de Mexico", "Mexico"),
    ("ciudad de mexico", "Ciudad de Mexico", "Mexico"),
    ("lima", "Lima", "Peru"),
    ("quito", "Quito", "Ecuador"),
    ("santiago", "Santiago", "Chile"),
)
_COUNTRY_ALIASES = (
    ("colombia", "Colombia"),
    ("mexico", "Mexico"),
    ("méxico", "Mexico"),
    ("peru", "Peru"),
    ("perú", "Peru"),
    ("ecuador", "Ecuador"),
    ("argentina", "Argentina"),
    ("chile", "Chile"),
    ("usa", "United States"),
    ("estados unidos", "United States"),
    ("united states", "United States"),
)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _clean_text(value: Any, *, max_chars: int = 300) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _normalize_place(raw: str) -> tuple[str, str]:
    lowered = _clean_text(raw, max_chars=200).casefold()
    city = ""
    country = ""
    for token, normalized_city, default_country in _CITY_ALIASES:
        if token in lowered:
            city = normalized_city
            country = default_country
            break
    for token, normalized_country in _COUNTRY_ALIASES:
        if token in lowered:
            country = normalized_country
            break
    return city, country


def _format_place(city: str, country: str, *, fallback: str = "") -> str:
    parts = [part for part in (city, country) if part]
    if parts:
        return ", ".join(parts)
    return _clean_text(fallback, max_chars=200)


def _candidate_location_matches(
    vacancy_city: str,
    vacancy_country: str,
    accepted_locations: list[str],
    current_location: str,
) -> bool:
    candidates = accepted_locations[:] if accepted_locations else []
    if current_location:
        candidates.append(current_location)
    for item in candidates:
        city, country = _normalize_place(item)
        if vacancy_city and city and vacancy_city.casefold() == city.casefold():
            if not vacancy_country or not country or vacancy_country.casefold() == country.casefold():
                return True
        if not vacancy_city and vacancy_country and country and vacancy_country.casefold() == country.casefold():
            return True
    return False


def _build_location_row(
    candidate_artifact: dict[str, Any],
    vacancy_artifact: dict[str, Any],
) -> tuple[dict[str, str], list[str]]:
    warnings: list[str] = []
    comparable = candidate_artifact["comparable_preferences"]
    location = vacancy_artifact["location"]
    modality = vacancy_artifact["modality"]

    vacancy_value = _format_place(
        location["normalized_city"],
        location["normalized_country"],
        fallback=location["raw"],
    )
    accepted_locations = list(comparable["accepted_locations"])
    current_location = str(comparable["current_location"]).strip()
    candidate_value = "; ".join(accepted_locations) if accepted_locations else current_location

    if modality["mode"] == "remote":
        return {
            "criterion_key": "location",
            "criterion": "Ubicacion",
            "state": STATE_MATCH,
            "vacancy_value": vacancy_value or "Remoto",
            "candidate_value": candidate_value,
            "why": "La vacante es remota, por lo que la ciudad no actua como bloqueador.",
            "confidence": "high",
        }, warnings

    if not vacancy_value:
        return {
            "criterion_key": "location",
            "criterion": "Ubicacion",
            "state": STATE_UNKNOWN,
            "vacancy_value": "",
            "candidate_value": candidate_value,
            "why": "La vacante no especifica una ubicacion comparable con suficiente claridad.",
            "confidence": "none",
        }, warnings

    if not candidate_value:
        return {
            "criterion_key": "location",
            "criterion": "Ubicacion",
            "state": STATE_UNKNOWN,
            "vacancy_value": vacancy_value,
            "candidate_value": "",
            "why": "El perfil del candidato no declara ubicaciones aceptadas ni una ubicacion actual comparable.",
            "confidence": "none",
        }, warnings

    if _candidate_location_matches(
        location["normalized_city"],
        location["normalized_country"],
        accepted_locations,
        current_location,
    ):
        return {
            "criterion_key": "location",
            "criterion": "Ubicacion",
            "state": STATE_MATCH,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": "La ubicacion declarada de la vacante coincide con una ubicacion compatible del candidato.",
            "confidence": "high",
        }, warnings

    relocation = str(comparable["relocation_willingness"]).strip()
    if accepted_locations:
        if relocation == "yes":
            return {
                "criterion_key": "location",
                "criterion": "Ubicacion",
                "state": STATE_PARTIAL,
                "vacancy_value": vacancy_value,
                "candidate_value": candidate_value,
                "why": "La ubicacion no coincide con las preferidas, pero el candidato declara disposicion a relocalizarse.",
                "confidence": "medium",
            }, warnings
        if relocation == "no":
            return {
                "criterion_key": "location",
                "criterion": "Ubicacion",
                "state": STATE_CONFLICT,
                "vacancy_value": vacancy_value,
                "candidate_value": candidate_value,
                "why": "La ubicacion ofrecida queda fuera de las ubicaciones aceptadas y el candidato no desea relocalizarse.",
                "confidence": "high",
            }, warnings

    return {
        "criterion_key": "location",
        "criterion": "Ubicacion",
        "state": STATE_UNKNOWN,
        "vacancy_value": vacancy_value,
        "candidate_value": candidate_value,
        "why": "La ubicacion difiere, pero no hay una restriccion suficientemente fuerte para declararla como conflicto.",
        "confidence": "low",
    }, warnings


def _build_modality_row(
    candidate_artifact: dict[str, Any],
    vacancy_artifact: dict[str, Any],
) -> dict[str, str]:
    comparable = candidate_artifact["comparable_preferences"]
    accepted_modalities = list(comparable["accepted_modalities"])
    mode = str(vacancy_artifact["modality"]["mode"]).strip()
    vacancy_value = str(vacancy_artifact["modality"]["raw"]).strip() or mode
    candidate_value = ", ".join(accepted_modalities)

    if mode == "unknown":
        return {
            "criterion_key": "modality",
            "criterion": "Modalidad",
            "state": STATE_UNKNOWN,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": "La vacante no especifica una modalidad comparable con suficiente claridad.",
            "confidence": "none",
        }
    if not accepted_modalities:
        return {
            "criterion_key": "modality",
            "criterion": "Modalidad",
            "state": STATE_UNKNOWN,
            "vacancy_value": vacancy_value,
            "candidate_value": "",
            "why": "El perfil del candidato no declara modalidades aceptadas.",
            "confidence": "none",
        }
    if mode in accepted_modalities:
        return {
            "criterion_key": "modality",
            "criterion": "Modalidad",
            "state": STATE_MATCH,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": "La modalidad ofrecida esta dentro de las modalidades aceptadas por el candidato.",
            "confidence": "high",
        }
    return {
        "criterion_key": "modality",
        "criterion": "Modalidad",
        "state": STATE_CONFLICT,
        "vacancy_value": vacancy_value,
        "candidate_value": candidate_value,
        "why": "La modalidad ofrecida no coincide con las modalidades aceptadas por el candidato.",
        "confidence": "high",
    }


def _build_contract_type_row(
    candidate_artifact: dict[str, Any],
    vacancy_artifact: dict[str, Any],
) -> dict[str, str]:
    comparable = candidate_artifact["comparable_preferences"]
    accepted_contracts = list(comparable["contract_types_accepted"])
    contract_value = str(vacancy_artifact["contract_type"]["value"]).strip()
    vacancy_value = str(vacancy_artifact["contract_type"]["raw"]).strip() or contract_value
    candidate_value = ", ".join(accepted_contracts)

    if contract_value == "unknown":
        return {
            "criterion_key": "contract_type",
            "criterion": "Tipo de contrato",
            "state": STATE_UNKNOWN,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": "La vacante no especifica un tipo de contrato comparable.",
            "confidence": "none",
        }
    if not accepted_contracts:
        return {
            "criterion_key": "contract_type",
            "criterion": "Tipo de contrato",
            "state": STATE_UNKNOWN,
            "vacancy_value": vacancy_value,
            "candidate_value": "",
            "why": "El perfil del candidato no declara tipos de contrato aceptados.",
            "confidence": "none",
        }
    if contract_value in accepted_contracts:
        return {
            "criterion_key": "contract_type",
            "criterion": "Tipo de contrato",
            "state": STATE_MATCH,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": "El tipo de contrato ofrecido esta dentro de los tipos aceptados por el candidato.",
            "confidence": "high",
        }
    return {
        "criterion_key": "contract_type",
        "criterion": "Tipo de contrato",
        "state": STATE_CONFLICT,
        "vacancy_value": vacancy_value,
        "candidate_value": candidate_value,
        "why": "El tipo de contrato ofrecido no coincide con los tipos aceptados por el candidato.",
        "confidence": "high",
    }


def _build_compensation_row(
    candidate_artifact: dict[str, Any],
    vacancy_artifact: dict[str, Any],
) -> tuple[dict[str, str], list[str]]:
    warnings: list[str] = []
    expected = candidate_artifact["comparable_preferences"]["salary_expectation"]
    offered = vacancy_artifact["compensation"]

    candidate_has_range = expected["min"] is not None or expected["max"] is not None
    vacancy_has_range = offered["min_amount"] is not None or offered["max_amount"] is not None
    candidate_value = _format_salary_value(
        expected["min"],
        expected["max"],
        str(expected["currency"]),
        str(expected["period"]),
    )
    vacancy_value = _format_salary_value(
        offered["min_amount"],
        offered["max_amount"],
        str(offered["currency"]),
        str(offered["period"]),
        raw_fallback=str(offered["raw"]),
    )

    if not candidate_has_range:
        return {
            "criterion_key": "compensation",
            "criterion": "Compensacion",
            "state": STATE_UNKNOWN,
            "vacancy_value": vacancy_value,
            "candidate_value": "",
            "why": "El candidato no declara una expectativa salarial comparable.",
            "confidence": "none",
        }, warnings
    if not vacancy_has_range:
        return {
            "criterion_key": "compensation",
            "criterion": "Compensacion",
            "state": STATE_UNKNOWN,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": "La vacante no ofrece una base salarial comparable con suficiente claridad.",
            "confidence": "none",
        }, warnings

    candidate_currency = str(expected["currency"]).upper()
    vacancy_currency = str(offered["currency"]).upper()
    if candidate_currency and vacancy_currency and candidate_currency != vacancy_currency:
        warnings.append("compensation_currency_mismatch_not_normalized")
        return {
            "criterion_key": "compensation",
            "criterion": "Compensacion",
            "state": STATE_UNKNOWN,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": "La comparacion salarial no es deterministica porque vacante y candidato usan monedas distintas.",
            "confidence": "low",
        }, warnings

    candidate_period = str(expected["period"]).casefold()
    vacancy_period = str(offered["period"]).casefold()
    if candidate_period and vacancy_period and candidate_period != vacancy_period:
        warnings.append("compensation_period_mismatch_not_normalized")
        return {
            "criterion_key": "compensation",
            "criterion": "Compensacion",
            "state": STATE_UNKNOWN,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": "La comparacion salarial no es deterministica porque el periodo declarado no coincide.",
            "confidence": "low",
        }, warnings

    candidate_min = expected["min"]
    candidate_max = expected["max"]
    vacancy_min = offered["min_amount"]
    vacancy_max = offered["max_amount"]
    candidate_lower = candidate_min if candidate_min is not None else candidate_max
    candidate_upper = candidate_max if candidate_max is not None else candidate_min
    vacancy_lower = vacancy_min if vacancy_min is not None else vacancy_max
    vacancy_upper = vacancy_max if vacancy_max is not None else vacancy_min

    if candidate_lower is None or candidate_upper is None or vacancy_lower is None or vacancy_upper is None:
        return {
            "criterion_key": "compensation",
            "criterion": "Compensacion",
            "state": STATE_PARTIAL,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": "Hay una senal salarial comparable, pero la informacion esta incompleta en alguno de los lados.",
            "confidence": "medium",
        }, warnings

    suffix = ""
    if offered["has_variable_component"]:
        note = _clean_text(offered["variable_component_note"], max_chars=120)
        suffix = (
            f" Ademas, la vacante incluye componente variable ({note})."
            if note
            else " Ademas, la vacante incluye componente variable."
        )

    if candidate_lower > vacancy_upper:
        return {
            "criterion_key": "compensation",
            "criterion": "Compensacion",
            "state": STATE_CONFLICT,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": f"La expectativa minima del candidato supera la base fija comparable ofrecida.{suffix}",
            "confidence": "high",
        }, warnings
    if candidate_upper < vacancy_lower:
        return {
            "criterion_key": "compensation",
            "criterion": "Compensacion",
            "state": STATE_CONFLICT,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": f"La base fija comparable ofrecida supera el tope declarado por el candidato.{suffix}",
            "confidence": "high",
        }, warnings

    complete_candidate = expected["min"] is not None and expected["max"] is not None
    complete_vacancy = offered["min_amount"] is not None and offered["max_amount"] is not None
    if complete_candidate and complete_vacancy:
        return {
            "criterion_key": "compensation",
            "criterion": "Compensacion",
            "state": STATE_MATCH,
            "vacancy_value": vacancy_value,
            "candidate_value": candidate_value,
            "why": f"Existe traslape entre la base fija comparable ofrecida y la expectativa declarada del candidato.{suffix}",
            "confidence": "high",
        }, warnings
    return {
        "criterion_key": "compensation",
        "criterion": "Compensacion",
        "state": STATE_PARTIAL,
        "vacancy_value": vacancy_value,
        "candidate_value": candidate_value,
        "why": f"Existe compatibilidad parcial entre la base fija comparable ofrecida y la expectativa declarada, pero la informacion no es completa.{suffix}",
        "confidence": "medium",
    }, warnings


def _format_salary_value(
    min_value: Any,
    max_value: Any,
    currency: str,
    period: str,
    *,
    raw_fallback: str = "",
) -> str:
    min_text = str(min_value) if min_value is not None else ""
    max_text = str(max_value) if max_value is not None else ""
    parts = []
    if min_text and max_text and min_text != max_text:
        parts.append(f"{min_text} - {max_text}")
    elif min_text:
        parts.append(min_text)
    elif max_text:
        parts.append(max_text)
    if currency:
        parts.append(currency.upper())
    if period:
        parts.append(period)
    return " ".join(parts).strip() or _clean_text(raw_fallback, max_chars=200)


def build_candidate_preference_checks(
    *,
    person: dict[str, Any],
    opportunity: dict[str, Any],
    candidate_preference_profile_artifact: dict[str, Any],
    vacancy_comparable_conditions_artifact: dict[str, Any],
) -> CandidatePreferenceChecksContract:
    if not isinstance(candidate_preference_profile_artifact, dict) or not is_candidate_preference_profile_contract(
        candidate_preference_profile_artifact
    ):
        raise CandidatePreferenceChecksBuildError(
            "C2 requires a valid candidate_preference_profile.v1 artifact."
        )
    if not isinstance(vacancy_comparable_conditions_artifact, dict) or not is_vacancy_comparable_conditions_contract(
        vacancy_comparable_conditions_artifact
    ):
        raise CandidatePreferenceChecksBuildError(
            "C2 requires a valid vacancy_comparable_conditions.v1 artifact."
        )

    candidate_artifact = normalize_candidate_preference_profile_contract(
        candidate_preference_profile_artifact
    )
    vacancy_artifact = normalize_vacancy_comparable_conditions_contract(
        vacancy_comparable_conditions_artifact
    )

    location_row, location_warnings = _build_location_row(candidate_artifact, vacancy_artifact)
    modality_row = _build_modality_row(candidate_artifact, vacancy_artifact)
    compensation_row, compensation_warnings = _build_compensation_row(
        candidate_artifact,
        vacancy_artifact,
    )
    contract_row = _build_contract_type_row(candidate_artifact, vacancy_artifact)

    warnings = (
        list(candidate_artifact.get("warnings", []))
        + list(vacancy_artifact.get("warnings", []))
        + location_warnings
        + compensation_warnings
    )
    if str(candidate_artifact["comparable_preferences"]["travel_willingness"]).strip() != "unknown":
        warnings.append("travel_willingness_captured_but_not_compared_yet")
    if list(candidate_artifact["comparable_preferences"]["hard_constraints"]):
        warnings.append("hard_constraints_captured_but_not_compared_yet")

    artifact = {
        "contract_version": "candidate_preference_checks.v1",
        "vacancy_id": str(vacancy_artifact.get("vacancy_id") or opportunity.get("opportunity_id", "")).strip(),
        "person_id": str(candidate_artifact.get("person_id") or person.get("person_id", "")).strip(),
        "generated_at": _now_iso(),
        "rows": [
            location_row,
            modality_row,
            compensation_row,
            contract_row,
        ],
        "warnings": warnings,
    }
    return normalize_candidate_preference_checks_contract(artifact)
