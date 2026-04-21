from __future__ import annotations

import json
from typing import Any, TypedDict

from app.core.settings import Settings, get_settings


DEFAULT_VACANCY_V2_LLM_TEMPERATURE = 0.1
MIN_VACANCY_V2_LLM_TEMPERATURE = 0.0
MAX_VACANCY_V2_LLM_TEMPERATURE = 1.0


class VacancyV2StepRuntimeConfig(TypedDict):
    llm_temperature: float


class VacancyV2RuntimeConfig(TypedDict):
    step2: VacancyV2StepRuntimeConfig
    step3: VacancyV2StepRuntimeConfig


def _default_step_runtime_config() -> VacancyV2StepRuntimeConfig:
    return VacancyV2StepRuntimeConfig(
        llm_temperature=DEFAULT_VACANCY_V2_LLM_TEMPERATURE,
    )


def default_vacancy_v2_runtime_config() -> VacancyV2RuntimeConfig:
    return VacancyV2RuntimeConfig(
        step2=_default_step_runtime_config(),
        step3=_default_step_runtime_config(),
    )


def _normalize_temperature(raw_value: Any) -> float:
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_VACANCY_V2_LLM_TEMPERATURE
    if value < MIN_VACANCY_V2_LLM_TEMPERATURE:
        return MIN_VACANCY_V2_LLM_TEMPERATURE
    if value > MAX_VACANCY_V2_LLM_TEMPERATURE:
        return MAX_VACANCY_V2_LLM_TEMPERATURE
    return value


def normalize_vacancy_v2_runtime_config(raw: Any) -> VacancyV2RuntimeConfig:
    normalized = default_vacancy_v2_runtime_config()
    if not isinstance(raw, dict):
        return normalized

    for step_key in ("step2", "step3"):
        step_payload = raw.get(step_key)
        if not isinstance(step_payload, dict):
            continue
        normalized[step_key]["llm_temperature"] = _normalize_temperature(
            step_payload.get("llm_temperature")
        )
    return normalized


def _parse_raw_config(raw_text: str) -> dict[str, Any] | None:
    text = str(raw_text).strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def get_vacancy_v2_runtime_config(settings: Settings | None = None) -> VacancyV2RuntimeConfig:
    resolved_settings = settings or get_settings()
    raw_json = str(
        getattr(
            resolved_settings,
            "vacancy_v2_runtime_config_json",
            "",
        )
    ).strip()
    raw = _parse_raw_config(raw_json)
    return normalize_vacancy_v2_runtime_config(raw)
