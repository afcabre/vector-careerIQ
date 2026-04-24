from __future__ import annotations

from typing import Any, TypedDict

from app.services.vacancy_dimensions_contract import (
    EnrichedVacancyDimensionsPayload,
    enrich_vacancy_dimensions_items,
)


CONTRACT_VERSION_VACANCY_DIMENSIONS_ENRICHED = "vacancy_dimensions_enriched.v1"


class VacancyDimensionsEnrichedContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    vacancy_dimensions: EnrichedVacancyDimensionsPayload


def empty_vacancy_dimensions_enriched_contract() -> VacancyDimensionsEnrichedContract:
    base = enrich_vacancy_dimensions_items({})
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_DIMENSIONS_ENRICHED,
        "vacancy_id": base["vacancy_id"],
        "generated_at": base["generated_at"],
        "vacancy_dimensions": base["vacancy_dimensions"],
    }


def normalize_vacancy_dimensions_enriched_contract(raw: Any) -> VacancyDimensionsEnrichedContract:
    base = enrich_vacancy_dimensions_items(raw)
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_DIMENSIONS_ENRICHED,
        "vacancy_id": base["vacancy_id"],
        "generated_at": base["generated_at"],
        "vacancy_dimensions": base["vacancy_dimensions"],
    }


def is_vacancy_dimensions_enriched_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return str(raw.get("contract_version", "")).strip() == CONTRACT_VERSION_VACANCY_DIMENSIONS_ENRICHED
