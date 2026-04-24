from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.services.vacancy_alignment_summary_contract import (
    CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY,
    ITEM_STATUS_NO_EVIDENCE,
    ITEM_STATUS_REVIEW,
    ITEM_STATUS_STRONG_EVIDENCE,
    ITEM_STATUS_USEFUL_EVIDENCE,
    PRIMARY_ALIGNMENT_GROUPS,
    AlignmentStatusCounts,
    AlignmentSummaryItemRef,
    VacancyAlignmentSummaryContract,
    empty_vacancy_alignment_summary_contract,
    normalize_vacancy_alignment_summary_contract,
)
from app.services.vacancy_evidence_analysis_contract import (
    CONTRACT_VERSION_VACANCY_EVIDENCE_ANALYSIS,
    EvidenceAnalysisItem,
    VacancyEvidenceAnalysisContract,
    is_vacancy_evidence_analysis_contract,
    normalize_vacancy_evidence_analysis_contract,
)


class VacancyAlignmentSummaryBuildError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _empty_counts() -> AlignmentStatusCounts:
    return {
        "total_items": 0,
        "strong_evidence_count": 0,
        "useful_evidence_count": 0,
        "review_count": 0,
        "no_evidence_count": 0,
    }


def _add_item_to_counts(
    counts: AlignmentStatusCounts,
    *,
    item_status: str,
) -> None:
    counts["total_items"] += 1
    if item_status == ITEM_STATUS_STRONG_EVIDENCE:
        counts["strong_evidence_count"] += 1
    elif item_status == ITEM_STATUS_USEFUL_EVIDENCE:
        counts["useful_evidence_count"] += 1
    elif item_status == ITEM_STATUS_REVIEW:
        counts["review_count"] += 1
    else:
        counts["no_evidence_count"] += 1


def _to_item_ref(group: str, item: EvidenceAnalysisItem) -> AlignmentSummaryItemRef:
    return {
        "group": group,
        "item_id": item["item_id"],
        "item_index": item["item_index"],
        "raw_text": item["raw_text"],
        "item_status": item["item_status"],
        "best_score": item["best_score"],
    }


def _sort_item_refs(items: list[AlignmentSummaryItemRef]) -> list[AlignmentSummaryItemRef]:
    return sorted(
        items,
        key=lambda item: (-item["best_score"], item["group"], item["item_index"]),
    )


def _has_any_primary_items(contract: VacancyEvidenceAnalysisContract) -> bool:
    payload = contract["analysis"]
    return any(bool(payload[group]) for group in PRIMARY_ALIGNMENT_GROUPS)


def build_vacancy_alignment_summary(
    *,
    opportunity: dict[str, Any],
    vacancy_evidence_analysis_artifact: dict[str, Any],
) -> VacancyAlignmentSummaryContract:
    if not isinstance(vacancy_evidence_analysis_artifact, dict) or not is_vacancy_evidence_analysis_contract(
        vacancy_evidence_analysis_artifact
    ):
        raise VacancyAlignmentSummaryBuildError(
            "Step 7 requires a valid vacancy_evidence_analysis.v1 artifact."
        )

    normalized_analysis = normalize_vacancy_evidence_analysis_contract(
        vacancy_evidence_analysis_artifact
    )
    if not _has_any_primary_items(normalized_analysis):
        raise VacancyAlignmentSummaryBuildError(
            "Step 7 requires at least one analyzed item in responsibilities, required_criteria or desirable_criteria."
        )

    payload = normalized_analysis["analysis"]
    overall = _empty_counts()
    group_counts = {
        "responsibilities": _empty_counts(),
        "required_criteria": _empty_counts(),
        "desirable_criteria": _empty_counts(),
    }
    strengths: list[AlignmentSummaryItemRef] = []
    gaps: list[AlignmentSummaryItemRef] = []
    review_items: list[AlignmentSummaryItemRef] = []

    for group in PRIMARY_ALIGNMENT_GROUPS:
        for item in payload[group]:
            item_ref = _to_item_ref(group, item)
            _add_item_to_counts(overall, item_status=item["item_status"])
            _add_item_to_counts(group_counts[group], item_status=item["item_status"])
            if item["item_status"] in {ITEM_STATUS_STRONG_EVIDENCE, ITEM_STATUS_USEFUL_EVIDENCE}:
                strengths.append(item_ref)
            elif item["item_status"] == ITEM_STATUS_REVIEW:
                review_items.append(item_ref)
            elif item["item_status"] == ITEM_STATUS_NO_EVIDENCE:
                gaps.append(item_ref)

    artifact = empty_vacancy_alignment_summary_contract()
    artifact["vacancy_id"] = normalized_analysis["vacancy_id"] or str(
        opportunity.get("opportunity_id", "")
    ).strip()
    artifact["generated_at"] = _now_iso()
    artifact["source_artifact_version"] = CONTRACT_VERSION_VACANCY_EVIDENCE_ANALYSIS
    artifact["thresholds"] = normalized_analysis["thresholds"]
    artifact["summary"] = {
        "overall": overall,
        "groups": group_counts,
        "strengths": _sort_item_refs(strengths),
        "gaps": _sort_item_refs(gaps),
        "review_items": _sort_item_refs(review_items),
    }
    return normalize_vacancy_alignment_summary_contract(artifact)
