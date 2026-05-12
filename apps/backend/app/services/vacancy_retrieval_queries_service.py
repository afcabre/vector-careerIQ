from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt
from app.services.ai_runtime_config_store import get_ai_runtime_config
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


RETRIEVAL_ENABLED_GROUPS = (
    "responsibilities",
    "required_criteria",
    "desirable_criteria",
)

RETRIEVAL_DISABLED_GROUPS = (
    "benefits",
    "about_the_company",
    "work_conditions",
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
    if "queries" in parsed:
        return parsed
    return {"queries": parsed}


def _has_any_queries(contract: VacancyRetrievalQueriesContract) -> bool:
    payload = contract["queries"]
    return any(bool(payload[group]) for group in RETRIEVAL_ENABLED_GROUPS)


def _clear_disabled_retrieval_groups(contract: VacancyRetrievalQueriesContract) -> None:
    for group in RETRIEVAL_DISABLED_GROUPS:
        contract["queries"][group] = []


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
    ai_runtime_config = get_ai_runtime_config()
    retrieval_queries_per_item = int(ai_runtime_config["vacancy_retrieval_queries_per_item"])

    system_prompt = (
        "You are a vacancy retrieval query generator. Return valid JSON only for vacancy_retrieval_queries.v1. "
        "Do not reclassify the vacancy. Do not generate categories. Do not decide compliance. "
        "Generate search queries that help retrieve evidence from the CV for each item. "
        "Queries must be short retrieval probes, not interview questions, not role-play prompts, and not compliance judgments. "
        "Use the dominant language of the vacancy and CV pair; if both are in Spanish, generate the probes in Spanish. "
        "Do not use question marks or second-person interview wording. "
        "Do not switch to English unnecessarily; preserve acronyms, proper nouns, and technology names when needed. "
        "Queries must be probative, not just semantically similar restatements of the requirement. "
        "When the criterion is abstract, translate it into observable signals such as roles, responsibilities, metrics, business outcomes, certifications, years of experience, budget ownership, stakeholder management, governance, architecture, cost optimization, profitability, delivery control, or transformation results. "
        f"For each item that merits queries, generate exactly {retrieval_queries_per_item} distinct useful queries with diverse probative angles."
    )
    fallback_user_prompt = (
        "Generate retrieval queries and respond with valid JSON only. "
        "Root key allowed: queries. "
        "Allowed keys inside queries: responsibilities, required_criteria, desirable_criteria, benefits, about_the_company, work_conditions. "
        "work_conditions must be a flat list of query items, not an object with subcategories. "
        "Generate non-empty queries only for responsibilities, required_criteria, and desirable_criteria. "
        "Keep benefits, about_the_company, and work_conditions present but empty. "
        "Each query item must include exactly: item_id, item_index, group_code, raw_text, queries. "
        "Use the metadata already present in the input items. Do not invent new ids or group codes. "
        "Queries should be phrased to retrieve evidence from the CV, not to summarize the vacancy. "
        "Use short retrieval probes rather than long sentences. "
        "Do not phrase the queries as questions. Do not use question marks. "
        "If the vacancy and CV context are in Spanish, write the probes in Spanish. "
        "Do not switch to English unnecessarily; preserve acronyms, proper nouns, and technology names only when needed. "
        "Avoid second-person interview wording such as 'can you', 'what is your', or 'how have you'. "
        "Prioritize observable evidence patterns such as equivalent responsibilities, measurable outcomes, technologies used, certifications, years of experience, business cases, budget ownership, stakeholder coordination, time-cost-scope control, efficiency gains, profitability, governance, standards, architecture, and transformation results. "
        "When a criterion is abstract, translate it into concrete observable evidence rather than merely repeating the wording of the vacancy. "
        f"For each item that merits queries, generate exactly {retrieval_queries_per_item} distinct useful queries with diverse probative angles. "
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
            "retrieval_queries_per_item": str(retrieval_queries_per_item),
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
    _clear_disabled_retrieval_groups(normalized)

    if _has_any_queries(normalized):
        return normalized

    raise VacancyRetrievalQueriesExtractionError(
        "Step 4 LLM response produced empty retrieval queries; extraction aborted."
    )
