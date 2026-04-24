from __future__ import annotations

from typing import Any, TypedDict

from app.services.vacancy_dimensions_contract import normalize_salary_normalization


CONTRACT_VERSION_VACANCY_SALARY_NORMALIZATION = "vacancy_salary_normalization.v1"


class VacancySalaryNormalizationPayload(TypedDict):
    min: int | None
    max: int | None
    currency: str
    period: str
    raw_text: str


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


def empty_vacancy_salary_normalization_contract() -> VacancySalaryNormalizationContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_SALARY_NORMALIZATION,
        "vacancy_id": "",
        "generated_at": "",
        "salary": normalize_salary_normalization({}),
    }


def normalize_vacancy_salary_normalization_contract(raw: Any) -> VacancySalaryNormalizationContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_salary_normalization_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)
    salary_source = source.get("salary") if isinstance(source.get("salary"), dict) else source
    normalized["salary"] = normalize_salary_normalization(salary_source)
    return normalized


def is_vacancy_salary_normalization_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return str(raw.get("contract_version", "")).strip() == CONTRACT_VERSION_VACANCY_SALARY_NORMALIZATION
