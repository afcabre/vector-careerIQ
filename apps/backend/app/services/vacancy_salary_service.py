from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt
from app.services.prompt_config_store import (
    FLOW_TASK_VACANCY_SALARY_NORMALIZE,
    build_prompt_text,
)
from app.services.vacancy_dimensions_contract import is_vacancy_dimensions_contract, normalize_vacancy_dimensions_contract
from app.services.vacancy_salary_contract import (
    VacancySalaryNormalizationContract,
    normalize_vacancy_salary_normalization_contract,
)
from app.services.vacancy_v2_runtime_config import get_vacancy_v2_runtime_config


class VacancySalaryNormalizationError(RuntimeError):
    pass


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
    if "salary" in parsed:
        return parsed
    if any(key in parsed for key in ("min", "max", "currency", "period", "raw_text", "text")):
        return {"salary": parsed}
    return parsed


def _has_any_salary_content(contract: VacancySalaryNormalizationContract) -> bool:
    salary = contract["salary"]
    if salary["min"] is not None:
        return True
    if salary["max"] is not None:
        return True
    if salary["currency"]:
        return True
    if salary["period"]:
        return True
    return bool(salary["raw_text"])


def extract_vacancy_salary_normalization(
    opportunity: dict[str, Any],
    vacancy_dimensions_artifact: dict[str, Any],
    settings: Any,
) -> VacancySalaryNormalizationContract:
    if not isinstance(vacancy_dimensions_artifact, dict) or not is_vacancy_dimensions_contract(vacancy_dimensions_artifact):
        raise VacancySalaryNormalizationError(
            "Step 3.1 requires a valid vacancy_dimensions.v2 artifact."
        )

    normalized_dimensions = normalize_vacancy_dimensions_contract(vacancy_dimensions_artifact)
    vacancy_id = normalized_dimensions["vacancy_id"] or str(opportunity.get("opportunity_id", "")).strip()
    generated_at = _now_iso()
    salary_raw_text = normalized_dimensions["vacancy_dimensions"]["work_conditions"]["salary"]["raw_text"]
    if not salary_raw_text:
        raise VacancySalaryNormalizationError(
            "Step 3.1 requires non-empty vacancy_dimensions.work_conditions.salary.raw_text."
        )

    system_prompt = (
        "You are a vacancy salary normalizer. Return valid JSON only for vacancy_salary_normalization.v1. "
        "Normalize salary into min, max, currency, period, and raw_text. "
        "Preserve raw_text exactly when min/max/currency/period are uncertain."
    )
    fallback_user_prompt = (
        "Normalize vacancy salary and respond with valid JSON only. "
        "Root key allowed: salary. "
        "Allowed keys inside salary: min, max, currency, period, raw_text. "
        "Do not invent extra keys. Keep raw_text aligned with the source salary signal. "
        f"Vacancy title: {opportunity.get('title', '')}. "
        f"Company: {opportunity.get('company', '')}. "
        f"Location: {opportunity.get('location', '')}. "
        f"URL: {opportunity.get('source_url', '')}. "
        f"Salary raw text: {salary_raw_text}"
    )
    user_prompt = build_prompt_text(
        flow_key=FLOW_TASK_VACANCY_SALARY_NORMALIZE,
        context={
            "opportunity_title": str(opportunity.get("title", "")).strip(),
            "opportunity_company": str(opportunity.get("company", "")).strip(),
            "opportunity_location": str(opportunity.get("location", "")).strip(),
            "opportunity_url": str(opportunity.get("source_url", "")).strip(),
            "salary_raw_text": salary_raw_text,
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
        opportunity_id=str(opportunity.get("opportunity_id", "")).strip(),
        flow_key=FLOW_TASK_VACANCY_SALARY_NORMALIZE,
    )
    if not response_text or response_text == FALLBACK_MESSAGE:
        raise VacancySalaryNormalizationError(
            "Step 3.1 LLM response unavailable; salary normalization aborted."
        )

    parsed = _extract_json_object(response_text)
    if not parsed:
        raise VacancySalaryNormalizationError(
            "Step 3.1 LLM response is not valid JSON; salary normalization aborted."
        )

    candidate = _contract_candidate_from_llm(parsed)
    normalized = normalize_vacancy_salary_normalization_contract(candidate)
    normalized["vacancy_id"] = vacancy_id
    normalized["generated_at"] = generated_at
    normalized["salary"]["raw_text"] = normalized["salary"]["raw_text"] or salary_raw_text

    if _has_any_salary_content(normalized):
        return normalized

    raise VacancySalaryNormalizationError(
        "Step 3.1 LLM response produced empty salary normalization; extraction aborted."
    )
