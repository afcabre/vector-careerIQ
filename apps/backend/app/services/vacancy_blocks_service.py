from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

from app.core.settings import Settings
from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt
from app.services.opportunity_store import OpportunityRecord
from app.services.prompt_config_store import (
    FLOW_TASK_VACANCY_BLOCKS_EXTRACT,
    build_prompt_text,
)
from app.services.vacancy_blocks_contract import (
    VACANCY_BLOCK_KEYS,
    VacancyBlocksContract,
    empty_vacancy_blocks_contract,
    normalize_vacancy_blocks_contract,
)
from app.services.vacancy_v2_runtime_config import get_vacancy_v2_runtime_config


class VacancyBlocksExtractionError(RuntimeError):
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


def _with_metadata(
    raw_contract: Any,
    *,
    vacancy_id: str,
    generated_at: str,
) -> VacancyBlocksContract:
    normalized = normalize_vacancy_blocks_contract(raw_contract)
    normalized["vacancy_id"] = vacancy_id
    normalized["generated_at"] = generated_at
    return normalized


def _contract_candidate_from_llm(parsed: dict[str, object]) -> dict[str, object]:
    if "vacancy_blocks" in parsed:
        return parsed
    if any(key in parsed for key in VACANCY_BLOCK_KEYS):
        return {
            "vacancy_blocks": {key: parsed.get(key, []) for key in VACANCY_BLOCK_KEYS},
            "warnings": parsed.get("warnings", []),
            "coverage_notes": parsed.get("coverage_notes", []),
        }
    return parsed


def _has_any_classified_fragment(contract: VacancyBlocksContract) -> bool:
    payload = contract["vacancy_blocks"]
    return any(payload.get(key) for key in VACANCY_BLOCK_KEYS)


def extract_vacancy_blocks(
    opportunity: OpportunityRecord,
    settings: Settings,
) -> VacancyBlocksContract:
    vacancy_id = str(opportunity.get("opportunity_id", "")).strip()
    raw_text = str(opportunity.get("snapshot_raw_text", "")).strip()
    generated_at = _now_iso()

    if not raw_text:
        raise VacancyBlocksExtractionError(
            "Step 2 requires snapshot_raw_text; received empty input."
        )

    system_prompt = (
        "You are a vacancy Step 2 classifier. "
        "Return valid JSON only, preserving the raw meaning of fragments. "
        "Compensation signals (salary, pay, remuneration, compensation range) "
        "must be classified in work_conditions and never in benefits."
    )
    fallback_user_prompt = (
        "Classify this vacancy into vacancy_blocks.v1 and respond with valid JSON only. "
        "Root keys allowed: vacancy_blocks, warnings, coverage_notes. "
        "vacancy_blocks keys allowed: work_conditions, responsibilities, "
        "required_requirements, desirable_requirements, benefits, unclassified. "
        "Salary/compensation must always be in work_conditions and never in benefits. "
        "Rules: classify and clean text; do not summarize; do not atomize; do not invent keys. "
        f"Vacancy title: {opportunity.get('title', '')}. "
        f"Company: {opportunity.get('company', '')}. "
        f"Location: {opportunity.get('location', '')}. "
        f"URL: {opportunity.get('source_url', '')}. "
        f"Description: {raw_text}"
    )
    user_prompt = build_prompt_text(
        flow_key=FLOW_TASK_VACANCY_BLOCKS_EXTRACT,
        context={
            "opportunity_title": str(opportunity.get("title", "")).strip(),
            "opportunity_company": str(opportunity.get("company", "")).strip(),
            "opportunity_location": str(opportunity.get("location", "")).strip(),
            "opportunity_url": str(opportunity.get("source_url", "")).strip(),
            "opportunity_raw_text": raw_text,
        },
        fallback=fallback_user_prompt,
    )

    runtime_config = get_vacancy_v2_runtime_config(settings)
    llm_temperature = float(runtime_config["step2"]["llm_temperature"])

    response_text = complete_prompt(
        system_prompt,
        user_prompt,
        settings,
        temperature=llm_temperature,
        person_id=str(opportunity.get("person_id", "")).strip(),
        opportunity_id=vacancy_id,
        flow_key=FLOW_TASK_VACANCY_BLOCKS_EXTRACT,
    )
    if not response_text or response_text == FALLBACK_MESSAGE:
        raise VacancyBlocksExtractionError(
            "Step 2 LLM response unavailable; vacancy_blocks extraction aborted."
        )

    parsed = _extract_json_object(response_text)
    if not parsed:
        raise VacancyBlocksExtractionError(
            "Step 2 LLM response is not valid JSON; vacancy_blocks extraction aborted."
        )

    candidate = _contract_candidate_from_llm(parsed)
    normalized = _with_metadata(candidate, vacancy_id=vacancy_id, generated_at=generated_at)
    if _has_any_classified_fragment(normalized):
        return normalized

    raise VacancyBlocksExtractionError(
        "Step 2 LLM response produced empty vacancy_blocks; extraction aborted."
    )
