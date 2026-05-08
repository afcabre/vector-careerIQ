from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.vacancy_alignment_summary_v2_contract import (
    CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY_V2,
    VacancyAlignmentSummaryV2Contract,
    empty_vacancy_alignment_summary_v2_contract,
    normalize_vacancy_alignment_summary_v2_contract,
)
from app.services.vacancy_evidence_adjudication_contract import (
    ALIGNMENT_STATUS_CONFLICT,
    ALIGNMENT_STATUS_DIRECT,
    ALIGNMENT_STATUS_INDIRECT,
    ALIGNMENT_STATUS_NOT_APPLICABLE,
    ALIGNMENT_STATUS_NOT_EVIDENCED,
    ALIGNMENT_STATUS_PARTIAL,
    EVIDENCE_STRENGTH_HIGH,
    EVIDENCE_STRENGTH_MEDIUM,
    GROUP_DESIRABLE_CRITERIA,
    PRIORITY_CONTEXTUAL,
    PRIORITY_CRITICAL,
    PRIORITY_DESIRABLE,
    VacancyEvidenceAdjudicationContract,
    is_vacancy_evidence_adjudication_contract,
    normalize_vacancy_evidence_adjudication_contract,
)


class VacancyAlignmentSummaryV2BuildError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _empty_counts() -> dict[str, int]:
    return {
        "total_items": 0,
        "direct_count": 0,
        "partial_count": 0,
        "indirect_count": 0,
        "not_evidenced_count": 0,
        "conflict_count": 0,
        "not_applicable_count": 0,
    }


def _add_status(counts: dict[str, int], alignment_status: str) -> None:
    counts["total_items"] += 1
    if alignment_status == ALIGNMENT_STATUS_DIRECT:
        counts["direct_count"] += 1
    elif alignment_status == ALIGNMENT_STATUS_PARTIAL:
        counts["partial_count"] += 1
    elif alignment_status == ALIGNMENT_STATUS_INDIRECT:
        counts["indirect_count"] += 1
    elif alignment_status == ALIGNMENT_STATUS_NOT_EVIDENCED:
        counts["not_evidenced_count"] += 1
    elif alignment_status == ALIGNMENT_STATUS_CONFLICT:
        counts["conflict_count"] += 1
    else:
        counts["not_applicable_count"] += 1


def _has_relevant_items(contract: VacancyEvidenceAdjudicationContract) -> bool:
    return any(
        item["group"] in {"required_criteria", "responsibilities", "desirable_criteria", "work_conditions"}
        for item in contract["items"]
    )


def _impact_from_priority(priority: str) -> str:
    if priority == PRIORITY_CRITICAL:
        return "high"
    if priority == PRIORITY_DESIRABLE:
        return "low"
    return "medium"


def _strength_candidate(item: dict[str, Any]) -> bool:
    return item["alignment_status"] == ALIGNMENT_STATUS_DIRECT and item["evidence_strength"] in {
        EVIDENCE_STRENGTH_HIGH,
        EVIDENCE_STRENGTH_MEDIUM,
    }


def _gap_payload(item: dict[str, Any]) -> dict[str, str] | None:
    raw_text = item["raw_text"]
    proof_summary = item["proof_summary"] or raw_text
    priority = item["priority"]
    if item["alignment_status"] == ALIGNMENT_STATUS_NOT_EVIDENCED:
        if priority == PRIORITY_DESIRABLE or item["group"] == GROUP_DESIRABLE_CRITERIA:
            return {
                "item_id": item["item_id"],
                "raw_text": raw_text,
                "gap_type": "desirable_not_evidenced",
                "impact": "low",
                "explanation": proof_summary,
            }
        return {
            "item_id": item["item_id"],
            "raw_text": raw_text,
            "gap_type": "not_evidenced_in_cv",
            "impact": _impact_from_priority(priority),
            "explanation": proof_summary,
        }
    if item["alignment_status"] == ALIGNMENT_STATUS_PARTIAL:
        return {
            "item_id": item["item_id"],
            "raw_text": raw_text,
            "gap_type": "partial_coverage",
            "impact": _impact_from_priority(priority),
            "explanation": proof_summary,
        }
    if item["alignment_status"] == ALIGNMENT_STATUS_INDIRECT:
        return {
            "item_id": item["item_id"],
            "raw_text": raw_text,
            "gap_type": "unclear_requirement",
            "impact": _impact_from_priority(priority),
            "explanation": proof_summary,
        }
    if item["alignment_status"] == ALIGNMENT_STATUS_CONFLICT:
        return {
            "item_id": item["item_id"],
            "raw_text": raw_text,
            "gap_type": "real_gap",
            "impact": _impact_from_priority(priority),
            "explanation": proof_summary,
        }
    return None


def _review_payload(item: dict[str, Any]) -> dict[str, str] | None:
    if item["alignment_status"] == ALIGNMENT_STATUS_INDIRECT:
        return {
            "item_id": item["item_id"],
            "raw_text": item["raw_text"],
            "reason": item["proof_summary"] or "La evidencia es transferible, pero no equivalente.",
        }
    if item["alignment_status"] == ALIGNMENT_STATUS_PARTIAL and item["priority"] in {
        PRIORITY_CRITICAL,
        PRIORITY_CONTEXTUAL,
    }:
        return {
            "item_id": item["item_id"],
            "raw_text": item["raw_text"],
            "reason": item["proof_summary"] or "La cobertura es parcial y requiere revision adicional.",
        }
    return None


def _risk_payload(item: dict[str, Any]) -> dict[str, str] | None:
    risk = str(item.get("candidate_risk", "")).strip()
    if risk not in {"medium", "high"}:
        return None
    return {
        "item_id": item["item_id"],
        "risk": item["proof_summary"] or item["raw_text"],
        "severity": risk,
    }


def build_vacancy_alignment_summary_v2(
    *,
    opportunity: dict[str, Any],
    vacancy_evidence_adjudication_artifact: dict[str, Any],
) -> VacancyAlignmentSummaryV2Contract:
    if not isinstance(vacancy_evidence_adjudication_artifact, dict) or not is_vacancy_evidence_adjudication_contract(
        vacancy_evidence_adjudication_artifact
    ):
        raise VacancyAlignmentSummaryV2BuildError(
            "Step 7 v2 requires a valid vacancy_evidence_adjudication.v1 artifact."
        )

    normalized_adjudication = normalize_vacancy_evidence_adjudication_contract(
        vacancy_evidence_adjudication_artifact
    )
    if not _has_relevant_items(normalized_adjudication):
        raise VacancyAlignmentSummaryV2BuildError(
            "Step 7 v2 requires at least one adjudicated item in required_criteria, responsibilities, desirable_criteria or work_conditions."
        )

    overall = _empty_counts()
    groups = {
        "required_criteria": _empty_counts(),
        "responsibilities": _empty_counts(),
        "desirable_criteria": _empty_counts(),
        "work_conditions": _empty_counts(),
    }
    strengths: list[dict[str, str]] = []
    gaps: list[dict[str, str]] = []
    review_items: list[dict[str, str]] = []
    risks: list[dict[str, str]] = []

    for item in normalized_adjudication["items"]:
        if item["group"] not in groups:
            continue
        _add_status(overall, item["alignment_status"])
        _add_status(groups[item["group"]], item["alignment_status"])

        if _strength_candidate(item):
            strengths.append(
                {
                    "item_id": item["item_id"],
                    "raw_text": item["raw_text"],
                    "alignment_status": item["alignment_status"],
                    "evidence_strength": item["evidence_strength"],
                    "proof_summary": item["proof_summary"],
                }
            )

        gap = _gap_payload(item)
        if gap:
            gaps.append(gap)

        review_item = _review_payload(item)
        if review_item:
            review_items.append(review_item)

        risk = _risk_payload(item)
        if risk:
            risks.append(risk)

    artifact = empty_vacancy_alignment_summary_v2_contract()
    artifact["vacancy_id"] = normalized_adjudication["vacancy_id"] or str(
        opportunity.get("opportunity_id", "")
    ).strip()
    artifact["generated_at"] = _now_iso()
    artifact["source_artifact_version"] = "vacancy_evidence_adjudication.v1"
    artifact["summary"] = {
        "overall": overall,
        "groups": groups,
        "strengths": strengths,
        "gaps": gaps,
        "review_items": review_items,
        "risks": risks,
    }
    normalized = normalize_vacancy_alignment_summary_v2_contract(artifact)
    normalized["contract_version"] = CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY_V2
    return normalized
