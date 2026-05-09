from __future__ import annotations

from typing import Any, TypedDict

from app.services.vacancy_dimensions_contract import normalize_salary_normalization


CONTRACT_VERSION_VACANCY_SALARY_NORMALIZATION = "vacancy_salary_normalization.v1"
VARIABLE_COMPONENT_TYPE_VALUES = {"", "commission", "bonus", "mixed", "unknown"}


class VacancySalaryNormalizationPayload(TypedDict):
    min: int | None
    max: int | None
    currency: str
    period: str
    raw_text: str
    has_variable_component: bool
    variable_component_type: str
    variable_component_note: str


class VacancySalaryNormalizationContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    salary: VacancySalaryNormalizationPayload


def _clean_text(value: Any, *, max_chars: int = 120) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return value in (1, "1", "true", "True", "yes", "si", "sí")


def empty_vacancy_salary_normalization_contract() -> VacancySalaryNormalizationContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_SALARY_NORMALIZATION,
        "vacancy_id": "",
        "generated_at": "",
        "salary": {
            **normalize_salary_normalization({}),
            "has_variable_component": False,
            "variable_component_type": "",
            "variable_component_note": "",
        },
    }


def normalize_vacancy_salary_normalization_contract(raw: Any) -> VacancySalaryNormalizationContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_salary_normalization_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)
    salary_source = source.get("salary") if isinstance(source.get("salary"), dict) else source
    base_salary = normalize_salary_normalization(salary_source)
    variable_component_type = (
        _clean_text(
            salary_source.get("variable_component_type") if isinstance(salary_source, dict) else "",
            max_chars=24,
        ).lower()
    )
    variable_component_note = _clean_text(
        salary_source.get("variable_component_note") if isinstance(salary_source, dict) else "",
        max_chars=120,
    )
    has_variable_component = _normalize_bool(
        salary_source.get("has_variable_component")
        if isinstance(salary_source, dict)
        else False
    ) or bool(variable_component_type or variable_component_note)
    normalized["salary"] = {
        **base_salary,
        "has_variable_component": has_variable_component,
        "variable_component_type": (
            variable_component_type
            if variable_component_type in VARIABLE_COMPONENT_TYPE_VALUES
            else ("unknown" if has_variable_component else "")
        ),
        "variable_component_note": variable_component_note,
    }
    return normalized


def is_vacancy_salary_normalization_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return str(raw.get("contract_version", "")).strip() == CONTRACT_VERSION_VACANCY_SALARY_NORMALIZATION
