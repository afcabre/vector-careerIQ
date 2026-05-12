from __future__ import annotations

from difflib import SequenceMatcher
from datetime import UTC, datetime
from typing import Any

from app.services.ai_runtime_config_store import get_ai_runtime_config
from app.services.vacancy_evidence_analysis_contract import (
    DISCARD_REASON_DUPLICATE_OF_BETTER_MATCH,
    DISCARD_REASON_REDUNDANT_SAME_FRAGMENT,
    DISCARD_REASON_SCORE_BELOW_REVIEW_THRESHOLD,
    ITEM_STATUS_NO_EVIDENCE,
    ITEM_STATUS_REVIEW,
    ITEM_STATUS_STRONG_EVIDENCE,
    ITEM_STATUS_USEFUL_EVIDENCE,
    ConsolidatedEvidenceMatch,
    DiscardedEvidenceMatch,
    EvidenceAnalysisItem,
    VacancyEvidenceAnalysisContract,
    empty_vacancy_evidence_analysis_contract,
    normalize_vacancy_evidence_analysis_contract,
)
from app.services.vacancy_retrieval_evidence_contract import (
    RetrievalEvidenceItem,
    VacancyRetrievalEvidenceContract,
    is_vacancy_retrieval_evidence_contract,
    normalize_vacancy_retrieval_evidence_contract,
)


TOP_BEST_EVIDENCE_LIMIT = 3
SNIPPET_NEAR_DUPLICATE_THRESHOLD = 0.92
MIN_WEAK_MATCH_CRITERION_OVERLAP = 0.18


class VacancyEvidenceAnalysisBuildError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _score_thresholds() -> dict[str, float]:
    config = get_ai_runtime_config()
    strong_min = float(config.get("vacancy_retrieval_score_strong_min", 0.75) or 0.75)
    useful_min = float(config.get("vacancy_retrieval_score_useful_min", 0.45) or 0.45)
    review_min = float(config.get("vacancy_retrieval_score_review_min", 0.30) or 0.30)
    return {
        "strong_min": max(0.0, min(1.0, strong_min)),
        "useful_min": max(0.0, min(1.0, useful_min)),
        "review_min": max(0.0, min(1.0, review_min)),
    }


def _normalize_text(value: str) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in _normalize_text(value).split()
        if len(token) >= 3
    }


def _lexical_overlap(left: str, right: str) -> float:
    left_tokens = _content_tokens(left)
    right_tokens = _content_tokens(right)
    union = left_tokens | right_tokens
    if not union:
        return 0.0
    return len(left_tokens & right_tokens) / len(union)


def _are_near_duplicate_snippets(left: str, right: str) -> bool:
    left_normalized = _normalize_text(left)
    right_normalized = _normalize_text(right)
    if not left_normalized or not right_normalized:
        return False
    if left_normalized == right_normalized:
        return True
    return (
        SequenceMatcher(None, left_normalized, right_normalized).ratio()
        >= SNIPPET_NEAR_DUPLICATE_THRESHOLD
    )


def _consolidate_matches(item: RetrievalEvidenceItem) -> list[ConsolidatedEvidenceMatch]:
    grouped: dict[str, ConsolidatedEvidenceMatch] = {}
    for match in item["matches"]:
        signature = "|".join(
            [
                str(match.get("source_ref", "")).strip().casefold(),
                str(match.get("snippet", "")).strip().casefold(),
            ]
        )
        if not signature.strip("|"):
            continue
        score = float(match.get("score", 0.0) or 0.0)
        existing = grouped.get(signature)
        if existing is None:
            grouped[signature] = {
                "source_ref": str(match.get("source_ref", "")).strip(),
                "snippet": str(match.get("snippet", "")).strip(),
                "best_score": score,
                "query_texts": [str(match.get("query_text", "")).strip()] if str(match.get("query_text", "")).strip() else [],
                "query_indexes": [int(match.get("query_index", 0) or 0)]
                if isinstance(match.get("query_index"), int)
                else [],
                "section": str(match.get("section", "")).strip(),
                "block_type": str(match.get("block_type", "")).strip(),
                "block_title": str(match.get("block_title", "")).strip(),
                "raw_match_count": 1,
            }
            continue
        existing["raw_match_count"] += 1
        query_text = str(match.get("query_text", "")).strip()
        if query_text and query_text not in existing["query_texts"]:
            existing["query_texts"].append(query_text)
        query_index = match.get("query_index")
        if isinstance(query_index, int) and query_index >= 0 and query_index not in existing["query_indexes"]:
            existing["query_indexes"].append(query_index)
        if score > existing["best_score"]:
            existing["best_score"] = score
            existing["section"] = str(match.get("section", "")).strip()
            existing["block_type"] = str(match.get("block_type", "")).strip()
            existing["block_title"] = str(match.get("block_title", "")).strip()
    consolidated = list(grouped.values())
    for match in consolidated:
        match["query_indexes"] = sorted(match["query_indexes"])
    return sorted(consolidated, key=lambda value: (-value["best_score"], value["snippet"].casefold()))


def _build_discarded_match(
    match: ConsolidatedEvidenceMatch,
    *,
    discard_reason: str,
) -> DiscardedEvidenceMatch:
    return {
        **match,
        "discard_reason": discard_reason,
    }


def _assign_evidence_ids(
    matches: list[ConsolidatedEvidenceMatch] | list[DiscardedEvidenceMatch],
    *,
    prefix: str,
) -> list[ConsolidatedEvidenceMatch] | list[DiscardedEvidenceMatch]:
    identified: list[ConsolidatedEvidenceMatch] | list[DiscardedEvidenceMatch] = []
    for index, match in enumerate(matches, start=1):
        identified.append(
            {
                **match,
                "evidence_id": f"{prefix}_{index:03d}",
            }
        )
    return identified


def _partition_consolidated_matches(
    item: RetrievalEvidenceItem,
    *,
    consolidated_matches: list[ConsolidatedEvidenceMatch],
    thresholds: dict[str, float],
) -> tuple[list[ConsolidatedEvidenceMatch], list[DiscardedEvidenceMatch]]:
    accepted_matches: list[ConsolidatedEvidenceMatch] = []
    discarded_matches: list[DiscardedEvidenceMatch] = []

    for match in consolidated_matches:
        if match["best_score"] < thresholds["review_min"]:
            discarded_matches.append(
                _build_discarded_match(
                    match,
                    discard_reason=DISCARD_REASON_SCORE_BELOW_REVIEW_THRESHOLD,
                )
            )
            continue

        overlap = _lexical_overlap(item["raw_text"], match["snippet"])
        has_multi_query_support = len(match["query_texts"]) >= 2 or match["raw_match_count"] >= 2
        if (
            match["best_score"] < thresholds["useful_min"]
            and not has_multi_query_support
            and overlap < MIN_WEAK_MATCH_CRITERION_OVERLAP
        ):
            discarded_matches.append(
                _build_discarded_match(
                    match,
                    discard_reason=DISCARD_REASON_SCORE_BELOW_REVIEW_THRESHOLD,
                )
            )
            continue

        duplicate_of_index: int | None = None
        for index, accepted in enumerate(accepted_matches):
            if _are_near_duplicate_snippets(match["snippet"], accepted["snippet"]):
                duplicate_of_index = index
                break
        if duplicate_of_index is None:
            accepted_matches.append(match)
            continue

        accepted = accepted_matches[duplicate_of_index]
        if match["best_score"] > accepted["best_score"]:
            discarded_matches.append(
                _build_discarded_match(
                    accepted,
                    discard_reason=DISCARD_REASON_DUPLICATE_OF_BETTER_MATCH,
                )
            )
            accepted_matches[duplicate_of_index] = match
            continue
        discarded_matches.append(
            _build_discarded_match(
                match,
                discard_reason=DISCARD_REASON_REDUNDANT_SAME_FRAGMENT,
            )
        )

    accepted_matches.sort(key=lambda value: (-value["best_score"], value["snippet"].casefold()))
    discarded_matches.sort(key=lambda value: (-value["best_score"], value["snippet"].casefold()))
    accepted_matches = _assign_evidence_ids(accepted_matches, prefix="acc")
    discarded_matches = _assign_evidence_ids(discarded_matches, prefix="disc")
    return accepted_matches, discarded_matches


def _item_status_from_best_score(best_score: float, thresholds: dict[str, float]) -> str:
    if best_score >= thresholds["strong_min"]:
        return ITEM_STATUS_STRONG_EVIDENCE
    if best_score >= thresholds["useful_min"]:
        return ITEM_STATUS_USEFUL_EVIDENCE
    if best_score >= thresholds["review_min"]:
        return ITEM_STATUS_REVIEW
    return ITEM_STATUS_NO_EVIDENCE


def _analyze_item(
    item: RetrievalEvidenceItem,
    *,
    thresholds: dict[str, float],
) -> EvidenceAnalysisItem:
    consolidated_matches = _consolidate_matches(item)
    accepted_matches, discarded_matches = _partition_consolidated_matches(
        item,
        consolidated_matches=consolidated_matches,
        thresholds=thresholds,
    )
    best_score = max((match["best_score"] for match in accepted_matches), default=0.0)
    accepted_query_hits = {
        query_text.casefold()
        for match in accepted_matches
        for query_text in match["query_texts"]
        if query_text
    }
    return {
        "item_id": item["item_id"],
        "item_index": item["item_index"],
        "group_code": item["group_code"],
        "raw_text": item["raw_text"],
        "item_status": _item_status_from_best_score(best_score, thresholds),
        "best_score": best_score,
        "raw_match_count": len(item["matches"]),
        "accepted_match_count": len(accepted_matches),
        "discarded_match_count": len(discarded_matches),
        "distinct_query_hits": len(accepted_query_hits),
        "best_evidence": accepted_matches[:TOP_BEST_EVIDENCE_LIMIT],
        "accepted_matches": accepted_matches,
        "discarded_matches": discarded_matches,
    }


def _has_any_matches(contract: VacancyRetrievalEvidenceContract) -> bool:
    payload = contract["evidence"]
    groups = [
        payload["responsibilities"],
        payload["required_criteria"],
        payload["desirable_criteria"],
        payload["benefits"],
        payload["about_the_company"],
        payload["work_conditions"],
    ]
    return any(bool(item.get("matches")) for group in groups for item in group)


def build_vacancy_evidence_analysis(
    *,
    opportunity: dict[str, Any],
    vacancy_retrieval_evidence_artifact: dict[str, Any],
) -> VacancyEvidenceAnalysisContract:
    if not isinstance(vacancy_retrieval_evidence_artifact, dict) or not is_vacancy_retrieval_evidence_contract(
        vacancy_retrieval_evidence_artifact
    ):
        raise VacancyEvidenceAnalysisBuildError(
            "Step 6 requires a valid vacancy_retrieval_evidence.v1 artifact."
        )

    normalized_evidence = normalize_vacancy_retrieval_evidence_contract(vacancy_retrieval_evidence_artifact)
    if not _has_any_matches(normalized_evidence):
        raise VacancyEvidenceAnalysisBuildError(
            "Step 6 requires at least one retrieval match in Step 5 evidence."
        )

    thresholds = _score_thresholds()
    payload = normalized_evidence["evidence"]
    analysis = empty_vacancy_evidence_analysis_contract()
    analysis["vacancy_id"] = normalized_evidence["vacancy_id"] or str(opportunity.get("opportunity_id", "")).strip()
    analysis["generated_at"] = _now_iso()
    analysis["thresholds"] = thresholds
    analysis["analysis"] = {
        "responsibilities": [
            _analyze_item(item, thresholds=thresholds) for item in payload["responsibilities"]
        ],
        "required_criteria": [
            _analyze_item(item, thresholds=thresholds) for item in payload["required_criteria"]
        ],
        "desirable_criteria": [
            _analyze_item(item, thresholds=thresholds) for item in payload["desirable_criteria"]
        ],
        "benefits": [_analyze_item(item, thresholds=thresholds) for item in payload["benefits"]],
        "about_the_company": [
            _analyze_item(item, thresholds=thresholds) for item in payload["about_the_company"]
        ],
        "work_conditions": [_analyze_item(item, thresholds=thresholds) for item in payload["work_conditions"]],
    }
    return normalize_vacancy_evidence_analysis_contract(analysis)
