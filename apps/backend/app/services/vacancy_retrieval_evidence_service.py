from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.core.settings import Settings
from app.services.ai_runtime_config_store import get_ai_runtime_config
from app.services.cv_store import get_active_cv
from app.services.cv_vector_service import query_cv_matches
from app.services.vacancy_retrieval_queries_contract import (
    RetrievalQueryItem,
    VacancyRetrievalQueriesContract,
    is_vacancy_retrieval_queries_contract,
    normalize_vacancy_retrieval_queries_contract,
)
from app.services.vacancy_retrieval_evidence_contract import (
    RetrievalEvidenceItem,
    VacancyRetrievalEvidenceContract,
    empty_vacancy_retrieval_evidence_contract,
    normalize_vacancy_retrieval_evidence_contract,
)


PERSISTENCE_MODE_MINIMAL = "minimal"
PERSISTENCE_MODE_FULL = "full"


class VacancyRetrievalEvidenceBuildError(RuntimeError):
    pass


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _evidence_persistence_mode() -> str:
    raw = str(
        get_ai_runtime_config().get(
            "retrieval_evidence_persistence_mode",
            PERSISTENCE_MODE_MINIMAL,
        )
    ).strip().lower()
    if raw in {PERSISTENCE_MODE_MINIMAL, PERSISTENCE_MODE_FULL}:
        return raw
    return PERSISTENCE_MODE_MINIMAL


def _build_matches(
    *,
    person_id: str,
    cv_id: str,
    queries: list[str],
    settings: Settings,
    top_k: int,
    persistence_mode: str,
) -> list[dict[str, Any]]:
    all_matches: list[dict[str, Any]] = []
    for query_index, query_text in enumerate(queries):
        raw_matches = query_cv_matches(
            person_id=person_id,
            cv_id=cv_id,
            query_text=query_text,
            settings=settings,
            top_k=top_k,
        )
        for match in raw_matches:
            evidence_match = {
                "query_index": query_index,
                "query_text": query_text,
                "score": float(match.get("score", 0.0) or 0.0),
                "snippet": str(match.get("text", "")).strip(),
                "source_ref": str(match.get("chunk_id", "")).strip(),
                "section": str(match.get("section", "")).strip(),
                "block_type": str(match.get("block_type", "")).strip(),
                "block_title": str(match.get("block_title", "")).strip(),
            }
            if persistence_mode == PERSISTENCE_MODE_MINIMAL:
                all_matches.append(evidence_match)
            else:
                evidence_match["chunk_index"] = int(match.get("chunk_index", 0) or 0)
                evidence_match["source_format"] = str(match.get("source_format", "")).strip()
                evidence_match["block_index"] = int(match.get("block_index", 0) or 0)
                evidence_match["subchunk_index"] = int(match.get("subchunk_index", 0) or 0)
                all_matches.append(evidence_match)
    return all_matches


def _build_evidence_item(
    *,
    item: RetrievalQueryItem,
    person_id: str,
    cv_id: str,
    settings: Settings,
    top_k: int,
    persistence_mode: str,
) -> RetrievalEvidenceItem:
    return {
        "item_id": item["item_id"],
        "item_index": item["item_index"],
        "group_code": item["group_code"],
        "raw_text": item["raw_text"],
        "matches": _build_matches(
            person_id=person_id,
            cv_id=cv_id,
            queries=item["queries"],
            settings=settings,
            top_k=top_k,
            persistence_mode=persistence_mode,
        ),
    }


def _has_any_query_strings(contract: VacancyRetrievalQueriesContract) -> bool:
    payload = contract["queries"]
    groups = [
        payload["responsibilities"],
        payload["required_criteria"],
        payload["desirable_criteria"],
        payload["benefits"],
        payload["about_the_company"],
        payload["work_conditions"],
    ]
    return any(bool(item.get("queries")) for group in groups for item in group)


def build_vacancy_retrieval_evidence(
    *,
    opportunity: dict[str, Any],
    vacancy_retrieval_queries_artifact: dict[str, Any],
    settings: Settings,
) -> VacancyRetrievalEvidenceContract:
    if not isinstance(vacancy_retrieval_queries_artifact, dict) or not is_vacancy_retrieval_queries_contract(
        vacancy_retrieval_queries_artifact
    ):
        raise VacancyRetrievalEvidenceBuildError(
            "Step 5 requires a valid vacancy_retrieval_queries.v1 artifact."
        )

    normalized_queries = normalize_vacancy_retrieval_queries_contract(vacancy_retrieval_queries_artifact)
    if not _has_any_query_strings(normalized_queries):
        raise VacancyRetrievalEvidenceBuildError(
            "Step 5 requires at least one non-empty retrieval query."
        )

    person_id = str(opportunity.get("person_id", "")).strip()
    if not person_id:
        raise VacancyRetrievalEvidenceBuildError("Step 5 requires person context.")

    active_cv = get_active_cv(person_id)
    if not active_cv:
        raise VacancyRetrievalEvidenceBuildError(
            "Step 5 requires an active CV before retrieval can run."
        )
    if str(active_cv.get("vector_index_status", "")).strip() != "indexed":
        raise VacancyRetrievalEvidenceBuildError(
            "Step 5 requires an indexed active CV before retrieval can run."
        )

    ai_runtime_config = get_ai_runtime_config()
    top_k = int(ai_runtime_config["top_k_semantic_per_criterion"])
    persistence_mode = _evidence_persistence_mode()
    cv_id = str(active_cv.get("cv_id", "")).strip()
    payload = normalized_queries["queries"]

    evidence = empty_vacancy_retrieval_evidence_contract()
    evidence["vacancy_id"] = normalized_queries["vacancy_id"] or str(opportunity.get("opportunity_id", "")).strip()
    evidence["generated_at"] = _now_iso()
    evidence["evidence"] = {
        "responsibilities": [
            _build_evidence_item(
                item=item,
                person_id=person_id,
                cv_id=cv_id,
                settings=settings,
                top_k=top_k,
                persistence_mode=persistence_mode,
            )
            for item in payload["responsibilities"]
        ],
        "required_criteria": [
            _build_evidence_item(
                item=item,
                person_id=person_id,
                cv_id=cv_id,
                settings=settings,
                top_k=top_k,
                persistence_mode=persistence_mode,
            )
            for item in payload["required_criteria"]
        ],
        "desirable_criteria": [
            _build_evidence_item(
                item=item,
                person_id=person_id,
                cv_id=cv_id,
                settings=settings,
                top_k=top_k,
                persistence_mode=persistence_mode,
            )
            for item in payload["desirable_criteria"]
        ],
        "benefits": [
            _build_evidence_item(
                item=item,
                person_id=person_id,
                cv_id=cv_id,
                settings=settings,
                top_k=top_k,
                persistence_mode=persistence_mode,
            )
            for item in payload["benefits"]
        ],
        "about_the_company": [
            _build_evidence_item(
                item=item,
                person_id=person_id,
                cv_id=cv_id,
                settings=settings,
                top_k=top_k,
                persistence_mode=persistence_mode,
            )
            for item in payload["about_the_company"]
        ],
        "work_conditions": [
            _build_evidence_item(
                item=item,
                person_id=person_id,
                cv_id=cv_id,
                settings=settings,
                top_k=top_k,
                persistence_mode=persistence_mode,
            )
            for item in payload["work_conditions"]
        ],
    }
    return normalize_vacancy_retrieval_evidence_contract(evidence)
