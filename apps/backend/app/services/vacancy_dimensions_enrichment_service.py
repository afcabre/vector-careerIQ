from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.vacancy_dimensions_contract import is_vacancy_dimensions_contract, normalize_vacancy_dimensions_contract
from app.services.vacancy_dimensions_enriched_contract import VacancyDimensionsEnrichedContract


class VacancyDimensionsEnrichmentError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _has_any_enriched_items(contract: VacancyDimensionsEnrichedContract) -> bool:
    payload = contract["vacancy_dimensions"]
    if payload["responsibilities"]:
        return True
    if payload["required_criteria"]:
        return True
    if payload["desirable_criteria"]:
        return True
    if payload["benefits"]:
        return True
    if payload["about_the_company"]:
        return True
    return bool(payload["work_conditions"]["other_conditions"])


def enrich_vacancy_dimensions_artifact(
    opportunity: dict[str, Any],
    vacancy_dimensions_artifact: dict[str, Any],
) -> VacancyDimensionsEnrichedContract:
    if not isinstance(vacancy_dimensions_artifact, dict) or not is_vacancy_dimensions_contract(vacancy_dimensions_artifact):
        raise VacancyDimensionsEnrichmentError(
            "Step 3.9 requires a valid vacancy_dimensions.v2 artifact."
        )

    normalized = normalize_vacancy_dimensions_contract(vacancy_dimensions_artifact)
    vacancy_id = normalized["vacancy_id"] or str(opportunity.get("opportunity_id", "")).strip()
    generated_at = _now_iso()

    contract: VacancyDimensionsEnrichedContract = {
        "contract_version": "vacancy_dimensions_enriched.v1",
        "vacancy_id": vacancy_id,
        "generated_at": generated_at,
        "vacancy_dimensions": {
            "work_conditions": {
                "salary": normalized["vacancy_dimensions"]["work_conditions"]["salary"],
                "modality": normalized["vacancy_dimensions"]["work_conditions"]["modality"],
                "location": normalized["vacancy_dimensions"]["work_conditions"]["location"],
                "contract_type": normalized["vacancy_dimensions"]["work_conditions"]["contract_type"],
                "other_conditions": [],
            },
            "responsibilities": [],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
        },
    }

    from app.services.vacancy_dimensions_contract import enrich_vacancy_dimensions_items

    enriched = enrich_vacancy_dimensions_items(normalized)
    contract["vacancy_dimensions"] = enriched["vacancy_dimensions"]

    if _has_any_enriched_items(contract):
        return contract

    raise VacancyDimensionsEnrichmentError(
        "Step 3.9 produced no enrichable atomic items; enrichment aborted."
    )
