from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_RETRIEVAL_EVIDENCE = "vacancy_retrieval_evidence.v1"


class RetrievalEvidenceMatch(TypedDict):
    query_index: int
    query_text: str
    score: float
    snippet: str
    source_ref: str
    section: str
    block_type: str
    block_title: str


class RetrievalEvidenceItem(TypedDict):
    item_id: str
    item_index: int
    group_code: str
    raw_text: str
    matches: list[RetrievalEvidenceMatch]


class WorkConditionEvidencePayload(TypedDict):
    salary: list[RetrievalEvidenceItem]
    modality: list[RetrievalEvidenceItem]
    location: list[RetrievalEvidenceItem]
    contract_type: list[RetrievalEvidenceItem]
    other_conditions: list[RetrievalEvidenceItem]


class VacancyRetrievalEvidencePayload(TypedDict):
    responsibilities: list[RetrievalEvidenceItem]
    required_criteria: list[RetrievalEvidenceItem]
    desirable_criteria: list[RetrievalEvidenceItem]
    benefits: list[RetrievalEvidenceItem]
    about_the_company: list[RetrievalEvidenceItem]
    work_conditions: WorkConditionEvidencePayload


class VacancyRetrievalEvidenceContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    evidence: VacancyRetrievalEvidencePayload


def _clean_text(value: Any, *, max_chars: int = 800) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _empty_match() -> RetrievalEvidenceMatch:
    return {
        "query_index": 0,
        "query_text": "",
        "score": 0.0,
        "snippet": "",
        "source_ref": "",
        "section": "",
        "block_type": "",
        "block_title": "",
    }


def _normalize_match(raw: Any) -> RetrievalEvidenceMatch | None:
    if not isinstance(raw, dict):
        return None
    normalized = _empty_match()
    query_index = raw.get("query_index")
    normalized["query_index"] = int(query_index) if isinstance(query_index, int) and query_index >= 0 else 0
    normalized["query_text"] = _clean_text(raw.get("query_text"), max_chars=280)
    try:
        normalized["score"] = float(raw.get("score", 0.0) or 0.0)
    except (TypeError, ValueError):
        normalized["score"] = 0.0
    normalized["snippet"] = _clean_text(raw.get("snippet"), max_chars=500)
    normalized["source_ref"] = _clean_text(raw.get("source_ref"), max_chars=120)
    normalized["section"] = _clean_text(raw.get("section"), max_chars=120)
    normalized["block_type"] = _clean_text(raw.get("block_type"), max_chars=80)
    normalized["block_title"] = _clean_text(raw.get("block_title"), max_chars=160)
    if not normalized["snippet"]:
        return None
    return normalized


def _normalize_match_list(raw: Any) -> list[RetrievalEvidenceMatch]:
    if not isinstance(raw, list):
        return []
    items: list[RetrievalEvidenceMatch] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_match(value)
        if not normalized:
            continue
        signature = "|".join(
            [
                str(normalized["query_index"]),
                normalized["query_text"].casefold(),
                normalized["source_ref"].casefold(),
                normalized["snippet"].casefold(),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _empty_evidence_item() -> RetrievalEvidenceItem:
    return {
        "item_id": "",
        "item_index": 0,
        "group_code": "",
        "raw_text": "",
        "matches": [],
    }


def _normalize_evidence_item(raw: Any) -> RetrievalEvidenceItem | None:
    if not isinstance(raw, dict):
        return None
    normalized = _empty_evidence_item()
    normalized["item_id"] = _clean_text(raw.get("item_id"), max_chars=64)
    item_index = raw.get("item_index")
    normalized["item_index"] = int(item_index) if isinstance(item_index, int) and item_index >= 0 else 0
    normalized["group_code"] = _clean_text(raw.get("group_code"), max_chars=32)
    normalized["raw_text"] = _clean_text(raw.get("raw_text"), max_chars=500)
    normalized["matches"] = _normalize_match_list(raw.get("matches"))
    if not normalized["raw_text"]:
        return None
    return normalized


def _normalize_evidence_list(raw: Any) -> list[RetrievalEvidenceItem]:
    if not isinstance(raw, list):
        return []
    items: list[RetrievalEvidenceItem] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_evidence_item(value)
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


def _empty_work_conditions_evidence() -> WorkConditionEvidencePayload:
    return {
        "salary": [],
        "modality": [],
        "location": [],
        "contract_type": [],
        "other_conditions": [],
    }


def empty_vacancy_retrieval_evidence_contract() -> VacancyRetrievalEvidenceContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_RETRIEVAL_EVIDENCE,
        "vacancy_id": "",
        "generated_at": "",
        "evidence": {
            "responsibilities": [],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": _empty_work_conditions_evidence(),
        },
    }


def normalize_vacancy_retrieval_evidence_contract(raw: Any) -> VacancyRetrievalEvidenceContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_retrieval_evidence_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)

    payload = source.get("evidence")
    payload_source = payload if isinstance(payload, dict) else {}
    work_conditions = (
        payload_source.get("work_conditions")
        if isinstance(payload_source.get("work_conditions"), dict)
        else {}
    )
    normalized["evidence"] = {
        "responsibilities": _normalize_evidence_list(payload_source.get("responsibilities")),
        "required_criteria": _normalize_evidence_list(payload_source.get("required_criteria")),
        "desirable_criteria": _normalize_evidence_list(payload_source.get("desirable_criteria")),
        "benefits": _normalize_evidence_list(payload_source.get("benefits")),
        "about_the_company": _normalize_evidence_list(payload_source.get("about_the_company")),
        "work_conditions": {
            "salary": _normalize_evidence_list(work_conditions.get("salary")),
            "modality": _normalize_evidence_list(work_conditions.get("modality")),
            "location": _normalize_evidence_list(work_conditions.get("location")),
            "contract_type": _normalize_evidence_list(work_conditions.get("contract_type")),
            "other_conditions": _normalize_evidence_list(work_conditions.get("other_conditions")),
        },
    }
    return normalized


def is_vacancy_retrieval_evidence_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return str(raw.get("contract_version", "")).strip() == CONTRACT_VERSION_VACANCY_RETRIEVAL_EVIDENCE
