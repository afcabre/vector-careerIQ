from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_DIMENSIONS = "vacancy_dimensions.v1"

WORK_CONDITION_KEYS = (
    "salary",
    "modality",
    "location",
    "contract_type",
    "schedule",
    "availability",
    "travel",
    "legal_requirements",
    "relocation",
    "mobility_requirements",
)


class SalaryCondition(TypedDict):
    min: int | None
    max: int | None
    currency: str
    period: str
    text: str


class ModalityCondition(TypedDict):
    type: str
    location: str
    text: str


class LocationCondition(TypedDict):
    places: list[str]
    text: str


class ContractTypeCondition(TypedDict):
    type: str
    text: str


class ScheduleCondition(TypedDict):
    type: str
    detail: str
    text: str


class AvailabilityCondition(TypedDict):
    type: str
    detail: str
    text: str


class TravelCondition(TypedDict):
    required: bool | None
    frequency: str
    scope: str
    text: str


class LegalRequirementsCondition(TypedDict):
    documents_required: list[str]
    text: str


class RelocationCondition(TypedDict):
    required: bool | None
    destination: str
    text: str


class MobilityRequirementsCondition(TypedDict):
    vehicle_required: bool | None
    driving_license: list[str]
    other: list[str]
    text: str


class VacancyDimensionItem(TypedDict):
    id: str
    category: str
    semantic_queries: list[str]
    raw_text: str


class ResponsibilityItem(VacancyDimensionItem):
    task: str


class CompetencyItem(VacancyDimensionItem):
    requirement: str


class BenefitItem(VacancyDimensionItem):
    benefit: str


class WorkConditionsPayload(TypedDict):
    salary: SalaryCondition
    modality: ModalityCondition
    location: LocationCondition
    contract_type: ContractTypeCondition
    schedule: ScheduleCondition
    availability: AvailabilityCondition
    travel: TravelCondition
    legal_requirements: LegalRequirementsCondition
    relocation: RelocationCondition
    mobility_requirements: MobilityRequirementsCondition


class VacancyDimensionsPayload(TypedDict):
    work_conditions: WorkConditionsPayload
    responsibilities: list[ResponsibilityItem]
    required_competencies: list[CompetencyItem]
    desirable_competencies: list[CompetencyItem]
    benefits: list[BenefitItem]


class VacancyDimensionsContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    vacancy_dimensions: VacancyDimensionsPayload


def _clean_text(value: Any, *, max_chars: int = 800) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _normalize_text_list(raw: Any, *, max_items: int = 50, max_chars: int = 200) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for value in raw:
        cleaned = _clean_text(value, max_chars=max_chars)
        if not cleaned:
            continue
        signature = cleaned.casefold()
        if signature in seen:
            continue
        seen.add(signature)
        items.append(cleaned)
        if len(items) >= max_items:
            break
    return items


def _normalize_number(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _normalize_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "yes", "si", "1"}:
        return True
    if text in {"false", "no", "0"}:
        return False
    return None


def _empty_work_conditions() -> WorkConditionsPayload:
    return {
        "salary": {
            "min": None,
            "max": None,
            "currency": "",
            "period": "",
            "text": "",
        },
        "modality": {
            "type": "",
            "location": "",
            "text": "",
        },
        "location": {
            "places": [],
            "text": "",
        },
        "contract_type": {
            "type": "",
            "text": "",
        },
        "schedule": {
            "type": "",
            "detail": "",
            "text": "",
        },
        "availability": {
            "type": "",
            "detail": "",
            "text": "",
        },
        "travel": {
            "required": None,
            "frequency": "",
            "scope": "",
            "text": "",
        },
        "legal_requirements": {
            "documents_required": [],
            "text": "",
        },
        "relocation": {
            "required": None,
            "destination": "",
            "text": "",
        },
        "mobility_requirements": {
            "vehicle_required": None,
            "driving_license": [],
            "other": [],
            "text": "",
        },
    }


def _normalize_work_conditions(raw: Any) -> WorkConditionsPayload:
    source = raw if isinstance(raw, dict) else {}
    normalized = _empty_work_conditions()

    salary = source.get("salary") if isinstance(source.get("salary"), dict) else {}
    normalized["salary"] = {
        "min": _normalize_number(salary.get("min")),
        "max": _normalize_number(salary.get("max")),
        "currency": _clean_text(salary.get("currency"), max_chars=32),
        "period": _clean_text(salary.get("period"), max_chars=32),
        "text": _clean_text(salary.get("text"), max_chars=300),
    }

    modality = source.get("modality") if isinstance(source.get("modality"), dict) else {}
    normalized["modality"] = {
        "type": _clean_text(modality.get("type"), max_chars=80),
        "location": _clean_text(modality.get("location"), max_chars=120),
        "text": _clean_text(modality.get("text"), max_chars=300),
    }

    location = source.get("location") if isinstance(source.get("location"), dict) else {}
    normalized["location"] = {
        "places": _normalize_text_list(location.get("places"), max_items=20, max_chars=120),
        "text": _clean_text(location.get("text"), max_chars=300),
    }

    contract_type = (
        source.get("contract_type") if isinstance(source.get("contract_type"), dict) else {}
    )
    normalized["contract_type"] = {
        "type": _clean_text(contract_type.get("type"), max_chars=80),
        "text": _clean_text(contract_type.get("text"), max_chars=300),
    }

    schedule = source.get("schedule") if isinstance(source.get("schedule"), dict) else {}
    normalized["schedule"] = {
        "type": _clean_text(schedule.get("type"), max_chars=80),
        "detail": _clean_text(schedule.get("detail"), max_chars=160),
        "text": _clean_text(schedule.get("text"), max_chars=300),
    }

    availability = (
        source.get("availability") if isinstance(source.get("availability"), dict) else {}
    )
    normalized["availability"] = {
        "type": _clean_text(availability.get("type"), max_chars=80),
        "detail": _clean_text(availability.get("detail"), max_chars=160),
        "text": _clean_text(availability.get("text"), max_chars=300),
    }

    travel = source.get("travel") if isinstance(source.get("travel"), dict) else {}
    normalized["travel"] = {
        "required": _normalize_bool(travel.get("required")),
        "frequency": _clean_text(travel.get("frequency"), max_chars=80),
        "scope": _clean_text(travel.get("scope"), max_chars=120),
        "text": _clean_text(travel.get("text"), max_chars=300),
    }

    legal_requirements = (
        source.get("legal_requirements")
        if isinstance(source.get("legal_requirements"), dict)
        else {}
    )
    normalized["legal_requirements"] = {
        "documents_required": _normalize_text_list(
            legal_requirements.get("documents_required"),
            max_items=20,
            max_chars=120,
        ),
        "text": _clean_text(legal_requirements.get("text"), max_chars=300),
    }

    relocation = source.get("relocation") if isinstance(source.get("relocation"), dict) else {}
    normalized["relocation"] = {
        "required": _normalize_bool(relocation.get("required")),
        "destination": _clean_text(relocation.get("destination"), max_chars=120),
        "text": _clean_text(relocation.get("text"), max_chars=300),
    }

    mobility = (
        source.get("mobility_requirements")
        if isinstance(source.get("mobility_requirements"), dict)
        else {}
    )
    normalized["mobility_requirements"] = {
        "vehicle_required": _normalize_bool(mobility.get("vehicle_required")),
        "driving_license": _normalize_text_list(
            mobility.get("driving_license"),
            max_items=10,
            max_chars=64,
        ),
        "other": _normalize_text_list(mobility.get("other"), max_items=20, max_chars=120),
        "text": _clean_text(mobility.get("text"), max_chars=300),
    }

    return normalized


def _empty_item_payload() -> VacancyDimensionItem:
    return {
        "id": "",
        "category": "",
        "semantic_queries": [],
        "raw_text": "",
    }


def _normalize_atomic_item(
    raw: Any,
    *,
    item_key: str,
    prefix: str,
    position: int,
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    main_value = _clean_text(raw.get(item_key), max_chars=240)
    raw_text = _clean_text(raw.get("raw_text"), max_chars=500)
    if not main_value and not raw_text:
        return None
    item_id = _clean_text(raw.get("id"), max_chars=80) or f"{prefix}-{position:02d}"
    normalized = _empty_item_payload()
    normalized["id"] = item_id
    normalized["category"] = _clean_text(raw.get("category"), max_chars=80)
    normalized["semantic_queries"] = _normalize_text_list(
        raw.get("semantic_queries"),
        max_items=5,
        max_chars=240,
    )
    normalized["raw_text"] = raw_text
    normalized[item_key] = main_value or raw_text
    return normalized


def _normalize_atomic_list(
    raw: Any,
    *,
    item_key: str,
    prefix: str,
) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, value in enumerate(raw, start=1):
        normalized = _normalize_atomic_item(value, item_key=item_key, prefix=prefix, position=index)
        if not normalized:
            continue
        signature = "|".join(
            [
                str(normalized.get(item_key, "")).casefold(),
                str(normalized.get("category", "")).casefold(),
                str(normalized.get("raw_text", "")).casefold(),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _empty_vacancy_dimensions_payload() -> VacancyDimensionsPayload:
    return {
        "work_conditions": _empty_work_conditions(),
        "responsibilities": [],
        "required_competencies": [],
        "desirable_competencies": [],
        "benefits": [],
    }


def empty_vacancy_dimensions_contract() -> VacancyDimensionsContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_DIMENSIONS,
        "vacancy_id": "",
        "generated_at": "",
        "vacancy_dimensions": _empty_vacancy_dimensions_payload(),
    }


def normalize_vacancy_dimensions_contract(raw: Any) -> VacancyDimensionsContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_dimensions_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)

    payload = source.get("vacancy_dimensions")
    payload_source = payload if isinstance(payload, dict) else {}
    normalized["vacancy_dimensions"] = {
        "work_conditions": _normalize_work_conditions(payload_source.get("work_conditions")),
        "responsibilities": _normalize_atomic_list(
            payload_source.get("responsibilities"),
            item_key="task",
            prefix="RES",
        ),
        "required_competencies": _normalize_atomic_list(
            payload_source.get("required_competencies"),
            item_key="requirement",
            prefix="REQ",
        ),
        "desirable_competencies": _normalize_atomic_list(
            payload_source.get("desirable_competencies"),
            item_key="requirement",
            prefix="DES",
        ),
        "benefits": _normalize_atomic_list(
            payload_source.get("benefits"),
            item_key="benefit",
            prefix="BEN",
        ),
    }
    return normalized


def is_vacancy_dimensions_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return str(raw.get("contract_version", "")).strip() == CONTRACT_VERSION_VACANCY_DIMENSIONS
