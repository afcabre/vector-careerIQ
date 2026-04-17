from __future__ import annotations

from typing import Any, TypedDict

from app.core.settings import Settings
from app.services.ai_runtime_config_store import get_ai_runtime_config
from app.services.candidate_profile_normalizer import CandidateProfileNormalized
from app.services.cv_store import get_active_cv
from app.services.cv_vector_service import query_cv_matches
from app.services.job_criteria_mapper import JobCriteriaMap
from app.services.person_store import PersonRecord


PERSISTENCE_MODE_MINIMAL = "minimal"
PERSISTENCE_MODE_FULL = "full"


class ProfileEvidence(TypedDict):
    source_field: str
    matched_values: list[str]
    note: str


class CriterionEvidence(TypedDict):
    criterion_id: str
    criterion_label: str
    category: str
    origin: str
    query_text: str
    cv_matches: list[dict[str, Any]]
    profile_evidence: list[ProfileEvidence]
    evidence_summary: str


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


def _criterion_query_text(
    criterion: dict[str, Any],
    person: PersonRecord,
) -> str:
    roles = ", ".join(person.get("target_roles", [])[:2]).strip()
    label = str(criterion.get("criterion_label", "")).strip()
    category = str(criterion.get("category", "")).strip()
    origin = str(criterion.get("origin", "")).strip()
    return " ".join(part for part in [label, category, origin, roles] if part).strip()


def _tokenize(text: str) -> list[str]:
    raw = (
        text.lower()
        .replace("/", " ")
        .replace("-", " ")
        .replace(",", " ")
        .replace(";", " ")
        .split()
    )
    return [token for token in raw if len(token) >= 3]


def _match_tokens(values: list[str], criterion_label: str) -> list[str]:
    criterion_tokens = set(_tokenize(criterion_label))
    if not criterion_tokens:
        return []
    matches: list[str] = []
    for value in values:
        value_tokens = set(_tokenize(value))
        if criterion_tokens & value_tokens:
            matches.append(value)
    return matches


def _profile_evidence_for_criterion(
    criterion: dict[str, Any],
    normalized_candidate_profile: CandidateProfileNormalized,
) -> list[ProfileEvidence]:
    criterion_label = str(criterion.get("criterion_label", "")).strip()
    profile_evidence: list[ProfileEvidence] = []
    target_profile = normalized_candidate_profile.get("target_profile", {})
    identity = normalized_candidate_profile.get("identity", {})
    salary_expectation = normalized_candidate_profile.get("salary_expectation", {})
    cultural_preferences = normalized_candidate_profile.get("cultural_preferences", [])

    matched_roles = _match_tokens(list(target_profile.get("target_roles", [])), criterion_label)
    if matched_roles:
        profile_evidence.append(
            ProfileEvidence(
                source_field="target_roles",
                matched_values=matched_roles,
                note="Coincidencia en roles objetivo",
            )
        )

    matched_skills = _match_tokens(list(target_profile.get("skills", [])), criterion_label)
    if matched_skills:
        profile_evidence.append(
            ProfileEvidence(
                source_field="skills",
                matched_values=matched_skills,
                note="Coincidencia en skills declaradas",
            )
        )

    location = str(identity.get("location", "")).strip()
    if location and location.lower() in criterion_label.lower():
        profile_evidence.append(
            ProfileEvidence(
                source_field="location",
                matched_values=[location],
                note="Coincidencia con ubicacion del candidato",
            )
        )

    if "salario" in criterion_label.lower():
        salary_values: list[str] = []
        if salary_expectation.get("min") is not None:
            salary_values.append(str(salary_expectation.get("min")))
        if salary_expectation.get("max") is not None:
            salary_values.append(str(salary_expectation.get("max")))
        currency = str(salary_expectation.get("currency", "")).strip()
        if currency:
            salary_values.append(currency)
        if salary_values:
            profile_evidence.append(
                ProfileEvidence(
                    source_field="salary_expectation",
                    matched_values=salary_values,
                    note="Expectativa salarial declarada",
                )
            )

    if "modalidad" in criterion_label.lower() or "remoto" in criterion_label.lower():
        selected: list[str] = []
        for item in cultural_preferences:
            if str(item.get("field_id", "")).strip() != "work_modality":
                continue
            selected.extend([str(value) for value in item.get("selected_values", [])])
        if selected:
            profile_evidence.append(
                ProfileEvidence(
                    source_field="cultural_fit_preferences.work_modality",
                    matched_values=selected,
                    note="Preferencias de modalidad declaradas",
                )
            )
    return profile_evidence


def _minimalize_cv_matches(cv_matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for item in cv_matches:
        compact.append(
            {
                "score": item.get("score", 0.0),
                "chunk_id": item.get("chunk_id", ""),
                "section": item.get("section", ""),
                "block_type": item.get("block_type", ""),
                "block_title": item.get("block_title", ""),
                "text": str(item.get("text", ""))[:320].strip(),
            }
        )
    return compact


def build_criterion_evidence(
    *,
    person: PersonRecord,
    normalized_candidate_profile: CandidateProfileNormalized,
    mapped_criteria: JobCriteriaMap,
    settings: Settings,
    top_k: int = 3,
) -> list[CriterionEvidence]:
    active_cv = get_active_cv(person["person_id"])
    persistence_mode = _evidence_persistence_mode()
    evidence_rows: list[CriterionEvidence] = []

    for criterion in mapped_criteria.get("criteria", []):
        query_text = _criterion_query_text(criterion, person)
        cv_matches: list[dict[str, Any]] = []
        if active_cv and query_text:
            cv_matches = query_cv_matches(
                person_id=person["person_id"],
                cv_id=active_cv["cv_id"],
                query_text=query_text,
                settings=settings,
                top_k=top_k,
            )
        profile_evidence = _profile_evidence_for_criterion(
            criterion,
            normalized_candidate_profile,
        )
        persisted_matches = (
            cv_matches if persistence_mode == PERSISTENCE_MODE_FULL else _minimalize_cv_matches(cv_matches)
        )
        evidence_rows.append(
            CriterionEvidence(
                criterion_id=str(criterion.get("criterion_id", "")).strip(),
                criterion_label=str(criterion.get("criterion_label", "")).strip(),
                category=str(criterion.get("category", "")).strip(),
                origin=str(criterion.get("origin", "")).strip(),
                query_text=query_text,
                cv_matches=persisted_matches,
                profile_evidence=profile_evidence,
                evidence_summary=(
                    f"cv_matches={len(cv_matches)}, profile_matches={len(profile_evidence)}"
                ),
            )
        )
    return evidence_rows


def criterion_evidence_context(evidence_rows: list[CriterionEvidence]) -> str:
    if not evidence_rows:
        return "Evidencia por criterio: no disponible."
    lines = ["Evidencia por criterio:"]
    for item in evidence_rows:
        lines.append(
            f"- {item['criterion_label']} "
            f"[{item['origin']} / {item['category']}] -> {item['evidence_summary']}"
        )
        for profile_match in item.get("profile_evidence", [])[:2]:
            matched = ", ".join(profile_match.get("matched_values", [])[:3])
            lines.append(
                f"  - Perfil {profile_match.get('source_field')}: {matched}"
            )
        for cv_match in item.get("cv_matches", [])[:2]:
            snippet = str(cv_match.get("text", "")).strip()
            if snippet:
                lines.append(f"  - CV: {snippet[:220]}")
    return "\n".join(lines)
