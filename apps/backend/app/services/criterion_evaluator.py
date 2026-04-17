from __future__ import annotations

from typing import Any, TypedDict

from app.services.candidate_profile_normalizer import CandidateProfileNormalized
from app.services.criterion_evidence_retriever import CriterionEvidence


STATUS_MEETS = "meets"
STATUS_PARTIAL = "partial"
STATUS_UNKNOWN = "unknown"
STATUS_CONFLICT = "conflict"
STATUS_NOT_EVIDENCED_DESIRABLE = "not_evidenced_desirable"

EVIDENCE_DIRECT = "direct"
EVIDENCE_INDIRECT = "indirect"
EVIDENCE_NONE = "none"

GAP_NONE = "none"
GAP_EVIDENCE = "evidence_gap"
GAP_QUALIFICATION = "qualification_gap"
GAP_PREFERENCE = "preference_conflict"
GAP_DESIRABLE = "desirable_gap"


class CriterionEvaluationDetail(TypedDict):
    status: str
    confidence: str
    evidence_strength: str
    gap_type: str
    is_blocking: bool
    affects_objective_fit: bool
    affects_preference_fit: bool
    resolution_source: str
    semantic_notes: str
    missing_information: list[str]


class CriterionEvaluationRow(TypedDict):
    criterion_id: str
    criterion_label: str
    category: str
    origin: str
    criterion_payload: dict[str, Any]
    retrieval_evidence: dict[str, Any]
    evaluation: CriterionEvaluationDetail


def _first_enabled_preference(
    normalized_candidate_profile: CandidateProfileNormalized,
    field_id: str,
) -> list[str]:
    for item in normalized_candidate_profile.get("cultural_preferences", []):
        if str(item.get("field_id", "")).strip() != field_id:
            continue
        if not bool(item.get("enabled", False)):
            continue
        values = item.get("selected_values", [])
        if isinstance(values, list):
            return [str(value).strip() for value in values if str(value).strip()]
    return []


def _salary_match(
    normalized_candidate_profile: CandidateProfileNormalized,
    criterion_payload: dict[str, Any],
) -> tuple[str, str, list[str], str]:
    candidate_salary = normalized_candidate_profile.get("salary_expectation", {})
    c_min = candidate_salary.get("min")
    c_max = candidate_salary.get("max")
    v_min = criterion_payload.get("min")
    v_max = criterion_payload.get("max")
    if c_min is None and c_max is None:
        return STATUS_UNKNOWN, GAP_EVIDENCE, ["candidate_salary_expectation_missing"], "Sin expectativa salarial comparable"
    if v_min is None and v_max is None:
        return STATUS_UNKNOWN, GAP_EVIDENCE, ["vacancy_salary_missing"], "La vacante no ofrece rango comparable"

    lower_bound = v_min if v_min is not None else v_max
    upper_bound = v_max if v_max is not None else v_min
    if lower_bound is None or upper_bound is None:
        return STATUS_PARTIAL, GAP_EVIDENCE, ["partial_salary_information"], "Comparacion salarial incompleta"

    if c_min is not None and c_min > upper_bound:
        return STATUS_CONFLICT, GAP_PREFERENCE, [], "La expectativa minima supera la oferta"
    if c_max is not None and c_max < lower_bound:
        return STATUS_CONFLICT, GAP_PREFERENCE, [], "La expectativa declarada queda por debajo del rango"
    return STATUS_MEETS, GAP_NONE, [], "Existe traslape entre oferta y expectativa"


def _modality_match(
    normalized_candidate_profile: CandidateProfileNormalized,
    criterion_payload: dict[str, Any],
) -> tuple[str, str, list[str], str]:
    offered = str(criterion_payload.get("value", "")).strip().lower()
    allowed = _first_enabled_preference(normalized_candidate_profile, "work_modality")
    if not allowed:
        return STATUS_UNKNOWN, GAP_EVIDENCE, ["candidate_work_modality_missing"], "No hay preferencia de modalidad declarada"
    if offered in [value.lower() for value in allowed]:
        return STATUS_MEETS, GAP_NONE, [], "La modalidad ofrecida esta dentro de las aceptables"
    return STATUS_CONFLICT, GAP_PREFERENCE, [], "La modalidad ofrecida no coincide con las aceptables"


def _location_match(
    normalized_candidate_profile: CandidateProfileNormalized,
    criterion_payload: dict[str, Any],
) -> tuple[str, str, list[str], str]:
    offered = str(criterion_payload.get("value", "")).strip().lower()
    candidate_location = str(
        normalized_candidate_profile.get("identity", {}).get("location", "")
    ).strip().lower()
    if not offered or offered == "no_especificado":
        return STATUS_UNKNOWN, GAP_EVIDENCE, ["vacancy_location_missing"], "La vacante no define ubicacion comparable"
    if not candidate_location:
        return STATUS_UNKNOWN, GAP_EVIDENCE, ["candidate_location_missing"], "No hay ubicacion de candidato"
    if candidate_location in offered or offered in candidate_location:
        return STATUS_MEETS, GAP_NONE, [], "La ubicacion es compatible"
    return STATUS_UNKNOWN, GAP_EVIDENCE, ["location_not_declared_as_constraint"], "Ubicacion diferente, pero no declarada como restriccion"


def _seniority_match(
    normalized_candidate_profile: CandidateProfileNormalized,
    criterion_payload: dict[str, Any],
) -> tuple[str, str, list[str], str]:
    required = str(criterion_payload.get("value", "")).strip().lower()
    years = int(normalized_candidate_profile.get("target_profile", {}).get("years_experience", 0) or 0)
    thresholds = {
        "junior": 1,
        "semi_senior": 3,
        "senior": 5,
        "principal": 8,
    }
    threshold = thresholds.get(required)
    if threshold is None:
        return STATUS_UNKNOWN, GAP_EVIDENCE, ["unsupported_seniority_value"], "Seniority no homologable automaticamente"
    if years >= threshold:
        return STATUS_MEETS, GAP_NONE, [], "La experiencia declarada soporta el seniority"
    if years >= max(0, threshold - 1):
        return STATUS_PARTIAL, GAP_QUALIFICATION, [], "Experiencia cercana al umbral esperado"
    return STATUS_UNKNOWN, GAP_EVIDENCE, ["insufficient_years_signal"], "No hay evidencia suficiente para afirmar el seniority"


def _generic_match(
    evidence: CriterionEvidence,
) -> tuple[str, str, list[str], str, str, str]:
    cv_matches = evidence.get("cv_matches", [])
    profile_matches = evidence.get("profile_evidence", [])
    origin = str(evidence.get("origin", "")).strip()
    best_score = 0.0
    for item in cv_matches:
        try:
            score = float(item.get("score", 0.0) or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if score > best_score:
            best_score = score

    if profile_matches and cv_matches:
        return STATUS_MEETS, GAP_NONE, [], "Hay evidencia en perfil y CV", EVIDENCE_DIRECT, "high"
    if cv_matches and best_score >= 0.72:
        return STATUS_MEETS, GAP_NONE, [], "Hay evidencia CV suficientemente fuerte", EVIDENCE_DIRECT, "medium"
    if profile_matches or cv_matches:
        return STATUS_PARTIAL, GAP_QUALIFICATION, [], "La evidencia existe pero no es concluyente", EVIDENCE_INDIRECT, "medium"
    if origin == "vacante_deseable":
        return STATUS_NOT_EVIDENCED_DESIRABLE, GAP_DESIRABLE, ["desirable_not_demonstrated"], "Deseable no evidenciado", EVIDENCE_NONE, "medium"
    return STATUS_UNKNOWN, GAP_EVIDENCE, ["no_direct_evidence"], "No hay evidencia suficiente", EVIDENCE_NONE, "low"


def evaluate_criteria(
    *,
    normalized_candidate_profile: CandidateProfileNormalized,
    mapped_criteria: dict[str, Any],
    criterion_evidence: list[CriterionEvidence],
) -> list[CriterionEvaluationRow]:
    criteria_index = {
        str(item.get("criterion_id", "")).strip(): item
        for item in mapped_criteria.get("criteria", [])
        if isinstance(item, dict)
    }
    rows: list[CriterionEvaluationRow] = []

    for evidence in criterion_evidence:
        criterion_id = str(evidence.get("criterion_id", "")).strip()
        criterion = criteria_index.get(criterion_id, {})
        criterion_payload = dict(criterion.get("criterion_payload", {}))
        source_field = str(criterion.get("source_field", "")).strip()
        origin = str(evidence.get("origin", "")).strip()

        missing_information: list[str] = []
        semantic_notes = ""
        gap_type = GAP_EVIDENCE
        evidence_strength = EVIDENCE_NONE
        confidence = "low"

        if source_field == "condiciones_trabajo.modality":
            status, gap_type, missing_information, semantic_notes = _modality_match(
                normalized_candidate_profile,
                criterion_payload,
            )
        elif source_field == "condiciones_trabajo.salary":
            status, gap_type, missing_information, semantic_notes = _salary_match(
                normalized_candidate_profile,
                criterion_payload,
            )
        elif source_field == "condiciones_trabajo.location":
            status, gap_type, missing_information, semantic_notes = _location_match(
                normalized_candidate_profile,
                criterion_payload,
            )
        elif source_field == "seniority":
            status, gap_type, missing_information, semantic_notes = _seniority_match(
                normalized_candidate_profile,
                criterion_payload,
            )
        else:
            status, gap_type, missing_information, semantic_notes, evidence_strength, confidence = _generic_match(
                evidence
            )

        if evidence_strength == EVIDENCE_NONE and status in {STATUS_MEETS, STATUS_PARTIAL}:
            evidence_strength = EVIDENCE_INDIRECT
        if confidence == "low" and status == STATUS_MEETS:
            confidence = "medium"

        is_blocking = bool(
            status == STATUS_CONFLICT
            and origin in {"vacante_obligatoria", "vacante_condicion"}
        )
        affects_preference_fit = source_field.startswith("condiciones_trabajo.")
        affects_objective_fit = origin in {
            "vacante_obligatoria",
            "vacante_deseable",
            "vacante_condicion",
        }

        rows.append(
            CriterionEvaluationRow(
                criterion_id=criterion_id,
                criterion_label=str(evidence.get("criterion_label", "")).strip(),
                category=str(evidence.get("category", "")).strip(),
                origin=origin,
                criterion_payload=criterion_payload,
                retrieval_evidence={
                    "query_text": evidence.get("query_text", ""),
                    "cv_matches": evidence.get("cv_matches", []),
                    "profile_evidence": evidence.get("profile_evidence", []),
                },
                evaluation=CriterionEvaluationDetail(
                    status=status,
                    confidence=confidence,
                    evidence_strength=evidence_strength,
                    gap_type=gap_type,
                    is_blocking=is_blocking,
                    affects_objective_fit=affects_objective_fit,
                    affects_preference_fit=affects_preference_fit,
                    resolution_source="deterministic",
                    semantic_notes=semantic_notes,
                    missing_information=missing_information,
                ),
            )
        )
    return rows


def criteria_evaluation_context(rows: list[CriterionEvaluationRow]) -> str:
    if not rows:
        return "Evaluacion por criterio: no disponible."
    lines = ["Evaluacion deterministica preliminar por criterio:"]
    for row in rows:
        evaluation = row.get("evaluation", {})
        lines.append(
            f"- {row['criterion_label']} "
            f"[{row['origin']} / {row['category']}] => "
            f"status={evaluation.get('status', '')}, "
            f"confidence={evaluation.get('confidence', '')}, "
            f"gap={evaluation.get('gap_type', '')}, "
            f"source={evaluation.get('resolution_source', 'deterministic')}"
        )
        notes = str(evaluation.get("semantic_notes", "")).strip()
        if notes:
            lines.append(f"  - Nota: {notes}")
    return "\n".join(lines)
