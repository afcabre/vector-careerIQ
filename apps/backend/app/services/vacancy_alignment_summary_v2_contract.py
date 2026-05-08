from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY_V2 = "vacancy_alignment_summary.v2"
ALIGNMENT_SUMMARY_V2_GROUPS = (
    "required_criteria",
    "responsibilities",
    "desirable_criteria",
    "work_conditions",
)
ALIGNMENT_SUMMARY_V2_STATUSES = (
    "direct",
    "partial",
    "indirect",
    "not_evidenced",
    "conflict",
    "not_applicable",
)
ALIGNMENT_SUMMARY_V2_GAP_TYPES = (
    "real_gap",
    "not_evidenced_in_cv",
    "partial_coverage",
    "unclear_requirement",
    "desirable_not_evidenced",
)
ALIGNMENT_SUMMARY_V2_IMPACTS = ("high", "medium", "low")


class AlignmentSummaryV2Counts(TypedDict):
    total_items: int
    direct_count: int
    partial_count: int
    indirect_count: int
    not_evidenced_count: int
    conflict_count: int
    not_applicable_count: int


class AlignmentSummaryV2Groups(TypedDict):
    required_criteria: AlignmentSummaryV2Counts
    responsibilities: AlignmentSummaryV2Counts
    desirable_criteria: AlignmentSummaryV2Counts
    work_conditions: AlignmentSummaryV2Counts


class AlignmentSummaryV2StrengthItem(TypedDict):
    item_id: str
    raw_text: str
    alignment_status: str
    evidence_strength: str
    proof_summary: str


class AlignmentSummaryV2GapItem(TypedDict):
    item_id: str
    raw_text: str
    gap_type: str
    impact: str
    explanation: str


class AlignmentSummaryV2ReviewItem(TypedDict):
    item_id: str
    raw_text: str
    reason: str


class AlignmentSummaryV2RiskItem(TypedDict):
    item_id: str
    risk: str
    severity: str


class VacancyAlignmentSummaryV2Contract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    source_artifact_version: str
    summary: dict[str, Any]


def _clean_text(value: Any, *, max_chars: int = 800) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _clean_non_negative_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number >= 0 else 0


def _empty_counts() -> AlignmentSummaryV2Counts:
    return {
        "total_items": 0,
        "direct_count": 0,
        "partial_count": 0,
        "indirect_count": 0,
        "not_evidenced_count": 0,
        "conflict_count": 0,
        "not_applicable_count": 0,
    }


def _normalize_counts(raw: Any) -> AlignmentSummaryV2Counts:
    if not isinstance(raw, dict):
        return _empty_counts()
    return {
        "total_items": _clean_non_negative_int(raw.get("total_items")),
        "direct_count": _clean_non_negative_int(raw.get("direct_count")),
        "partial_count": _clean_non_negative_int(raw.get("partial_count")),
        "indirect_count": _clean_non_negative_int(raw.get("indirect_count")),
        "not_evidenced_count": _clean_non_negative_int(raw.get("not_evidenced_count")),
        "conflict_count": _clean_non_negative_int(raw.get("conflict_count")),
        "not_applicable_count": _clean_non_negative_int(raw.get("not_applicable_count")),
    }


def _normalize_groups(raw: Any) -> AlignmentSummaryV2Groups:
    groups = raw if isinstance(raw, dict) else {}
    return {
        "required_criteria": _normalize_counts(groups.get("required_criteria")),
        "responsibilities": _normalize_counts(groups.get("responsibilities")),
        "desirable_criteria": _normalize_counts(groups.get("desirable_criteria")),
        "work_conditions": _normalize_counts(groups.get("work_conditions")),
    }


def _normalize_strength_item(raw: Any) -> AlignmentSummaryV2StrengthItem | None:
    if not isinstance(raw, dict):
        return None
    item = {
        "item_id": _clean_text(raw.get("item_id"), max_chars=64),
        "raw_text": _clean_text(raw.get("raw_text"), max_chars=500),
        "alignment_status": _clean_text(raw.get("alignment_status"), max_chars=32),
        "evidence_strength": _clean_text(raw.get("evidence_strength"), max_chars=32),
        "proof_summary": _clean_text(raw.get("proof_summary"), max_chars=500),
    }
    if not item["item_id"] and not item["raw_text"]:
        return None
    return item


def _normalize_gap_item(raw: Any) -> AlignmentSummaryV2GapItem | None:
    if not isinstance(raw, dict):
        return None
    gap_type = _clean_text(raw.get("gap_type"), max_chars=40)
    impact = _clean_text(raw.get("impact"), max_chars=16)
    item = {
        "item_id": _clean_text(raw.get("item_id"), max_chars=64),
        "raw_text": _clean_text(raw.get("raw_text"), max_chars=500),
        "gap_type": gap_type if gap_type in ALIGNMENT_SUMMARY_V2_GAP_TYPES else "unclear_requirement",
        "impact": impact if impact in ALIGNMENT_SUMMARY_V2_IMPACTS else "low",
        "explanation": _clean_text(raw.get("explanation"), max_chars=500),
    }
    if not item["item_id"] and not item["raw_text"]:
        return None
    return item


def _normalize_review_item(raw: Any) -> AlignmentSummaryV2ReviewItem | None:
    if not isinstance(raw, dict):
        return None
    item = {
        "item_id": _clean_text(raw.get("item_id"), max_chars=64),
        "raw_text": _clean_text(raw.get("raw_text"), max_chars=500),
        "reason": _clean_text(raw.get("reason"), max_chars=400),
    }
    if not item["item_id"] and not item["raw_text"]:
        return None
    return item


def _normalize_risk_item(raw: Any) -> AlignmentSummaryV2RiskItem | None:
    if not isinstance(raw, dict):
        return None
    severity = _clean_text(raw.get("severity"), max_chars=16)
    item = {
        "item_id": _clean_text(raw.get("item_id"), max_chars=64),
        "risk": _clean_text(raw.get("risk"), max_chars=400),
        "severity": severity if severity in ALIGNMENT_SUMMARY_V2_IMPACTS else "low",
    }
    if not item["item_id"] and not item["risk"]:
        return None
    return item


def _normalize_unique_list(raw: Any, normalizer: Any) -> list[Any]:
    if not isinstance(raw, list):
        return []
    items: list[Any] = []
    seen: set[str] = set()
    for value in raw:
        normalized = normalizer(value)
        if not normalized:
            continue
        signature = "|".join(
            [
                str(normalized.get("item_id", "")).casefold(),
                str(normalized.get("raw_text", "")).casefold(),
                str(normalized.get("risk", "")).casefold(),
                str(normalized.get("reason", "")).casefold(),
                str(normalized.get("gap_type", "")).casefold(),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def empty_vacancy_alignment_summary_v2_contract() -> VacancyAlignmentSummaryV2Contract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY_V2,
        "vacancy_id": "",
        "generated_at": "",
        "source_artifact_version": "",
        "summary": {
            "overall": _empty_counts(),
            "groups": _normalize_groups({}),
            "strengths": [],
            "gaps": [],
            "review_items": [],
            "risks": [],
        },
    }


def normalize_vacancy_alignment_summary_v2_contract(raw: Any) -> VacancyAlignmentSummaryV2Contract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_alignment_summary_v2_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)
    normalized["source_artifact_version"] = _clean_text(source.get("source_artifact_version"), max_chars=64)
    summary = source.get("summary") if isinstance(source.get("summary"), dict) else {}
    normalized["summary"] = {
        "overall": _normalize_counts(summary.get("overall")),
        "groups": _normalize_groups(summary.get("groups")),
        "strengths": _normalize_unique_list(summary.get("strengths"), _normalize_strength_item),
        "gaps": _normalize_unique_list(summary.get("gaps"), _normalize_gap_item),
        "review_items": _normalize_unique_list(summary.get("review_items"), _normalize_review_item),
        "risks": _normalize_unique_list(summary.get("risks"), _normalize_risk_item),
    }
    return normalized


def is_vacancy_alignment_summary_v2_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return (
        str(raw.get("contract_version", "")).strip()
        == CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY_V2
    )
