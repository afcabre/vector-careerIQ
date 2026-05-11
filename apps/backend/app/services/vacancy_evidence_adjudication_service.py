from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

from app.services.llm_service import FALLBACK_MESSAGE, complete_prompt
from app.services.prompt_config_store import (
    FLOW_TASK_VACANCY_EVIDENCE_ADJUDICATION,
    build_prompt_text,
)
from app.services.vacancy_alignment_report_service import (
    _extract_json_object,
    _opportunity_context_payload,
    _person_context_payload,
    _system_prompt_from_global_layers,
)
from app.services.vacancy_dimensions_enriched_contract import (
    is_vacancy_dimensions_enriched_contract,
    normalize_vacancy_dimensions_enriched_contract,
)
from app.services.vacancy_evidence_adjudication_contract import (
    ADJUDICATION_GROUPS,
    CONTRACT_VERSION_VACANCY_EVIDENCE_ADJUDICATION,
    GROUP_CODE_BY_GROUP,
    GROUP_ABOUT_THE_COMPANY,
    GROUP_BENEFITS,
    GROUP_DESIRABLE_CRITERIA,
    GROUP_REQUIRED_CRITERIA,
    GROUP_RESPONSIBILITIES,
    GROUP_WORK_CONDITIONS,
    PRIORITY_CONTEXTUAL,
    PRIORITY_DESIRABLE,
    PRIORITY_IMPORTANT,
    VacancyEvidenceAdjudicationContract,
    VacancyEvidenceAdjudicationItem,
    empty_vacancy_evidence_adjudication_contract,
    normalize_vacancy_evidence_adjudication_contract,
)
from app.services.vacancy_evidence_analysis_contract import (
    VacancyEvidenceAnalysisContract,
    is_vacancy_evidence_analysis_contract,
    normalize_vacancy_evidence_analysis_contract,
)
from app.services.vacancy_v2_runtime_config import get_vacancy_v2_runtime_config


class VacancyEvidenceAdjudicationBuildError(RuntimeError):
    pass


PROFESSIONAL_ADJUDICATION_GROUPS = (
    GROUP_RESPONSIBILITIES,
    GROUP_REQUIRED_CRITERIA,
    GROUP_DESIRABLE_CRITERIA,
)
EXCLUDED_CONTEXTUAL_ADJUDICATION_GROUPS = (
    GROUP_WORK_CONDITIONS,
    GROUP_BENEFITS,
    GROUP_ABOUT_THE_COMPANY,
)


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _default_priority_for_group(group: str) -> str:
    if group == GROUP_DESIRABLE_CRITERIA:
        return PRIORITY_DESIRABLE
    if group in {"work_conditions", "benefits", "about_the_company"}:
        return PRIORITY_CONTEXTUAL
    return PRIORITY_IMPORTANT


def _analysis_signature(*, item_id: str, item_index: int, group_code: str, raw_text: str) -> str:
    return "|".join(
        [
            item_id.strip().casefold(),
            str(item_index),
            group_code.strip().casefold(),
            raw_text.strip().casefold(),
        ]
    )


def _expected_item_signature(item: dict[str, Any] | VacancyEvidenceAdjudicationItem) -> str:
    return _analysis_signature(
        item_id=str(item.get("item_id", "")).strip(),
        item_index=int(item.get("item_index", 0) or 0),
        group_code=str(item.get("group_code", "")).strip(),
        raw_text=str(item.get("raw_text", "")).strip(),
    )


def _iter_expected_items(
    vacancy_dimensions_enriched_artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    normalized = normalize_vacancy_dimensions_enriched_contract(vacancy_dimensions_enriched_artifact)
    items: list[dict[str, Any]] = []
    payload = normalized["vacancy_dimensions"]
    for group in PROFESSIONAL_ADJUDICATION_GROUPS:
        for item in payload[group]:
            raw_text = str(item.get("raw_text", "")).strip()
            item_id = str(item.get("item_id", "")).strip()
            item_index = item.get("item_index", 0)
            if not raw_text:
                continue
            items.append(
                {
                    "item_id": item_id,
                    "item_index": int(item_index) if isinstance(item_index, int) and item_index >= 0 else 0,
                    "group": group,
                    "group_code": GROUP_CODE_BY_GROUP[group],
                    "raw_text": raw_text,
                    "priority": _default_priority_for_group(group),
                }
            )
    return items


def _has_any_expected_items(items: list[dict[str, Any]]) -> bool:
    return any(bool(item["raw_text"]) for item in items)


def _build_analysis_index(
    vacancy_evidence_analysis_artifact: VacancyEvidenceAnalysisContract,
) -> dict[str, dict[str, Any]]:
    payload = vacancy_evidence_analysis_artifact["analysis"]
    indexed: dict[str, dict[str, Any]] = {}
    for group in PROFESSIONAL_ADJUDICATION_GROUPS:
        for item in payload[group]:
            signature = _analysis_signature(
                item_id=item["item_id"],
                item_index=item["item_index"],
                group_code=item["group_code"],
                raw_text=item["raw_text"],
            )
            indexed[signature] = {
                "group": group,
                "analysis": item,
            }
    return indexed


def _build_adjudication_input(
    expected_items: list[dict[str, Any]],
    analysis_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    adjudication_input: list[dict[str, Any]] = []
    for item in expected_items:
        signature = _analysis_signature(
            item_id=item["item_id"],
            item_index=item["item_index"],
            group_code=item["group_code"],
            raw_text=item["raw_text"],
        )
        analysis_payload = analysis_index.get(signature, {})
        analysis_item = analysis_payload.get("analysis")
        adjudication_input.append(
            {
                "item_id": item["item_id"],
                "item_index": item["item_index"],
                "group": item["group"],
                "group_code": item["group_code"],
                "raw_text": item["raw_text"],
                "default_priority": item["priority"],
                "evidence_analysis": analysis_item or {
                    "item_id": item["item_id"],
                    "item_index": item["item_index"],
                    "group_code": item["group_code"],
                    "raw_text": item["raw_text"],
                    "item_status": "no_evidence",
                    "best_score": 0.0,
                    "raw_match_count": 0,
                    "accepted_match_count": 0,
                    "discarded_match_count": 0,
                    "distinct_query_hits": 0,
                    "best_evidence": [],
                    "accepted_matches": [],
                    "discarded_matches": [],
                },
            }
        )
    return adjudication_input


def _contract_candidate_from_llm(parsed: dict[str, object]) -> dict[str, object]:
    if "items" in parsed or "warnings" in parsed:
        return parsed
    return {"items": parsed, "warnings": []}


def _has_meaningful_items(contract: VacancyEvidenceAdjudicationContract) -> bool:
    return bool(contract["items"])


def _describe_expected_item(item: dict[str, Any]) -> str:
    item_id = str(item.get("item_id", "")).strip()
    raw_text = str(item.get("raw_text", "")).strip()
    if item_id and raw_text:
        return f"{item_id}: {raw_text}"
    return item_id or raw_text or "unknown_item"


def _filter_dimensions_enriched_artifact(
    vacancy_dimensions_enriched_artifact: dict[str, Any],
    expected_items: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_signatures = {_expected_item_signature(item) for item in expected_items}
    payload = vacancy_dimensions_enriched_artifact["vacancy_dimensions"]
    return {
        "contract_version": vacancy_dimensions_enriched_artifact["contract_version"],
        "vacancy_id": vacancy_dimensions_enriched_artifact["vacancy_id"],
        "generated_at": vacancy_dimensions_enriched_artifact["generated_at"],
        "vacancy_dimensions": {
            group: [
                item
                for item in payload[group]
                if _expected_item_signature(item) in expected_signatures
            ]
            for group in ADJUDICATION_GROUPS
        },
    }


def _filter_evidence_analysis_artifact(
    vacancy_evidence_analysis_artifact: VacancyEvidenceAnalysisContract,
    expected_items: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_signatures = {_expected_item_signature(item) for item in expected_items}
    payload = vacancy_evidence_analysis_artifact["analysis"]
    return {
        "contract_version": vacancy_evidence_analysis_artifact["contract_version"],
        "vacancy_id": vacancy_evidence_analysis_artifact["vacancy_id"],
        "generated_at": vacancy_evidence_analysis_artifact["generated_at"],
        "thresholds": dict(vacancy_evidence_analysis_artifact["thresholds"]),
        "analysis": {
            group: [
                item
                for item in payload[group]
                if _expected_item_signature(item) in expected_signatures
            ]
            for group in ADJUDICATION_GROUPS
        },
    }


def _excluded_contextual_group_warnings(
    vacancy_dimensions_enriched_artifact: dict[str, Any],
) -> list[str]:
    payload = vacancy_dimensions_enriched_artifact["vacancy_dimensions"]
    warnings: list[str] = []
    for group in EXCLUDED_CONTEXTUAL_ADJUDICATION_GROUPS:
        if payload[group]:
            warnings.append(f"{group}_excluded_from_step_6_5")
    return warnings


def _build_prompt_inputs(
    *,
    person: dict[str, Any],
    opportunity: dict[str, Any],
    vacancy_id: str,
    expected_items: list[dict[str, Any]],
    vacancy_dimensions_enriched_artifact: dict[str, Any],
    vacancy_evidence_analysis_artifact: VacancyEvidenceAnalysisContract,
) -> dict[str, str]:
    person_context = json.dumps(_person_context_payload(person), ensure_ascii=False)
    opportunity_context = json.dumps(_opportunity_context_payload(opportunity), ensure_ascii=False)
    dimensions_json = json.dumps(
        _filter_dimensions_enriched_artifact(
            vacancy_dimensions_enriched_artifact,
            expected_items,
        ),
        ensure_ascii=False,
    )
    evidence_analysis_json = json.dumps(
        _filter_evidence_analysis_artifact(
            vacancy_evidence_analysis_artifact,
            expected_items,
        ),
        ensure_ascii=False,
    )
    adjudication_input_json = json.dumps(
        {
            "vacancy_id": vacancy_id,
            "items": _build_adjudication_input(
                expected_items,
                _build_analysis_index(vacancy_evidence_analysis_artifact),
            ),
        },
        ensure_ascii=False,
    )
    return {
        "person_context": person_context,
        "opportunity_context": opportunity_context,
        "vacancy_dimensions_enriched_json": dimensions_json,
        "evidence_analysis_json": evidence_analysis_json,
        "adjudication_input_json": adjudication_input_json,
    }


def _run_adjudication_completion(
    *,
    person: dict[str, Any],
    opportunity: dict[str, Any],
    vacancy_id: str,
    expected_items: list[dict[str, Any]],
    vacancy_dimensions_enriched_artifact: dict[str, Any],
    vacancy_evidence_analysis_artifact: VacancyEvidenceAnalysisContract,
    settings: Any,
    llm_temperature: float,
    phase_label: str,
) -> VacancyEvidenceAdjudicationContract:
    prompt_inputs = _build_prompt_inputs(
        person=person,
        opportunity=opportunity,
        vacancy_id=vacancy_id,
        expected_items=expected_items,
        vacancy_dimensions_enriched_artifact=vacancy_dimensions_enriched_artifact,
        vacancy_evidence_analysis_artifact=vacancy_evidence_analysis_artifact,
    )
    fallback_user_prompt = (
        "Actua como evaluador senior de evidencia candidato-vacante. "
        "Tu tarea es decidir, de forma estrictamente grounded, si la evidencia recuperada del CV soporta cada criterio de la vacante. "
        "Responde exclusivamente JSON valido conforme a vacancy_evidence_adjudication.v1. "
        "No incluyas markdown ni explicaciones fuera del JSON. "
        "Debes devolver exactamente estas claves raiz: items, warnings. "
        "Usa un item de salida por cada item de entrada en adjudication_input. "
        "No omitas ningun item de entrada y no inventes items nuevos. "
        "Antes de responder, verifica internamente que la cantidad de items en items coincide exactamente con la cantidad de items recibidos en adjudication_input. "
        "Para cada item debes devolver exactamente: item_id, item_index, group, group_code, raw_text, criterion_type, priority, alignment_status, evidence_strength, proof_summary, best_supporting_evidence, weak_or_discarded_evidence, limitations, candidate_risk, cv_improvement_opportunity, confidence. "
        "Reglas obligatorias: usa unicamente la evidencia proporcionada; no inventes experiencia, certificaciones, cargos, sectores, herramientas, anos ni preferencias; "
        "no conviertas similitud semantica en cumplimiento; no conviertas ausencia de evidencia en incumplimiento; no uses el score como prueba final; "
        "evalua si el snippet realmente prueba el criterio; si un snippet es cercano pero no prueba el criterio, muevelo a weak_or_discarded_evidence; "
        "si el criterio incluye parte obligatoria y parte deseable, no trates la parte deseable como bloqueador. "
        "alignment_status solo puede ser: direct, partial, indirect, not_evidenced, conflict, not_applicable. "
        "evidence_strength solo puede ser: high, medium, low, none. "
        "priority solo puede ser: critical, important, desirable, contextual. "
        "criterion_type solo puede ser: education, years_experience, leadership, technical_skill, project_management, transformation, business_outcome, certification, language, condition, cultural, other. "
        "candidate_risk solo puede ser: none, low, medium, high. confidence solo puede ser: high, medium, low. "
        "best_supporting_evidence debe incluir solo evidencia que realmente soporte el criterio e indicar why_it_supports. "
        "Vacante: {opportunity_context}. Persona: {person_context}. "
        "Entrada vacancy_dimensions_enriched.v1: {vacancy_dimensions_enriched_json}. "
        "Entrada vacancy_evidence_analysis.v1: {evidence_analysis_json}. "
        "Entrada adjudication_input: {adjudication_input_json}."
    )
    user_prompt = build_prompt_text(
        flow_key=FLOW_TASK_VACANCY_EVIDENCE_ADJUDICATION,
        context=prompt_inputs,
        fallback=fallback_user_prompt,
    )
    response_text = complete_prompt(
        _system_prompt_from_global_layers(person),
        user_prompt,
        settings,
        temperature=llm_temperature,
        person_id=str(person.get("person_id", "")).strip(),
        opportunity_id=str(opportunity.get("opportunity_id", "")).strip(),
        flow_key=FLOW_TASK_VACANCY_EVIDENCE_ADJUDICATION,
        trace_truncation_override=False,
    )
    if not response_text or response_text == FALLBACK_MESSAGE:
        raise VacancyEvidenceAdjudicationBuildError(
            f"{phase_label} LLM response unavailable; evidence adjudication aborted."
        )

    parsed = _extract_json_object(response_text)
    if not parsed:
        raise VacancyEvidenceAdjudicationBuildError(
            f"{phase_label} LLM response is not valid JSON; evidence adjudication aborted."
        )

    candidate = _contract_candidate_from_llm(parsed)
    return normalize_vacancy_evidence_adjudication_contract(candidate)


def _merge_candidate_contracts(
    primary: VacancyEvidenceAdjudicationContract,
    supplemental: VacancyEvidenceAdjudicationContract,
) -> VacancyEvidenceAdjudicationContract:
    merged_items_by_signature: dict[str, VacancyEvidenceAdjudicationItem] = {}
    for item in primary["items"]:
        merged_items_by_signature[_expected_item_signature(item)] = item
    for item in supplemental["items"]:
        merged_items_by_signature[_expected_item_signature(item)] = item

    return normalize_vacancy_evidence_adjudication_contract(
        {
            "items": list(merged_items_by_signature.values()),
            "warnings": list(primary["warnings"]) + list(supplemental["warnings"]),
        }
    )


def _ordered_items_from_expected(
    *,
    candidate_contract: VacancyEvidenceAdjudicationContract,
    expected_items: list[dict[str, Any]],
) -> tuple[list[VacancyEvidenceAdjudicationItem], list[str], list[str]]:
    by_signature = {
        _analysis_signature(
            item_id=item["item_id"],
            item_index=item["item_index"],
            group_code=item["group_code"],
            raw_text=item["raw_text"],
        ): item
        for item in candidate_contract["items"]
    }
    expected_signatures = {
        _analysis_signature(
            item_id=item["item_id"],
            item_index=item["item_index"],
            group_code=item["group_code"],
            raw_text=item["raw_text"],
        )
        for item in expected_items
    }
    ordered: list[VacancyEvidenceAdjudicationItem] = []
    missing: list[str] = []
    for expected in expected_items:
        signature = _analysis_signature(
            item_id=expected["item_id"],
            item_index=expected["item_index"],
            group_code=expected["group_code"],
            raw_text=expected["raw_text"],
        )
        matched = by_signature.get(signature)
        if not matched:
            missing.append(_describe_expected_item(expected))
            continue
        ordered.append(
            {
                **matched,
                "item_id": expected["item_id"],
                "item_index": expected["item_index"],
                "group": expected["group"],
                "group_code": expected["group_code"],
                "raw_text": expected["raw_text"],
                "priority": matched["priority"] or expected["priority"],
            }
        )

    extras = [
        item["raw_text"]
        for signature, item in by_signature.items()
        if signature not in expected_signatures
    ]
    return ordered, missing, extras


def build_vacancy_evidence_adjudication(
    *,
    person: dict[str, Any],
    opportunity: dict[str, Any],
    vacancy_dimensions_enriched_artifact: dict[str, Any],
    vacancy_evidence_analysis_artifact: dict[str, Any],
    settings: Any,
) -> VacancyEvidenceAdjudicationContract:
    if not isinstance(vacancy_dimensions_enriched_artifact, dict) or not is_vacancy_dimensions_enriched_contract(
        vacancy_dimensions_enriched_artifact
    ):
        raise VacancyEvidenceAdjudicationBuildError(
            "Step 6.5 requires a valid vacancy_dimensions_enriched.v1 artifact."
        )
    if not isinstance(vacancy_evidence_analysis_artifact, dict) or not is_vacancy_evidence_analysis_contract(
        vacancy_evidence_analysis_artifact
    ):
        raise VacancyEvidenceAdjudicationBuildError(
            "Step 6.5 requires a valid vacancy_evidence_analysis.v1 artifact."
        )

    normalized_dimensions = normalize_vacancy_dimensions_enriched_contract(
        vacancy_dimensions_enriched_artifact
    )
    normalized_analysis = normalize_vacancy_evidence_analysis_contract(
        vacancy_evidence_analysis_artifact
    )
    expected_items = _iter_expected_items(normalized_dimensions)
    if not _has_any_expected_items(expected_items):
        raise VacancyEvidenceAdjudicationBuildError(
            "Step 6.5 requires at least one enriched vacancy item to adjudicate."
        )

    vacancy_id = (
        normalized_dimensions["vacancy_id"]
        or normalized_analysis["vacancy_id"]
        or str(opportunity.get("opportunity_id", "")).strip()
    )
    generated_at = _now_iso()
    runtime_config = get_vacancy_v2_runtime_config(settings)
    llm_temperature = float(runtime_config["step3"]["llm_temperature"])
    normalized = _run_adjudication_completion(
        person=person,
        opportunity=opportunity,
        vacancy_id=vacancy_id,
        expected_items=expected_items,
        vacancy_dimensions_enriched_artifact=normalized_dimensions,
        vacancy_evidence_analysis_artifact=normalized_analysis,
        settings=settings,
        llm_temperature=llm_temperature,
        phase_label="Step 6.5",
    )
    ordered_items, missing_items, extra_items = _ordered_items_from_expected(
        candidate_contract=normalized,
        expected_items=expected_items,
    )
    retry_used = False
    if missing_items:
        missing_expected_items = [
            item
            for item in expected_items
            if _describe_expected_item(item) in missing_items
        ]
        retry_used = True
        retry_contract = _run_adjudication_completion(
            person=person,
            opportunity=opportunity,
            vacancy_id=vacancy_id,
            expected_items=missing_expected_items,
            vacancy_dimensions_enriched_artifact=normalized_dimensions,
            vacancy_evidence_analysis_artifact=normalized_analysis,
            settings=settings,
            llm_temperature=llm_temperature,
            phase_label="Step 6.5 retry",
        )
        normalized = _merge_candidate_contracts(normalized, retry_contract)
        ordered_items, missing_items, extra_items = _ordered_items_from_expected(
            candidate_contract=normalized,
            expected_items=expected_items,
        )
        if missing_items:
            missing_detail = ", ".join(missing_items)
            raise VacancyEvidenceAdjudicationBuildError(
                "Step 6.5 LLM response omitted adjudication for one or more vacancy items. "
                f"Missing items after retry: {missing_detail}"
            )

    artifact = empty_vacancy_evidence_adjudication_contract()
    artifact["vacancy_id"] = vacancy_id
    artifact["generated_at"] = generated_at
    artifact["items"] = ordered_items
    artifact["warnings"] = list(normalized["warnings"])
    artifact["warnings"].extend(_excluded_contextual_group_warnings(normalized_dimensions))
    if retry_used:
        artifact["warnings"].append(
            "Step 6.5 required a retry because the initial LLM response omitted one or more items."
        )
    if extra_items:
        artifact["warnings"].append(
            "Step 6.5 returned extra items not present in vacancy_dimensions_enriched.v1; they were ignored."
        )
    normalized_artifact = normalize_vacancy_evidence_adjudication_contract(artifact)
    normalized_artifact["contract_version"] = CONTRACT_VERSION_VACANCY_EVIDENCE_ADJUDICATION

    if _has_meaningful_items(normalized_artifact):
        return normalized_artifact

    raise VacancyEvidenceAdjudicationBuildError(
        "Step 6.5 LLM response produced empty evidence adjudication; extraction aborted."
    )
