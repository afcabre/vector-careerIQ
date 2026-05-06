from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_EVIDENCE_ANALYSIS = "vacancy_evidence_analysis.v1"
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
DISCARD_REASON_SCORE_BELOW_REVIEW_THRESHOLD = "score_below_review_threshold"
DISCARD_REASON_DUPLICATE_OF_BETTER_MATCH = "duplicate_of_better_match"
DISCARD_REASON_REDUNDANT_SAME_FRAGMENT = "redundant_same_fragment"
DISCARD_REASONS = {
    DISCARD_REASON_SCORE_BELOW_REVIEW_THRESHOLD,
    DISCARD_REASON_DUPLICATE_OF_BETTER_MATCH,
    DISCARD_REASON_REDUNDANT_SAME_FRAGMENT,
}


class EvidenceAnalysisThresholds(TypedDict):
    strong_min: float
    useful_min: float
    review_min: float


class ConsolidatedEvidenceMatch(TypedDict):
    source_ref: str
    snippet: str
    best_score: float
    query_texts: list[str]
    query_indexes: list[int]
    section: str
    block_type: str
    block_title: str
    raw_match_count: int


class DiscardedEvidenceMatch(ConsolidatedEvidenceMatch):
    discard_reason: str


class EvidenceAnalysisItem(TypedDict):
    item_id: str
    item_index: int
    group_code: str
    raw_text: str
    item_status: str
    best_score: float
    raw_match_count: int
    accepted_match_count: int
    discarded_match_count: int
    distinct_query_hits: int
    best_evidence: list[ConsolidatedEvidenceMatch]
    accepted_matches: list[ConsolidatedEvidenceMatch]
    discarded_matches: list[DiscardedEvidenceMatch]


class VacancyEvidenceAnalysisPayload(TypedDict):
    responsibilities: list[EvidenceAnalysisItem]
    required_criteria: list[EvidenceAnalysisItem]
    desirable_criteria: list[EvidenceAnalysisItem]
    benefits: list[EvidenceAnalysisItem]
    about_the_company: list[EvidenceAnalysisItem]
    work_conditions: list[EvidenceAnalysisItem]


class VacancyEvidenceAnalysisContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    thresholds: EvidenceAnalysisThresholds
    analysis: VacancyEvidenceAnalysisPayload


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


def _normalize_query_texts(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _clean_text(value, max_chars=280)
        if not normalized:
            continue
        signature = normalized.casefold()
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _normalize_query_indexes(raw: Any) -> list[int]:
    if not isinstance(raw, list):
        return []
    items: list[int] = []
    seen: set[int] = set()
    for value in raw:
        if not isinstance(value, int) or value < 0:
            continue
        if value in seen:
            continue
        seen.add(value)
        items.append(value)
    return sorted(items)


def _empty_consolidated_match() -> ConsolidatedEvidenceMatch:
    return {
        "source_ref": "",
        "snippet": "",
        "best_score": 0.0,
        "query_texts": [],
        "query_indexes": [],
        "section": "",
        "block_type": "",
        "block_title": "",
        "raw_match_count": 0,
    }


def _normalize_consolidated_match(raw: Any) -> ConsolidatedEvidenceMatch | None:
    if not isinstance(raw, dict):
        return None
    normalized = _empty_consolidated_match()
    normalized["source_ref"] = _clean_text(raw.get("source_ref"), max_chars=120)
    normalized["snippet"] = _clean_text(raw.get("snippet"), max_chars=500)
    normalized["best_score"] = _clean_score(raw.get("best_score", 0.0))
    normalized["query_texts"] = _normalize_query_texts(raw.get("query_texts"))
    normalized["query_indexes"] = _normalize_query_indexes(raw.get("query_indexes"))
    normalized["section"] = _clean_text(raw.get("section"), max_chars=120)
    normalized["block_type"] = _clean_text(raw.get("block_type"), max_chars=80)
    normalized["block_title"] = _clean_text(raw.get("block_title"), max_chars=160)
    raw_match_count = raw.get("raw_match_count")
    normalized["raw_match_count"] = (
        int(raw_match_count) if isinstance(raw_match_count, int) and raw_match_count >= 0 else 0
    )
    if not normalized["snippet"]:
        return None
    return normalized


def _normalize_consolidated_match_list(raw: Any) -> list[ConsolidatedEvidenceMatch]:
    if not isinstance(raw, list):
        return []
    items: list[ConsolidatedEvidenceMatch] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_consolidated_match(value)
        if not normalized:
            continue
        signature = "|".join(
            [
                normalized["source_ref"].casefold(),
                normalized["snippet"].casefold(),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _normalize_discarded_match(raw: Any) -> DiscardedEvidenceMatch | None:
    normalized = _normalize_consolidated_match(raw)
    if not normalized or not isinstance(raw, dict):
        return None
    discard_reason = _clean_text(raw.get("discard_reason"), max_chars=80)
    if discard_reason not in DISCARD_REASONS:
        discard_reason = DISCARD_REASON_SCORE_BELOW_REVIEW_THRESHOLD
    return {
        **normalized,
        "discard_reason": discard_reason,
    }


def _normalize_discarded_match_list(raw: Any) -> list[DiscardedEvidenceMatch]:
    if not isinstance(raw, list):
        return []
    items: list[DiscardedEvidenceMatch] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_discarded_match(value)
        if not normalized:
            continue
        signature = "|".join(
            [
                normalized["source_ref"].casefold(),
                normalized["snippet"].casefold(),
                normalized["discard_reason"].casefold(),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _empty_analysis_item() -> EvidenceAnalysisItem:
    return {
        "item_id": "",
        "item_index": 0,
        "group_code": "",
        "raw_text": "",
        "item_status": ITEM_STATUS_NO_EVIDENCE,
        "best_score": 0.0,
        "raw_match_count": 0,
        "accepted_match_count": 0,
        "discarded_match_count": 0,
        "distinct_query_hits": 0,
        "best_evidence": [],
        "accepted_matches": [],
        "discarded_matches": [],
    }


def _normalize_analysis_item(raw: Any) -> EvidenceAnalysisItem | None:
    if not isinstance(raw, dict):
        return None
    normalized = _empty_analysis_item()
    normalized["item_id"] = _clean_text(raw.get("item_id"), max_chars=64)
    item_index = raw.get("item_index")
    normalized["item_index"] = int(item_index) if isinstance(item_index, int) and item_index >= 0 else 0
    normalized["group_code"] = _clean_text(raw.get("group_code"), max_chars=32)
    normalized["raw_text"] = _clean_text(raw.get("raw_text"), max_chars=500)
    item_status = _clean_text(raw.get("item_status"), max_chars=32)
    normalized["item_status"] = item_status if item_status in ITEM_STATUSES else ITEM_STATUS_NO_EVIDENCE
    normalized["best_score"] = _clean_score(raw.get("best_score", 0.0))
    for field_name in ("raw_match_count", "accepted_match_count", "discarded_match_count", "distinct_query_hits"):
        value = raw.get(field_name)
        normalized[field_name] = int(value) if isinstance(value, int) and value >= 0 else 0
    normalized["best_evidence"] = _normalize_consolidated_match_list(raw.get("best_evidence"))
    normalized["accepted_matches"] = _normalize_consolidated_match_list(raw.get("accepted_matches"))
    normalized["discarded_matches"] = _normalize_discarded_match_list(raw.get("discarded_matches"))
    if not normalized["raw_text"]:
        return None
    return normalized


def _normalize_analysis_list(raw: Any) -> list[EvidenceAnalysisItem]:
    if not isinstance(raw, list):
        return []
    items: list[EvidenceAnalysisItem] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_analysis_item(value)
        if not normalized:
            continue
        signature = "|".join(
            [
                normalized["item_id"].casefold(),
                str(normalized["item_index"]),
                normalized["group_code"].casefold(),
                normalized["raw_text"].casefold(),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def empty_vacancy_evidence_analysis_contract() -> VacancyEvidenceAnalysisContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_EVIDENCE_ANALYSIS,
        "vacancy_id": "",
        "generated_at": "",
        "thresholds": {
            "strong_min": 0.0,
            "useful_min": 0.0,
            "review_min": 0.0,
        },
        "analysis": {
            "responsibilities": [],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": [],
        },
    }


def normalize_vacancy_evidence_analysis_contract(raw: Any) -> VacancyEvidenceAnalysisContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_evidence_analysis_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)

    thresholds = source.get("thresholds") if isinstance(source.get("thresholds"), dict) else {}
    normalized["thresholds"] = {
        "strong_min": _clean_score(thresholds.get("strong_min", 0.0)),
        "useful_min": _clean_score(thresholds.get("useful_min", 0.0)),
        "review_min": _clean_score(thresholds.get("review_min", 0.0)),
    }

    payload = source.get("analysis")
    payload_source = payload if isinstance(payload, dict) else {}
    raw_work_conditions = payload_source.get("work_conditions")
    if isinstance(raw_work_conditions, dict):
        work_conditions = []
        for key in ("salary", "modality", "location", "contract_type", "other_conditions"):
            value = raw_work_conditions.get(key)
            if isinstance(value, list):
                work_conditions.extend(value)
    else:
        work_conditions = raw_work_conditions
    normalized["analysis"] = {
        "responsibilities": _normalize_analysis_list(payload_source.get("responsibilities")),
        "required_criteria": _normalize_analysis_list(payload_source.get("required_criteria")),
        "desirable_criteria": _normalize_analysis_list(payload_source.get("desirable_criteria")),
        "benefits": _normalize_analysis_list(payload_source.get("benefits")),
        "about_the_company": _normalize_analysis_list(payload_source.get("about_the_company")),
        "work_conditions": _normalize_analysis_list(work_conditions),
    }
    return normalized


def is_vacancy_evidence_analysis_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return str(raw.get("contract_version", "")).strip() == CONTRACT_VERSION_VACANCY_EVIDENCE_ANALYSIS
