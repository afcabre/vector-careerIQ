from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_RETRIEVAL_QUERIES = "vacancy_retrieval_queries.v1"


class RetrievalQueryItem(TypedDict):
    item_id: str
    item_index: int
    group_code: str
    raw_text: str
    queries: list[str]


class VacancyRetrievalQueriesPayload(TypedDict):
    responsibilities: list[RetrievalQueryItem]
    required_criteria: list[RetrievalQueryItem]
    desirable_criteria: list[RetrievalQueryItem]
    benefits: list[RetrievalQueryItem]
    about_the_company: list[RetrievalQueryItem]
    work_conditions: list[RetrievalQueryItem]


class VacancyRetrievalQueriesContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    queries: VacancyRetrievalQueriesPayload


def _clean_text(value: Any, *, max_chars: int = 800) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _normalize_text_list(raw: Any, *, max_items: int = 5, max_chars: int = 240) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for value in raw:
        cleaned = _clean_text(value, max_chars=max_chars)
        if not cleaned:
            continue
        signature = cleaned.casefold()
        if signature in seen:
            continue
        seen.add(signature)
        items.append(cleaned)
        if len(items) >= max_items:
            break
    return items


def _empty_query_item() -> RetrievalQueryItem:
    return {
        "item_id": "",
        "item_index": 0,
        "group_code": "",
        "raw_text": "",
        "queries": [],
    }


def _normalize_query_item(raw: Any) -> RetrievalQueryItem | None:
    if not isinstance(raw, dict):
        return None
    normalized = _empty_query_item()
    normalized["item_id"] = _clean_text(raw.get("item_id"), max_chars=64)
    item_index = raw.get("item_index")
    normalized["item_index"] = int(item_index) if isinstance(item_index, int) and item_index >= 0 else 0
    normalized["group_code"] = _clean_text(raw.get("group_code"), max_chars=32)
    normalized["raw_text"] = _clean_text(raw.get("raw_text"), max_chars=500)
    normalized["queries"] = _normalize_text_list(raw.get("queries"), max_items=5, max_chars=240)
    if not normalized["raw_text"]:
        return None
    return normalized


def _normalize_query_list(raw: Any) -> list[RetrievalQueryItem]:
    if not isinstance(raw, list):
        return []
    items: list[RetrievalQueryItem] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_query_item(value)
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


def empty_vacancy_retrieval_queries_contract() -> VacancyRetrievalQueriesContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_RETRIEVAL_QUERIES,
        "vacancy_id": "",
        "generated_at": "",
        "queries": {
            "responsibilities": [],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": [],
        },
    }


def normalize_vacancy_retrieval_queries_contract(raw: Any) -> VacancyRetrievalQueriesContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_retrieval_queries_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)

    payload = source.get("queries")
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
    normalized["queries"] = {
        "responsibilities": _normalize_query_list(payload_source.get("responsibilities")),
        "required_criteria": _normalize_query_list(payload_source.get("required_criteria")),
        "desirable_criteria": _normalize_query_list(payload_source.get("desirable_criteria")),
        "benefits": _normalize_query_list(payload_source.get("benefits")),
        "about_the_company": _normalize_query_list(payload_source.get("about_the_company")),
        "work_conditions": _normalize_query_list(work_conditions),
    }
    return normalized


def is_vacancy_retrieval_queries_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return str(raw.get("contract_version", "")).strip() == CONTRACT_VERSION_VACANCY_RETRIEVAL_QUERIES
