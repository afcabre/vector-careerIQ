from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_FIT_PRESENTATION = "vacancy_fit_presentation.v1"
FIT_PRESENTATION_GROUPS = {
    "required_criteria",
    "responsibilities",
    "desirable_criteria",
}
FIT_PRESENTATION_STATE_VALUES = {
    "🟢 Cumple",
    "🟡 Parcial",
    "⚪ Sin informacion",
    "🔴 En conflicto",
    "🔵 Deseable no evidenciado",
}
FIT_PRESENTATION_CONFIDENCE_VALUES = {"none", "low", "medium", "high"}
FIT_PRESENTATION_CANDIDATE_RISK_VALUES = {"none", "low", "medium", "high"}


class FitPresentationEvidenceRef(TypedDict):
    source_ref: str
    block_title: str
    section: str
    snippet: str
    support_scope: str
    support_note_short: str


class VacancyFitPresentationRow(TypedDict):
    item_id: str
    item_index: int
    group: str
    group_code: str
    type_label: str
    criterion: str
    state: str
    why: str
    evidence_count: int
    evidence: list[FitPresentationEvidenceRef]
    limitations: list[str]
    confidence: str
    candidate_risk: str


class VacancyFitPresentationGroups(TypedDict):
    required_criteria: list[VacancyFitPresentationRow]
    responsibilities: list[VacancyFitPresentationRow]
    desirable_criteria: list[VacancyFitPresentationRow]


class VacancyFitPresentationContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    groups: VacancyFitPresentationGroups
    warnings: list[str]


def _clean_text(value: Any, *, max_chars: int = 1200) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _normalize_string_list(raw: Any, *, max_items: int = 20, max_chars: int = 280) -> list[str]:
    if not isinstance(raw, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for value in raw[:max_items]:
        normalized = _clean_text(value, max_chars=max_chars)
        if not normalized:
            continue
        signature = normalized.casefold()
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _normalize_evidence_ref(raw: Any) -> FitPresentationEvidenceRef | None:
    if not isinstance(raw, dict):
        return None
    normalized = {
        "source_ref": _clean_text(raw.get("source_ref"), max_chars=120),
        "block_title": _clean_text(raw.get("block_title"), max_chars=160),
        "section": _clean_text(raw.get("section"), max_chars=120),
        "snippet": _clean_text(raw.get("snippet"), max_chars=600),
        "support_scope": _clean_text(raw.get("support_scope"), max_chars=40),
        "support_note_short": _clean_text(
            raw.get("support_note_short") or raw.get("why_it_supports"),
            max_chars=220,
        ),
    }
    if not normalized["source_ref"] and not normalized["snippet"]:
        return None
    return normalized


def _normalize_evidence_list(raw: Any) -> list[FitPresentationEvidenceRef]:
    if not isinstance(raw, list):
        return []
    items: list[FitPresentationEvidenceRef] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_evidence_ref(value)
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


def _normalize_row(raw: Any) -> VacancyFitPresentationRow | None:
    if not isinstance(raw, dict):
        return None
    group = _clean_text(raw.get("group"), max_chars=40)
    if group not in FIT_PRESENTATION_GROUPS:
        return None
    state = _clean_text(raw.get("state"), max_chars=40)
    if state not in FIT_PRESENTATION_STATE_VALUES:
        state = "⚪ Sin informacion"
    confidence = _clean_text(raw.get("confidence"), max_chars=16).lower()
    if confidence not in FIT_PRESENTATION_CONFIDENCE_VALUES:
        confidence = "none"
    candidate_risk = _clean_text(raw.get("candidate_risk"), max_chars=16).lower()
    if candidate_risk not in FIT_PRESENTATION_CANDIDATE_RISK_VALUES:
        candidate_risk = "none"
    evidence = _normalize_evidence_list(raw.get("evidence"))
    item_id = _clean_text(raw.get("item_id"), max_chars=120)
    criterion = _clean_text(raw.get("criterion"), max_chars=600)
    if not item_id or not criterion:
        return None
    return {
        "item_id": item_id,
        "item_index": int(raw.get("item_index", 0) or 0),
        "group": group,
        "group_code": _clean_text(raw.get("group_code"), max_chars=24),
        "type_label": _clean_text(raw.get("type_label"), max_chars=48),
        "criterion": criterion,
        "state": state,
        "why": _clean_text(raw.get("why"), max_chars=600),
        "evidence_count": int(raw.get("evidence_count", len(evidence)) or 0),
        "evidence": evidence,
        "limitations": _normalize_string_list(raw.get("limitations"), max_items=10, max_chars=240),
        "confidence": confidence,
        "candidate_risk": candidate_risk,
    }


def empty_vacancy_fit_presentation_contract() -> VacancyFitPresentationContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_FIT_PRESENTATION,
        "vacancy_id": "",
        "generated_at": "",
        "groups": {
            "required_criteria": [],
            "responsibilities": [],
            "desirable_criteria": [],
        },
        "warnings": [],
    }


def normalize_vacancy_fit_presentation_contract(raw: Any) -> VacancyFitPresentationContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_fit_presentation_contract()
    normalized["contract_version"] = (
        _clean_text(source.get("contract_version"), max_chars=64)
        or CONTRACT_VERSION_VACANCY_FIT_PRESENTATION
    )
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)

    raw_groups = source.get("groups") if isinstance(source.get("groups"), dict) else {}
    normalized_groups: VacancyFitPresentationGroups = {
        "required_criteria": [],
        "responsibilities": [],
        "desirable_criteria": [],
    }
    for group_name in FIT_PRESENTATION_GROUPS:
        group_items = raw_groups.get(group_name) if isinstance(raw_groups.get(group_name), list) else []
        rows: list[VacancyFitPresentationRow] = []
        seen_ids: set[str] = set()
        for item in group_items:
            normalized_row = _normalize_row(item)
            if not normalized_row or normalized_row["group"] != group_name:
                continue
            if normalized_row["item_id"] in seen_ids:
                continue
            seen_ids.add(normalized_row["item_id"])
            rows.append(normalized_row)
        rows.sort(key=lambda row: (row["item_index"], row["criterion"].casefold(), row["item_id"]))
        normalized_groups[group_name] = rows
    normalized["groups"] = normalized_groups
    normalized["warnings"] = _normalize_string_list(source.get("warnings"))
    return normalized


def is_vacancy_fit_presentation_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return (
        _clean_text(raw.get("contract_version"), max_chars=64)
        == CONTRACT_VERSION_VACANCY_FIT_PRESENTATION
    )
