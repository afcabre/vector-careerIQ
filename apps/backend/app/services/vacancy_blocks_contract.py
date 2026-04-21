from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_BLOCKS = "vacancy_blocks.v1"

VACANCY_BLOCK_KEYS = (
    "work_conditions",
    "responsibilities",
    "required_requirements",
    "desirable_requirements",
    "benefits",
    "unclassified",
)


class VacancyBlocksPayload(TypedDict):
    work_conditions: list[str]
    responsibilities: list[str]
    required_requirements: list[str]
    desirable_requirements: list[str]
    benefits: list[str]
    unclassified: list[str]


class VacancyBlocksContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    vacancy_blocks: VacancyBlocksPayload
    warnings: list[str]
    coverage_notes: list[str]


def _clean_text(value: Any, *, max_chars: int = 800) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _normalize_text_list(raw: Any, *, max_items: int = 200, max_chars: int = 800) -> list[str]:
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


def _empty_vacancy_blocks_payload() -> VacancyBlocksPayload:
    return {
        "work_conditions": [],
        "responsibilities": [],
        "required_requirements": [],
        "desirable_requirements": [],
        "benefits": [],
        "unclassified": [],
    }


def empty_vacancy_blocks_contract() -> VacancyBlocksContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_BLOCKS,
        "vacancy_id": "",
        "generated_at": "",
        "vacancy_blocks": _empty_vacancy_blocks_payload(),
        "warnings": [],
        "coverage_notes": [],
    }


def normalize_vacancy_blocks_contract(raw: Any) -> VacancyBlocksContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_blocks_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)

    payload = source.get("vacancy_blocks")
    payload_source = payload if isinstance(payload, dict) else {}
    normalized_payload = _empty_vacancy_blocks_payload()
    for key in VACANCY_BLOCK_KEYS:
        normalized_payload[key] = _normalize_text_list(payload_source.get(key))
    normalized["vacancy_blocks"] = normalized_payload
    normalized["warnings"] = _normalize_text_list(source.get("warnings"), max_items=100, max_chars=300)
    normalized["coverage_notes"] = _normalize_text_list(
        source.get("coverage_notes"),
        max_items=100,
        max_chars=300,
    )
    return normalized


def is_vacancy_blocks_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return str(raw.get("contract_version", "")).strip() == CONTRACT_VERSION_VACANCY_BLOCKS
