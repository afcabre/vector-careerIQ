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
    normalize_vacancy_dimensions_contract,
)
from app.services.vacancy_v2_runtime_config import get_vacancy_v2_runtime_config


DIMENSIONS_KEYS = (
    "work_conditions",
    "responsibilities",
    "required_competencies",
    "desirable_competencies",
    "benefits",
)


class VacancyDimensionsExtractionError(RuntimeError):
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
    if "vacancy_dimensions" in parsed:
        return parsed
    if any(key in parsed for key in DIMENSIONS_KEYS):
        return {
            "vacancy_dimensions": {key: parsed.get(key, [] if key != "work_conditions" else {}) for key in DIMENSIONS_KEYS}
        }
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
    if payload["required_competencies"]:
        return True
    if payload["desirable_competencies"]:
        return True
    if payload["benefits"]:
        return True
    return _has_non_default_value(payload["work_conditions"])


def extract_vacancy_dimensions(
    opportunity: dict[str, Any],
    vacancy_blocks_artifact: dict[str, Any],
    settings: Any,
) -> VacancyDimensionsContract:
    if not isinstance(vacancy_blocks_artifact, dict) or not is_vacancy_blocks_contract(vacancy_blocks_artifact):
        raise VacancyDimensionsExtractionError(
            "Step 3 requires a valid vacancy_blocks.v1 artifact."
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
        "You are a vacancy Step 3 normalizer. Return valid JSON only for vacancy_dimensions.v1."
    )
    fallback_user_prompt = (
        "Transform vacancy_blocks.v1 into vacancy_dimensions.v1 and respond with valid JSON only. "
        "Root key allowed: vacancy_dimensions. "
        "Allowed keys inside vacancy_dimensions: work_conditions, responsibilities, required_competencies, "
        "desirable_competencies, benefits. "
        "Do not invent keys and do not embed vacancy_blocks. "
        f"Vacancy title: {opportunity.get('title', '')}. "
        f"Company: {opportunity.get('company', '')}. "
        f"Location: {opportunity.get('location', '')}. "
        f"URL: {opportunity.get('source_url', '')}. "
        f"Input vacancy_blocks.v1: {blocks_json}"
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

    if _has_any_dimensions_content(normalized):
        return normalized

    raise VacancyDimensionsExtractionError(
        "Step 3 LLM response produced empty vacancy_dimensions; extraction aborted."
    )
