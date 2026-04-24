from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt
from app.services.prompt_config_store import (
    FLOW_TASK_VACANCY_RETRIEVAL_QUERIES_EXTRACT,
    build_prompt_text,
)
from app.services.vacancy_dimensions_enriched_contract import (
    is_vacancy_dimensions_enriched_contract,
    normalize_vacancy_dimensions_enriched_contract,
)
from app.services.vacancy_retrieval_queries_contract import (
    VacancyRetrievalQueriesContract,
    normalize_vacancy_retrieval_queries_contract,
)
from app.services.vacancy_salary_contract import (
    is_vacancy_salary_normalization_contract,
    normalize_vacancy_salary_normalization_contract,
)
from app.services.vacancy_v2_runtime_config import get_vacancy_v2_runtime_config


class VacancyRetrievalQueriesExtractionError(RuntimeError):
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
    if "queries" in parsed:
        return parsed
    return {"queries": parsed}


def _has_any_queries(contract: VacancyRetrievalQueriesContract) -> bool:
    payload = contract["queries"]
    return any(
        [
            bool(payload["responsibilities"]),
            bool(payload["required_criteria"]),
            bool(payload["desirable_criteria"]),
            bool(payload["benefits"]),
            bool(payload["about_the_company"]),
            bool(payload["work_conditions"]["salary"]),
            bool(payload["work_conditions"]["modality"]),
            bool(payload["work_conditions"]["location"]),
            bool(payload["work_conditions"]["contract_type"]),
            bool(payload["work_conditions"]["other_conditions"]),
        ]
    )


def extract_vacancy_retrieval_queries(
    opportunity: dict[str, Any],
    vacancy_dimensions_enriched_artifact: dict[str, Any],
    vacancy_salary_artifact: dict[str, Any] | None,
    settings: Any,
) -> VacancyRetrievalQueriesContract:
    if not isinstance(vacancy_dimensions_enriched_artifact, dict) or not is_vacancy_dimensions_enriched_contract(vacancy_dimensions_enriched_artifact):
        raise VacancyRetrievalQueriesExtractionError(
            "Step 4 requires a valid vacancy_dimensions_enriched.v1 artifact."
        )

    normalized_enriched = normalize_vacancy_dimensions_enriched_contract(vacancy_dimensions_enriched_artifact)
    vacancy_id = normalized_enriched["vacancy_id"] or str(opportunity.get("opportunity_id", "")).strip()
    generated_at = _now_iso()
    enriched_json = json.dumps(normalized_enriched, ensure_ascii=False)

    salary_json = "{}"
    if isinstance(vacancy_salary_artifact, dict) and is_vacancy_salary_normalization_contract(vacancy_salary_artifact):
        salary_json = json.dumps(
            normalize_vacancy_salary_normalization_contract(vacancy_salary_artifact),
            ensure_ascii=False,
        )

    system_prompt = (
        "You are a vacancy retrieval query generator. Return valid JSON only for vacancy_retrieval_queries.v1. "
        "Do not reclassify the vacancy. Do not generate categories. Do not decide compliance. "
        "Generate search queries that help retrieve evidence from the CV for each item."
    )
    fallback_user_prompt = (
        "Generate retrieval queries and respond with valid JSON only. "
        "Root key allowed: queries. "
        "Allowed keys inside queries: responsibilities, required_criteria, desirable_criteria, benefits, about_the_company, work_conditions. "
        "Inside work_conditions use only: salary, modality, location, contract_type, other_conditions. "
        "Each query item must include exactly: item_id, item_index, group_code, raw_text, queries. "
        "Use the metadata already present in the input items. Do not invent new ids or group codes. "
        "Queries should be phrased to retrieve evidence from the CV, not to summarize the vacancy. "
        "If an item does not justify a useful query, leave queries empty. "
        f"Vacancy title: {opportunity.get('title', '')}. "
        f"Company: {opportunity.get('company', '')}. "
        f"Location: {opportunity.get('location', '')}. "
        f"URL: {opportunity.get('source_url', '')}. "
        f"Input vacancy_dimensions_enriched.v1: {enriched_json}. "
        f"Input vacancy_salary_normalization.v1: {salary_json}"
    )
    user_prompt = build_prompt_text(
        flow_key=FLOW_TASK_VACANCY_RETRIEVAL_QUERIES_EXTRACT,
        context={
            "opportunity_title": str(opportunity.get("title", "")).strip(),
            "opportunity_company": str(opportunity.get("company", "")).strip(),
            "opportunity_location": str(opportunity.get("location", "")).strip(),
            "opportunity_url": str(opportunity.get("source_url", "")).strip(),
            "vacancy_dimensions_enriched_json": enriched_json,
            "vacancy_salary_json": salary_json,
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
        flow_key=FLOW_TASK_VACANCY_RETRIEVAL_QUERIES_EXTRACT,
    )
    if not response_text or response_text == FALLBACK_MESSAGE:
        raise VacancyRetrievalQueriesExtractionError(
            "Step 4 LLM response unavailable; retrieval query extraction aborted."
        )

    parsed = _extract_json_object(response_text)
    if not parsed:
        raise VacancyRetrievalQueriesExtractionError(
            "Step 4 LLM response is not valid JSON; retrieval query extraction aborted."
        )

    candidate = _contract_candidate_from_llm(parsed)
    normalized = normalize_vacancy_retrieval_queries_contract(candidate)
    normalized["vacancy_id"] = vacancy_id
    normalized["generated_at"] = generated_at

    if _has_any_queries(normalized):
        return normalized

    raise VacancyRetrievalQueriesExtractionError(
        "Step 4 LLM response produced empty retrieval queries; extraction aborted."
    )
