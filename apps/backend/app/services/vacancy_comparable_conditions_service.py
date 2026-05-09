from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

from app.services.vacancy_comparable_conditions_contract import (
    VacancyComparableConditionsContract,
    normalize_vacancy_comparable_conditions_contract,
)
from app.services.vacancy_dimensions_contract import (
    is_vacancy_dimensions_contract,
    normalize_vacancy_dimensions_contract,
)
from app.services.vacancy_salary_contract import (
    is_vacancy_salary_normalization_contract,
    normalize_vacancy_salary_normalization_contract,
)


class VacancyComparableConditionsBuildError(RuntimeError):
    pass


_LOCATION_LABEL_PATTERN = re.compile(r"(?i)\b(ubicaci[oó]n|location|ciudad|city)\s*:\s*(.+)")
_MODALITY_LINE_PATTERN = re.compile(
    r"(?i)\b(remot[oa]|remote|h[ií]brid[oa]?|hybrid|presencial|on[\s-]?site|onsite)\b"
)
_CONTRACT_LINE_PATTERN = re.compile(
    r"(?i)\b(indefinid[oa]?|t[eé]rmino fijo|fixed term|prestaci[oó]n de servicios|service contract|obra labor|obra-labor|contratista)\b"
)
_SALARY_SIGNAL_PATTERN = re.compile(r"(?i)(salario|compens|remuner|\$\s*\d|usd|cop|eur|mxn)")
_MODALITY_INTENSITY_PATTERN = re.compile(r"(?i)\b(\d+\s*[xX]\s*\d+)\b")
_REMOTE_PATTERN = re.compile(r"(?i)\b(remot[oa]|remote)\b")
_HYBRID_PATTERN = re.compile(r"(?i)\b(h[ií]brid[oa]?|hybrid)\b")
_ONSITE_PATTERN = re.compile(r"(?i)\b(presencial|on[\s-]?site|onsite)\b")
_INDEFINITE_PATTERN = re.compile(r"(?i)\b(indefinid[oa]?)\b")
_FIXED_TERM_PATTERN = re.compile(r"(?i)\b(t[eé]rmino fijo|fixed term|obra labor|obra-labor|temporal)\b")
_SERVICE_CONTRACT_PATTERN = re.compile(r"(?i)\b(prestaci[oó]n de servicios|service contract|contratista)\b")

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


def _iter_work_condition_texts(vacancy_dimensions_artifact: dict[str, Any]) -> list[str]:
    normalized = normalize_vacancy_dimensions_contract(vacancy_dimensions_artifact)
    items = normalized["vacancy_dimensions"]["work_conditions"]
    return [
        _clean_text(item.get("raw_text", ""), max_chars=300)
        for item in items
        if isinstance(item, dict) and _clean_text(item.get("raw_text", ""), max_chars=300)
    ]


def _pick_location_raw(
    work_conditions: list[str],
    *,
    opportunity_location: str,
    snapshot_raw_text: str,
) -> tuple[str, str]:
    for item in work_conditions:
        match = _LOCATION_LABEL_PATTERN.search(item)
        if match:
            return _clean_text(match.group(2), max_chars=200), "high"
        lowered = item.casefold()
        if any(token in lowered for token, _, _ in _CITY_ALIASES) or any(
            token in lowered for token, _ in _COUNTRY_ALIASES
        ):
            return _clean_text(item, max_chars=200), "medium"
    if opportunity_location.strip():
        return _clean_text(opportunity_location, max_chars=200), "medium"

    compact_snapshot = _clean_text(snapshot_raw_text, max_chars=1500)
    if compact_snapshot:
        for line in re.split(r"[\n|]", compact_snapshot):
            cleaned = _clean_text(line, max_chars=200)
            lowered = cleaned.casefold()
            if any(token in lowered for token, _, _ in _CITY_ALIASES) or any(
                token in lowered for token, _ in _COUNTRY_ALIASES
            ):
                return cleaned, "low"
    return "", "none"


def _normalize_location(raw_text: str, *, confidence: str) -> tuple[dict[str, str], list[str]]:
    warnings: list[str] = []
    raw = _clean_text(raw_text, max_chars=200)
    if not raw:
        return {
            "raw": "",
            "normalized_city": "",
            "normalized_country": "",
            "confidence": "none",
        }, warnings

    lowered = raw.casefold()
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
    if raw.casefold().startswith("bogot") and not country:
        country = "Colombia"
    if not city and not country:
        warnings.append("vacancy_location_not_normalized")
        normalized_confidence = "low" if confidence != "none" else "none"
    else:
        normalized_confidence = confidence
    return {
        "raw": raw,
        "normalized_city": city,
        "normalized_country": country,
        "confidence": normalized_confidence,
    }, warnings


def _extract_modality(work_conditions: list[str], snapshot_raw_text: str) -> tuple[dict[str, str], list[str]]:
    text_candidates = work_conditions + [_clean_text(snapshot_raw_text, max_chars=2000)]
    for item in text_candidates:
        if not item:
            continue
        if not _MODALITY_LINE_PATTERN.search(item):
            continue
        raw = _clean_text(item, max_chars=200)
        intensity_match = _MODALITY_INTENSITY_PATTERN.search(raw)
        intensity = _clean_text(intensity_match.group(1), max_chars=32) if intensity_match else ""
        lowered = raw.casefold()
        if _REMOTE_PATTERN.search(lowered):
            mode = "remote"
        elif _HYBRID_PATTERN.search(lowered):
            mode = "hybrid"
        elif _ONSITE_PATTERN.search(lowered):
            mode = "onsite"
        else:
            mode = "unknown"
        confidence = "high" if item in work_conditions else "medium"
        return {
            "raw": raw,
            "mode": mode,
            "intensity": intensity,
            "confidence": confidence if mode != "unknown" else "low",
        }, []
    return {
        "raw": "",
        "mode": "unknown",
        "intensity": "",
        "confidence": "none",
    }, []


def _extract_contract_type(work_conditions: list[str], snapshot_raw_text: str) -> tuple[dict[str, str], list[str]]:
    warnings: list[str] = []
    text_candidates = work_conditions + [_clean_text(snapshot_raw_text, max_chars=2000)]
    for item in text_candidates:
        if not item:
            continue
        if not _CONTRACT_LINE_PATTERN.search(item):
            continue
        raw = _clean_text(item, max_chars=220)
        lowered = raw.casefold()
        if _INDEFINITE_PATTERN.search(lowered):
            value = "indefinite"
        elif _SERVICE_CONTRACT_PATTERN.search(lowered):
            value = "service_contract"
        elif _FIXED_TERM_PATTERN.search(lowered):
            value = "fixed_term"
            if "obra labor" in lowered or "obra-labor" in lowered:
                warnings.append("vacancy_contract_type_mapped_from_obra_labor")
        else:
            value = "unknown"
        confidence = "high" if item in work_conditions else "medium"
        return {
            "raw": raw,
            "value": value,
            "confidence": confidence if value != "unknown" else "low",
        }, warnings
    return {
        "raw": "",
        "value": "unknown",
        "confidence": "none",
    }, warnings


def _first_salary_raw(work_conditions: list[str], snapshot_raw_text: str) -> str:
    for item in work_conditions:
        if _SALARY_SIGNAL_PATTERN.search(item):
            return _clean_text(item, max_chars=300)
    compact_snapshot = _clean_text(snapshot_raw_text, max_chars=2000)
    for line in re.split(r"[\n|]", compact_snapshot):
        cleaned = _clean_text(line, max_chars=300)
        if _SALARY_SIGNAL_PATTERN.search(cleaned):
            return cleaned
    return ""


def _build_compensation(
    work_conditions: list[str],
    snapshot_raw_text: str,
    vacancy_salary_artifact: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    salary_artifact = (
        normalize_vacancy_salary_normalization_contract(vacancy_salary_artifact)
        if is_vacancy_salary_normalization_contract(vacancy_salary_artifact)
        else normalize_vacancy_salary_normalization_contract({})
    )
    salary = salary_artifact["salary"]
    raw = salary["raw_text"] or _first_salary_raw(work_conditions, snapshot_raw_text)
    has_comparable = any(
        value is not None and value != ""
        for value in (salary["min"], salary["max"], salary["currency"], salary["period"])
    )
    confidence = "high" if has_comparable else ("medium" if raw else "none")
    if raw and not has_comparable:
        warnings.append("vacancy_compensation_not_fully_comparable")
    return {
        "raw": raw,
        "currency": salary["currency"],
        "min_amount": salary["min"],
        "max_amount": salary["max"],
        "period": salary["period"],
        "has_variable_component": bool(salary.get("has_variable_component", False)),
        "variable_component_type": str(salary.get("variable_component_type", "")).strip(),
        "variable_component_note": str(salary.get("variable_component_note", "")).strip(),
        "confidence": confidence,
    }, warnings


def build_vacancy_comparable_conditions(
    *,
    opportunity: dict[str, Any],
    vacancy_dimensions_artifact: dict[str, Any],
    vacancy_salary_artifact: dict[str, Any] | None = None,
) -> VacancyComparableConditionsContract:
    if not isinstance(vacancy_dimensions_artifact, dict) or not is_vacancy_dimensions_contract(
        vacancy_dimensions_artifact
    ):
        raise VacancyComparableConditionsBuildError(
            "C1 requires a valid vacancy_dimensions.v2 artifact."
        )

    work_conditions = _iter_work_condition_texts(vacancy_dimensions_artifact)
    vacancy_id = str(
        normalize_vacancy_dimensions_contract(vacancy_dimensions_artifact).get("vacancy_id")
        or opportunity.get("opportunity_id", "")
    ).strip()
    snapshot_raw_text = str(opportunity.get("snapshot_raw_text", "")).strip()
    location_raw, location_confidence = _pick_location_raw(
        work_conditions,
        opportunity_location=str(opportunity.get("location", "")).strip(),
        snapshot_raw_text=snapshot_raw_text,
    )
    location, location_warnings = _normalize_location(
        location_raw,
        confidence=location_confidence,
    )
    modality, modality_warnings = _extract_modality(work_conditions, snapshot_raw_text)
    contract_type, contract_warnings = _extract_contract_type(work_conditions, snapshot_raw_text)
    compensation, compensation_warnings = _build_compensation(
        work_conditions,
        snapshot_raw_text,
        vacancy_salary_artifact or {},
    )

    artifact = {
        "contract_version": "vacancy_comparable_conditions.v1",
        "vacancy_id": vacancy_id,
        "generated_at": _now_iso(),
        "location": location,
        "modality": modality,
        "compensation": compensation,
        "contract_type": contract_type,
        "warnings": (
            location_warnings
            + modality_warnings
            + contract_warnings
            + compensation_warnings
        ),
    }
    return normalize_vacancy_comparable_conditions_contract(artifact)
