from __future__ import annotations

from typing import Any, TypedDict


CONTRACT_VERSION_VACANCY_EVIDENCE_ADJUDICATION = "vacancy_evidence_adjudication.v1"

GROUP_RESPONSIBILITIES = "responsibilities"
GROUP_REQUIRED_CRITERIA = "required_criteria"
GROUP_DESIRABLE_CRITERIA = "desirable_criteria"
GROUP_WORK_CONDITIONS = "work_conditions"
GROUP_BENEFITS = "benefits"
GROUP_ABOUT_THE_COMPANY = "about_the_company"
ADJUDICATION_GROUPS = (
    GROUP_RESPONSIBILITIES,
    GROUP_REQUIRED_CRITERIA,
    GROUP_DESIRABLE_CRITERIA,
    GROUP_WORK_CONDITIONS,
    GROUP_BENEFITS,
    GROUP_ABOUT_THE_COMPANY,
)

GROUP_CODE_BY_GROUP = {
    GROUP_RESPONSIBILITIES: "resp",
    GROUP_REQUIRED_CRITERIA: "req",
    GROUP_DESIRABLE_CRITERIA: "des",
    GROUP_WORK_CONDITIONS: "cond",
    GROUP_BENEFITS: "ben",
    GROUP_ABOUT_THE_COMPANY: "about",
}
GROUP_BY_CODE = {value: key for key, value in GROUP_CODE_BY_GROUP.items()}

CRITERION_TYPE_EDUCATION = "education"
CRITERION_TYPE_YEARS_EXPERIENCE = "years_experience"
CRITERION_TYPE_LEADERSHIP = "leadership"
CRITERION_TYPE_TECHNICAL_SKILL = "technical_skill"
CRITERION_TYPE_PROJECT_MANAGEMENT = "project_management"
CRITERION_TYPE_TRANSFORMATION = "transformation"
CRITERION_TYPE_BUSINESS_OUTCOME = "business_outcome"
CRITERION_TYPE_CERTIFICATION = "certification"
CRITERION_TYPE_LANGUAGE = "language"
CRITERION_TYPE_CONDITION = "condition"
CRITERION_TYPE_CULTURAL = "cultural"
CRITERION_TYPE_OTHER = "other"
CRITERION_TYPES = {
    CRITERION_TYPE_EDUCATION,
    CRITERION_TYPE_YEARS_EXPERIENCE,
    CRITERION_TYPE_LEADERSHIP,
    CRITERION_TYPE_TECHNICAL_SKILL,
    CRITERION_TYPE_PROJECT_MANAGEMENT,
    CRITERION_TYPE_TRANSFORMATION,
    CRITERION_TYPE_BUSINESS_OUTCOME,
    CRITERION_TYPE_CERTIFICATION,
    CRITERION_TYPE_LANGUAGE,
    CRITERION_TYPE_CONDITION,
    CRITERION_TYPE_CULTURAL,
    CRITERION_TYPE_OTHER,
}

PRIORITY_CRITICAL = "critical"
PRIORITY_IMPORTANT = "important"
PRIORITY_DESIRABLE = "desirable"
PRIORITY_CONTEXTUAL = "contextual"
PRIORITIES = {
    PRIORITY_CRITICAL,
    PRIORITY_IMPORTANT,
    PRIORITY_DESIRABLE,
    PRIORITY_CONTEXTUAL,
}

ALIGNMENT_STATUS_DIRECT = "direct"
ALIGNMENT_STATUS_PARTIAL = "partial"
ALIGNMENT_STATUS_INDIRECT = "indirect"
ALIGNMENT_STATUS_NOT_EVIDENCED = "not_evidenced"
ALIGNMENT_STATUS_CONFLICT = "conflict"
ALIGNMENT_STATUS_NOT_APPLICABLE = "not_applicable"
ALIGNMENT_STATUSES = {
    ALIGNMENT_STATUS_DIRECT,
    ALIGNMENT_STATUS_PARTIAL,
    ALIGNMENT_STATUS_INDIRECT,
    ALIGNMENT_STATUS_NOT_EVIDENCED,
    ALIGNMENT_STATUS_CONFLICT,
    ALIGNMENT_STATUS_NOT_APPLICABLE,
}

EVIDENCE_STRENGTH_HIGH = "high"
EVIDENCE_STRENGTH_MEDIUM = "medium"
EVIDENCE_STRENGTH_LOW = "low"
EVIDENCE_STRENGTH_NONE = "none"
EVIDENCE_STRENGTHS = {
    EVIDENCE_STRENGTH_HIGH,
    EVIDENCE_STRENGTH_MEDIUM,
    EVIDENCE_STRENGTH_LOW,
    EVIDENCE_STRENGTH_NONE,
}

CANDIDATE_RISK_NONE = "none"
CANDIDATE_RISK_LOW = "low"
CANDIDATE_RISK_MEDIUM = "medium"
CANDIDATE_RISK_HIGH = "high"
CANDIDATE_RISKS = {
    CANDIDATE_RISK_NONE,
    CANDIDATE_RISK_LOW,
    CANDIDATE_RISK_MEDIUM,
    CANDIDATE_RISK_HIGH,
}

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
CONFIDENCE_LEVELS = {
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
}


class SupportingEvidenceRef(TypedDict):
    source_ref: str
    block_title: str
    section: str
    snippet: str
    why_it_supports: str


class WeakEvidenceRef(TypedDict):
    source_ref: str
    block_title: str
    reason: str


class VacancyEvidenceAdjudicationItem(TypedDict):
    item_id: str
    item_index: int
    group: str
    group_code: str
    raw_text: str
    criterion_type: str
    priority: str
    alignment_status: str
    evidence_strength: str
    proof_summary: str
    best_supporting_evidence: list[SupportingEvidenceRef]
    weak_or_discarded_evidence: list[WeakEvidenceRef]
    limitations: list[str]
    candidate_risk: str
    cv_improvement_opportunity: str
    confidence: str


class VacancyEvidenceAdjudicationContract(TypedDict):
    contract_version: str
    vacancy_id: str
    generated_at: str
    items: list[VacancyEvidenceAdjudicationItem]
    warnings: list[str]


def _clean_text(value: Any, *, max_chars: int = 1200) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return " ".join(text.split())[:max_chars].rstrip()


def _normalize_string_list(
    raw: Any,
    *,
    max_items: int = 20,
    max_chars: int = 240,
) -> list[str]:
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


def _default_priority_for_group(group: str) -> str:
    if group == GROUP_DESIRABLE_CRITERIA:
        return PRIORITY_DESIRABLE
    if group in {GROUP_WORK_CONDITIONS, GROUP_BENEFITS, GROUP_ABOUT_THE_COMPANY}:
        return PRIORITY_CONTEXTUAL
    return PRIORITY_IMPORTANT


def _empty_supporting_evidence_ref() -> SupportingEvidenceRef:
    return {
        "source_ref": "",
        "block_title": "",
        "section": "",
        "snippet": "",
        "why_it_supports": "",
    }


def _normalize_supporting_evidence_ref(raw: Any) -> SupportingEvidenceRef | None:
    if not isinstance(raw, dict):
        return None
    normalized = _empty_supporting_evidence_ref()
    normalized["source_ref"] = _clean_text(raw.get("source_ref"), max_chars=120)
    normalized["block_title"] = _clean_text(raw.get("block_title"), max_chars=160)
    normalized["section"] = _clean_text(raw.get("section"), max_chars=120)
    normalized["snippet"] = _clean_text(raw.get("snippet"), max_chars=600)
    normalized["why_it_supports"] = _clean_text(raw.get("why_it_supports"), max_chars=280)
    if not normalized["snippet"] and not normalized["source_ref"]:
        return None
    return normalized


def _normalize_supporting_evidence_list(raw: Any) -> list[SupportingEvidenceRef]:
    if not isinstance(raw, list):
        return []
    items: list[SupportingEvidenceRef] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_supporting_evidence_ref(value)
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


def _empty_weak_evidence_ref() -> WeakEvidenceRef:
    return {
        "source_ref": "",
        "block_title": "",
        "reason": "",
    }


def _normalize_weak_evidence_ref(raw: Any) -> WeakEvidenceRef | None:
    if not isinstance(raw, dict):
        return None
    normalized = _empty_weak_evidence_ref()
    normalized["source_ref"] = _clean_text(raw.get("source_ref"), max_chars=120)
    normalized["block_title"] = _clean_text(raw.get("block_title"), max_chars=160)
    normalized["reason"] = _clean_text(raw.get("reason"), max_chars=240)
    if not normalized["reason"] and not normalized["source_ref"]:
        return None
    return normalized


def _normalize_weak_evidence_list(raw: Any) -> list[WeakEvidenceRef]:
    if not isinstance(raw, list):
        return []
    items: list[WeakEvidenceRef] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_weak_evidence_ref(value)
        if not normalized:
            continue
        signature = "|".join(
            [
                normalized["source_ref"].casefold(),
                normalized["reason"].casefold(),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)
        items.append(normalized)
    return items


def _empty_adjudication_item() -> VacancyEvidenceAdjudicationItem:
    return {
        "item_id": "",
        "item_index": 0,
        "group": GROUP_REQUIRED_CRITERIA,
        "group_code": GROUP_CODE_BY_GROUP[GROUP_REQUIRED_CRITERIA],
        "raw_text": "",
        "criterion_type": CRITERION_TYPE_OTHER,
        "priority": PRIORITY_IMPORTANT,
        "alignment_status": ALIGNMENT_STATUS_NOT_EVIDENCED,
        "evidence_strength": EVIDENCE_STRENGTH_NONE,
        "proof_summary": "",
        "best_supporting_evidence": [],
        "weak_or_discarded_evidence": [],
        "limitations": [],
        "candidate_risk": CANDIDATE_RISK_NONE,
        "cv_improvement_opportunity": "",
        "confidence": CONFIDENCE_LOW,
    }


def _normalize_adjudication_item(raw: Any) -> VacancyEvidenceAdjudicationItem | None:
    if not isinstance(raw, dict):
        return None
    normalized = _empty_adjudication_item()
    normalized["item_id"] = _clean_text(raw.get("item_id"), max_chars=64)
    item_index = raw.get("item_index")
    normalized["item_index"] = int(item_index) if isinstance(item_index, int) and item_index >= 0 else 0
    raw_group = _clean_text(raw.get("group"), max_chars=80)
    raw_group_code = _clean_text(raw.get("group_code"), max_chars=32)
    if raw_group in ADJUDICATION_GROUPS:
        normalized["group"] = raw_group
    elif raw_group_code in GROUP_BY_CODE:
        normalized["group"] = GROUP_BY_CODE[raw_group_code]
    normalized["group_code"] = GROUP_CODE_BY_GROUP[normalized["group"]]
    normalized["raw_text"] = _clean_text(raw.get("raw_text"), max_chars=600)
    criterion_type = _clean_text(raw.get("criterion_type"), max_chars=80)
    normalized["criterion_type"] = criterion_type if criterion_type in CRITERION_TYPES else CRITERION_TYPE_OTHER
    priority = _clean_text(raw.get("priority"), max_chars=40)
    normalized["priority"] = priority if priority in PRIORITIES else _default_priority_for_group(normalized["group"])
    alignment_status = _clean_text(raw.get("alignment_status"), max_chars=40)
    normalized["alignment_status"] = (
        alignment_status if alignment_status in ALIGNMENT_STATUSES else ALIGNMENT_STATUS_NOT_EVIDENCED
    )
    evidence_strength = _clean_text(raw.get("evidence_strength"), max_chars=40)
    normalized["evidence_strength"] = (
        evidence_strength if evidence_strength in EVIDENCE_STRENGTHS else EVIDENCE_STRENGTH_NONE
    )
    normalized["proof_summary"] = _clean_text(raw.get("proof_summary"), max_chars=600)
    normalized["best_supporting_evidence"] = _normalize_supporting_evidence_list(
        raw.get("best_supporting_evidence")
    )
    normalized["weak_or_discarded_evidence"] = _normalize_weak_evidence_list(
        raw.get("weak_or_discarded_evidence")
    )
    normalized["limitations"] = _normalize_string_list(raw.get("limitations"), max_items=12, max_chars=220)
    candidate_risk = _clean_text(raw.get("candidate_risk"), max_chars=32)
    normalized["candidate_risk"] = candidate_risk if candidate_risk in CANDIDATE_RISKS else CANDIDATE_RISK_NONE
    normalized["cv_improvement_opportunity"] = _clean_text(
        raw.get("cv_improvement_opportunity"),
        max_chars=320,
    )
    confidence = _clean_text(raw.get("confidence"), max_chars=32)
    normalized["confidence"] = confidence if confidence in CONFIDENCE_LEVELS else CONFIDENCE_LOW
    if not normalized["item_id"] and not normalized["raw_text"]:
        return None
    return normalized


def _normalize_adjudication_items(raw: Any) -> list[VacancyEvidenceAdjudicationItem]:
    if not isinstance(raw, list):
        return []
    items: list[VacancyEvidenceAdjudicationItem] = []
    seen: set[str] = set()
    for value in raw:
        normalized = _normalize_adjudication_item(value)
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


def empty_vacancy_evidence_adjudication_contract() -> VacancyEvidenceAdjudicationContract:
    return {
        "contract_version": CONTRACT_VERSION_VACANCY_EVIDENCE_ADJUDICATION,
        "vacancy_id": "",
        "generated_at": "",
        "items": [],
        "warnings": [],
    }


def normalize_vacancy_evidence_adjudication_contract(raw: Any) -> VacancyEvidenceAdjudicationContract:
    source = raw if isinstance(raw, dict) else {}
    normalized = empty_vacancy_evidence_adjudication_contract()
    normalized["vacancy_id"] = _clean_text(source.get("vacancy_id"), max_chars=120)
    normalized["generated_at"] = _clean_text(source.get("generated_at"), max_chars=64)
    normalized["items"] = _normalize_adjudication_items(source.get("items"))
    normalized["warnings"] = _normalize_string_list(source.get("warnings"), max_items=20, max_chars=220)
    return normalized


def is_vacancy_evidence_adjudication_contract(raw: Any) -> bool:
    if not isinstance(raw, dict):
        return False
    return (
        str(raw.get("contract_version", "")).strip()
        == CONTRACT_VERSION_VACANCY_EVIDENCE_ADJUDICATION
    )
