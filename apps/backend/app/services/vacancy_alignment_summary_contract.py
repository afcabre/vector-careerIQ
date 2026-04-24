from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY = "vacancy_alignment_summary.v1"
PRIMARY_ALIGNMENT_GROUPS = (
    "responsibilities",
    "required_criteria",
    "desirable_criteria",
)
ITEM_STATUS_STRONG_EVIDENCE = "strong_evidence"
ITEM_STATUS_USEFUL_EVIDENCE = "useful_evidence"
ITEM_STATUS_REVIEW = "review"
ITEM_STATUS_NO_EVIDENCE = "no_evidence"
ITEM_STATUSES = {
    ITEM_STATUS_STRONG_EVIDENCE,
    ITEM_STATUS_USEFUL_EVIDENCE,
    ITEM_STATUS_REVIEW,
    ITEM_STATUS_NO_EVIDENCE,
}


class AlignmentSummaryThresholds(TypedDict):
    strong_min: float
    useful_min: float
    review_min: float


class AlignmentStatusCounts(TypedDict):
    total_items: int
    strong_evidence_count: int
    useful_evidence_count: int
    review_count: int
    no_evidence_count: int


class AlignmentSummaryItemRef(TypedDict):
    group: str
    item_id: str
    item_index: int
    raw_text: str
    item_status: str
    best_score: float


class AlignmentSummaryGroups(TypedDict):
    responsibilities: AlignmentStatusCounts
    required_criteria: AlignmentStatusCounts
    desirable_criteria: AlignmentStatusCounts


class AlignmentSummaryPayload(TypedDict):
    overall: AlignmentStatusCounts
    groups: AlignmentSummaryGroups
    strengths: list[AlignmentSummaryItemRef]
    gaps: list[AlignmentSummaryItemRef]
    review_items: list[AlignmentSummaryItemRef]


class VacancyAlignmentSummaryContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    source_artifact_version: str
    thresholds: AlignmentSummaryThresholds
    summary: AlignmentSummaryPayload


def _clean_text(value: Any, *, max_chars: int = 800) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _clean_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def _clean_non_negative_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number >= 0 else 0


def _empty_status_counts() -> AlignmentStatusCounts:
    return {
        "total_items": 0,
        "strong_evidence_count": 0,
        "useful_evidence_count": 0,
        "review_count": 0,
        "no_evidence_count": 0,
    }


def _normalize_status_counts(raw: Any) -> AlignmentStatusCounts:
    if not isinstance(raw, dict):
        return _empty_status_counts()
    return {
        "total_items": _clean_non_negative_int(raw.get("total_items")),
        "strong_evidence_count": _clean_non_negative_int(raw.get("strong_evidence_count")),
        "useful_evidence_count": _clean_non_negative_int(raw.get("useful_evidence_count")),
        "review_count": _clean_non_negative_int(raw.get("review_count")),
        "no_evidence_count": _clean_non_negative_int(raw.get("no_evidence_count")),
    }


def _empty_item_ref() -> AlignmentSummaryItemRef:
    return {
        "group": "",
        "item_id": "",
        "item_index": 0,
        "raw_text": "",
        "item_status": ITEM_STATUS_NO_EVIDENCE,
        "best_score": 0.0,
    }


def _normalize_item_ref(raw: Any) -> AlignmentSummaryItemRef | None:
    if not isinstance(raw, dict):
        return None
    normalized = _empty_item_ref()
    group = _clean_text(raw.get("group"), max_chars=48)
    if group not in PRIMARY_ALIGNMENT_GROUPS:
        return None
    normalized["group"] = group
    normalized["item_id"] = _clean_text(raw.get("item_id"), max_chars=64)
    normalized["item_index"] = _clean_non_negative_int(raw.get("item_index"))
    normalized["raw_text"] = _clean_text(raw.get("raw_text"), max_chars=500)
    item_status = _clean_text(raw.get("item_status"), max_chars=32)
    normalized["item_status"] = item_status if item_status in ITEM_STATUSES else ITEM_STATUS_NO_EVIDENCE
    normalized["best_score"] = _clean_score(raw.get("best_score", 0.0))
    if not normalized["raw_text"]:
        return None
    return normalized


def _normalize_item_ref_list(raw: Any) -> list[AlignmentSummaryItemRef]:
    if not isinstance(raw, list):
        return []
    items: list[AlignmentSummaryItemRef] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_item_ref(value)
        if not normalized:
            continue
        signature = "|".join(
            [
                normalized["group"],
                normalized["item_id"].casefold(),
                str(normalized["item_index"]),
                normalized["raw_text"].casefold(),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def empty_vacancy_alignment_summary_contract() -> VacancyAlignmentSummaryContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY,
        "vacancy_id": "",
        "generated_at": "",
        "source_artifact_version": "",
        "thresholds": {
            "strong_min": 0.0,
            "useful_min": 0.0,
            "review_min": 0.0,
        },
        "summary": {
            "overall": _empty_status_counts(),
            "groups": {
                "responsibilities": _empty_status_counts(),
                "required_criteria": _empty_status_counts(),
                "desirable_criteria": _empty_status_counts(),
            },
            "strengths": [],
            "gaps": [],
            "review_items": [],
        },
    }


def normalize_vacancy_alignment_summary_contract(raw: Any) -> VacancyAlignmentSummaryContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_alignment_summary_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)
    normalized["source_artifact_version"] = _clean_text(
        source.get("source_artifact_version"),
        max_chars=64,
    )
    thresholds = source.get("thresholds") if isinstance(source.get("thresholds"), dict) else {}
    normalized["thresholds"] = {
        "strong_min": _clean_score(thresholds.get("strong_min", 0.0)),
        "useful_min": _clean_score(thresholds.get("useful_min", 0.0)),
        "review_min": _clean_score(thresholds.get("review_min", 0.0)),
    }

    summary = source.get("summary") if isinstance(source.get("summary"), dict) else {}
    groups = summary.get("groups") if isinstance(summary.get("groups"), dict) else {}
    normalized["summary"] = {
        "overall": _normalize_status_counts(summary.get("overall")),
        "groups": {
            "responsibilities": _normalize_status_counts(groups.get("responsibilities")),
            "required_criteria": _normalize_status_counts(groups.get("required_criteria")),
            "desirable_criteria": _normalize_status_counts(groups.get("desirable_criteria")),
        },
        "strengths": _normalize_item_ref_list(summary.get("strengths")),
        "gaps": _normalize_item_ref_list(summary.get("gaps")),
        "review_items": _normalize_item_ref_list(summary.get("review_items")),
    }
    return normalized


def is_vacancy_alignment_summary_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return (
        str(raw.get("contract_version", "")).strip()
        == CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY
    )
