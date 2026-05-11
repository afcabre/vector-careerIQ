from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.vacancy_evidence_adjudication_contract import (
    ALIGNMENT_STATUS_CONFLICT,
    ALIGNMENT_STATUS_DIRECT,
    ALIGNMENT_STATUS_INDIRECT,
    ALIGNMENT_STATUS_NOT_APPLICABLE,
    ALIGNMENT_STATUS_NOT_EVIDENCED,
    ALIGNMENT_STATUS_PARTIAL,
    GROUP_ABOUT_THE_COMPANY,
    GROUP_BENEFITS,
    GROUP_DESIRABLE_CRITERIA,
    GROUP_REQUIRED_CRITERIA,
    GROUP_RESPONSIBILITIES,
    GROUP_WORK_CONDITIONS,
    VacancyEvidenceAdjudicationContract,
    is_vacancy_evidence_adjudication_contract,
    normalize_vacancy_evidence_adjudication_contract,
)
from app.services.vacancy_fit_presentation_contract import (
    CONTRACT_VERSION_VACANCY_FIT_PRESENTATION,
    VacancyFitPresentationContract,
    empty_vacancy_fit_presentation_contract,
    normalize_vacancy_fit_presentation_contract,
)


class VacancyFitPresentationBuildError(RuntimeError):
    pass


MAIN_MATRIX_GROUPS = (
    GROUP_REQUIRED_CRITERIA,
    GROUP_RESPONSIBILITIES,
    GROUP_DESIRABLE_CRITERIA,
)
EXCLUDED_PRESENTATION_GROUPS = (
    GROUP_WORK_CONDITIONS,
    GROUP_BENEFITS,
    GROUP_ABOUT_THE_COMPANY,
)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _has_relevant_items(contract: VacancyEvidenceAdjudicationContract) -> bool:
    return any(item["group"] in MAIN_MATRIX_GROUPS for item in contract["items"])


def _type_label(group: str) -> str:
    if group == GROUP_REQUIRED_CRITERIA:
        return "Obligatorio"
    if group == GROUP_RESPONSIBILITIES:
        return "Responsabilidad"
    return "Deseable"


def _state_from_item(item: dict[str, Any]) -> str:
    if item["alignment_status"] == ALIGNMENT_STATUS_DIRECT:
        return "🟢 Cumple"
    if item["alignment_status"] in {ALIGNMENT_STATUS_INDIRECT, ALIGNMENT_STATUS_PARTIAL}:
        return "🟡 Parcial"
    if item["alignment_status"] == ALIGNMENT_STATUS_CONFLICT:
        return "🔴 En conflicto"
    if item["alignment_status"] == ALIGNMENT_STATUS_NOT_EVIDENCED:
        if item["group"] == GROUP_DESIRABLE_CRITERIA:
            return "🔵 Deseable no evidenciado"
        return "⚪ Sin informacion"
    if item["alignment_status"] == ALIGNMENT_STATUS_NOT_APPLICABLE:
        return "⚪ Sin informacion"
    return "🟡 Parcial"


def _default_why(item: dict[str, Any]) -> str:
    if item["proof_summary"]:
        return item["proof_summary"]
    if item["alignment_status"] == ALIGNMENT_STATUS_DIRECT:
        return "La evidencia disponible soporta claramente el criterio."
    if item["alignment_status"] == ALIGNMENT_STATUS_PARTIAL:
        return "La evidencia disponible cubre solo una parte del criterio."
    if item["alignment_status"] == ALIGNMENT_STATUS_INDIRECT:
        return "La evidencia disponible es transferible, pero no equivalente."
    if item["alignment_status"] == ALIGNMENT_STATUS_CONFLICT:
        return "La evidencia disponible entra en conflicto con el criterio."
    if item["alignment_status"] == ALIGNMENT_STATUS_NOT_APPLICABLE:
        return "El criterio no requiere comparacion directa contra el CV."
    return "No hay evidencia suficiente en los snippets disponibles."


def _row_from_item(item: dict[str, Any]) -> dict[str, Any]:
    evidence = list(item.get("best_supporting_evidence", []))
    return {
        "item_id": item["item_id"],
        "item_index": int(item["item_index"]),
        "group": item["group"],
        "group_code": item["group_code"],
        "type_label": _type_label(item["group"]),
        "criterion": item["raw_text"],
        "state": _state_from_item(item),
        "why": _default_why(item),
        "evidence_count": len(evidence),
        "evidence": evidence,
        "limitations": list(item.get("limitations", [])),
        "confidence": item["confidence"],
        "candidate_risk": item["candidate_risk"],
    }


def build_vacancy_fit_presentation(
    *,
    opportunity: dict[str, Any],
    vacancy_evidence_adjudication_artifact: dict[str, Any],
) -> VacancyFitPresentationContract:
    if not isinstance(vacancy_evidence_adjudication_artifact, dict) or not is_vacancy_evidence_adjudication_contract(
        vacancy_evidence_adjudication_artifact
    ):
        raise VacancyFitPresentationBuildError(
            "P1 requires a valid vacancy_evidence_adjudication.v1 artifact."
        )

    normalized_adjudication = normalize_vacancy_evidence_adjudication_contract(
        vacancy_evidence_adjudication_artifact
    )
    if not _has_relevant_items(normalized_adjudication):
        raise VacancyFitPresentationBuildError(
            "P1 requires at least one adjudicated item in required_criteria, responsibilities or desirable_criteria."
        )

    warnings: list[str] = []
    groups = {
        "required_criteria": [],
        "responsibilities": [],
        "desirable_criteria": [],
    }
    excluded_group_warnings = {
        GROUP_WORK_CONDITIONS: "work_conditions_excluded_from_main_matrix",
        GROUP_BENEFITS: "benefits_excluded_from_main_matrix",
        GROUP_ABOUT_THE_COMPANY: "about_the_company_excluded_from_main_matrix",
    }

    for item in normalized_adjudication["items"]:
        if item["group"] in MAIN_MATRIX_GROUPS:
            groups[item["group"]].append(_row_from_item(item))
            if item["alignment_status"] == ALIGNMENT_STATUS_NOT_APPLICABLE:
                warnings.append("not_applicable_item_rendered_as_no_information")
            continue
        warning = excluded_group_warnings.get(item["group"])
        if warning and warning not in warnings:
            warnings.append(warning)

    artifact = empty_vacancy_fit_presentation_contract()
    artifact["vacancy_id"] = normalized_adjudication["vacancy_id"] or str(
        opportunity.get("opportunity_id", "")
    ).strip()
    artifact["generated_at"] = _now_iso()
    artifact["groups"] = groups
    artifact["warnings"] = warnings
    normalized = normalize_vacancy_fit_presentation_contract(artifact)
    normalized["contract_version"] = CONTRACT_VERSION_VACANCY_FIT_PRESENTATION
    return normalized
