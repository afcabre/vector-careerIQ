import asyncio
import json
import os
import unittest
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

from fastapi import HTTPException

import app.api.opportunities as opportunities_api
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import artifact_store, conversation_store, cv_store, opportunity_store, person_store, session_store
from app.services.ai_run_store import reset_ai_runs
from app.services.person_store import seed_persons
from app.services.request_trace_store import reset_request_traces
from app.services.vacancy_blocks_service import VacancyBlocksExtractionError
from app.services.vacancy_dimensions_service import VacancyDimensionsExtractionError
from app.services.vacancy_dimensions_enrichment_service import VacancyDimensionsEnrichmentError
from app.services.vacancy_alignment_summary_service import VacancyAlignmentSummaryBuildError
from app.services.vacancy_alignment_summary_v2_service import VacancyAlignmentSummaryV2BuildError
from app.services.vacancy_alignment_report_service import VacancyAlignmentReportBuildError
from app.services.vacancy_alignment_report_v2_service import VacancyAlignmentReportV2BuildError
from app.services.vacancy_evidence_adjudication_service import VacancyEvidenceAdjudicationBuildError
from app.services.vacancy_evidence_analysis_service import VacancyEvidenceAnalysisBuildError
from app.services.vacancy_retrieval_evidence_service import VacancyRetrievalEvidenceBuildError
from app.services.vacancy_retrieval_queries_service import VacancyRetrievalQueriesExtractionError
from app.services.vacancy_salary_service import VacancySalaryNormalizationError
from app.services.vacancy_comparable_conditions_service import VacancyComparableConditionsBuildError
from app.services.candidate_preference_checks_service import CandidatePreferenceChecksBuildError
from app.services.vacancy_fit_presentation_service import VacancyFitPresentationBuildError


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    artifact_store._artifacts.clear()  # type: ignore[attr-defined]
    session_store._sessions.clear()  # type: ignore[attr-defined]
    conversation_store._conversations.clear()  # type: ignore[attr-defined]
    cv_store._cvs.clear()  # type: ignore[attr-defined]
    reset_ai_runs()
    reset_request_traces()


def _sample_vacancy_blocks(opportunity_id: str) -> dict[str, Any]:
    return {
        "flow": {
            "flow_key": "task_vacancy_blocks_extract",
            "contract_version": "vacancy_blocks.v2",
            "prompt_version": "2026-04-21T18:00:00Z",
        },
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-21T10:00:00Z",
        "vacancy_blocks": {
            "about_the_company": [],
            "work_conditions": ["Hibrido en Bogota"],
            "responsibilities": ["Liderar backlog de datos"],
            "required_requirements": [],
            "desirable_requirements": [],
            "benefits": [],
            "unclassified": [],
        },
        "warnings": [],
        "coverage_notes": [],
    }


def _sample_vacancy_dimensions(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_dimensions.v2",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-21T10:01:00Z",
        "vacancy_dimensions": {
            "work_conditions": [{"raw_text": "Hibrido en Bogota"}],
            "responsibilities": [],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "unclassified": [],
        },
        "warnings": [],
        "coverage_notes": [],
    }


def _sample_vacancy_salary(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_salary_normalization.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-21T10:02:00Z",
        "salary": {
            "min": 12000000,
            "max": 18000000,
            "currency": "COP",
            "period": "mensual",
            "raw_text": "Salario COP 12M a 18M mensual",
            "has_variable_component": False,
            "variable_component_type": "",
            "variable_component_note": "",
        },
    }


def _sample_vacancy_comparable_conditions(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_comparable_conditions.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-21T10:02:30Z",
        "location": {
            "raw": "Bogota D.C.",
            "normalized_city": "Bogota",
            "normalized_country": "Colombia",
            "confidence": "high",
        },
        "modality": {
            "raw": "Hibrido 4x1",
            "mode": "hybrid",
            "intensity": "4x1",
            "confidence": "high",
        },
        "compensation": {
            "raw": "Salario COP 12M a 18M mensual",
            "currency": "COP",
            "min_amount": 12000000,
            "max_amount": 18000000,
            "period": "mensual",
            "has_variable_component": False,
            "variable_component_type": "",
            "variable_component_note": "",
            "confidence": "high",
        },
        "contract_type": {
            "raw": "Contrato indefinido",
            "value": "indefinite",
            "confidence": "high",
        },
        "warnings": [],
    }


def _sample_candidate_preference_checks(person_id: str, opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "candidate_preference_checks.v1",
        "vacancy_id": opportunity_id,
        "person_id": person_id,
        "generated_at": "2026-04-21T10:02:40Z",
        "rows": [
            {
                "criterion_key": "location",
                "criterion": "Ubicacion",
                "state": "🟢 Cumple",
                "vacancy_value": "Bogota, Colombia",
                "candidate_value": "Bogota, Colombia",
                "why": "La ubicacion es compatible.",
                "confidence": "high",
            },
            {
                "criterion_key": "modality",
                "criterion": "Modalidad",
                "state": "🟢 Cumple",
                "vacancy_value": "Hibrido 4x1",
                "candidate_value": "hybrid, remote",
                "why": "La modalidad esta dentro de las aceptadas.",
                "confidence": "high",
            },
            {
                "criterion_key": "compensation",
                "criterion": "Compensacion",
                "state": "🟡 Parcial",
                "vacancy_value": "12000000 COP mensual",
                "candidate_value": "10000000 - 14000000 COP monthly",
                "why": "Existe traslape parcial.",
                "confidence": "medium",
            },
            {
                "criterion_key": "contract_type",
                "criterion": "Tipo de contrato",
                "state": "🟢 Cumple",
                "vacancy_value": "Contrato indefinido",
                "candidate_value": "indefinite",
                "why": "El contrato esta dentro de los aceptados.",
                "confidence": "high",
            },
        ],
        "warnings": [],
    }


def _sample_vacancy_fit_presentation(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_fit_presentation.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-21T10:02:50Z",
        "groups": {
            "required_criteria": [
                {
                    "item_id": "req_123",
                    "item_index": 0,
                    "group": "required_criteria",
                    "group_code": "req",
                    "type_label": "Obligatorio",
                    "criterion": "Profesional en Ingenieria de Sistemas",
                    "state": "🟢 Cumple",
                    "why": "La formacion reportada coincide con el requisito.",
                    "evidence_count": 1,
                    "evidence": [
                        {
                            "source_ref": "cv-1",
                            "block_title": "Educacion",
                            "section": "education",
                            "snippet": "Ingeniero de Sistemas",
                            "support_scope": "direct",
                            "support_note_short": "Demuestra el titulo requerido.",
                        }
                    ],
                    "limitations": [],
                    "confidence": "high",
                    "candidate_risk": "low",
                }
            ],
            "responsibilities": [
                {
                    "item_id": "resp_1234567890",
                    "item_index": 0,
                    "group": "responsibilities",
                    "group_code": "resp",
                    "type_label": "Responsabilidad",
                    "criterion": "Liderar backlog de datos",
                    "state": "🟢 Cumple",
                    "why": "La experiencia descrita prueba liderazgo directo sobre backlog.",
                    "evidence_count": 1,
                    "evidence": [
                        {
                            "source_ref": "cv-chunk-1",
                            "block_title": "Experiencia",
                            "section": "experience",
                            "snippet": "Lidere backlog y priorizacion trimestral",
                            "support_scope": "direct",
                            "support_note_short": "Demuestra liderazgo operativo del backlog.",
                        }
                    ],
                    "limitations": [],
                    "confidence": "high",
                    "candidate_risk": "low",
                }
            ],
            "desirable_criteria": [],
        },
        "warnings": [],
    }


def _sample_vacancy_dimensions_enriched(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_dimensions_enriched.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-21T10:03:00Z",
        "vacancy_dimensions": {
            "work_conditions": [],
            "responsibilities": [
                {
                    "raw_text": "Liderar backlog de datos",
                    "item_id": "resp_1234567890",
                    "item_index": 0,
                    "group_code": "resp",
                }
            ],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
        },
    }


def _sample_vacancy_retrieval_queries(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_retrieval_queries.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-24T10:35:00Z",
        "queries": {
            "responsibilities": [
                {
                    "item_id": "resp_1234567890",
                    "item_index": 0,
                    "group_code": "resp",
                    "raw_text": "Liderar backlog de datos",
                    "queries": ["liderazgo de backlog, coordinacion de roadmap de datos"],
                }
            ],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": [],
        },
    }


def _sample_vacancy_retrieval_evidence(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_retrieval_evidence.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-24T10:36:00Z",
        "evidence": {
            "responsibilities": [
                {
                    "item_id": "resp_1234567890",
                    "item_index": 0,
                    "group_code": "resp",
                    "raw_text": "Liderar backlog de datos",
                    "matches": [
                        {
                            "query_index": 0,
                            "query_text": "liderazgo de backlog, coordinacion de roadmap de datos",
                            "score": 0.84,
                            "snippet": "Lidere backlog y priorizacion trimestral",
                            "source_ref": "cv-chunk-1",
                        }
                    ],
                }
            ],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": [],
        },
    }


def _sample_vacancy_evidence_analysis(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_evidence_analysis.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-24T10:37:00Z",
        "thresholds": {
            "strong_min": 0.75,
            "useful_min": 0.45,
            "review_min": 0.30,
        },
        "analysis": {
            "responsibilities": [
                {
                    "item_id": "resp_1234567890",
                    "item_index": 0,
                    "group_code": "resp",
                    "raw_text": "Liderar backlog de datos",
                    "item_status": "strong_evidence",
                    "best_score": 0.84,
                    "raw_match_count": 1,
                    "accepted_match_count": 1,
                    "discarded_match_count": 0,
                    "distinct_query_hits": 1,
                    "best_evidence": [
                        {
                            "source_ref": "cv-chunk-1",
                            "snippet": "Lidere backlog y priorizacion trimestral",
                            "best_score": 0.84,
                            "query_texts": [
                                "liderazgo de backlog, coordinacion de roadmap de datos"
                            ],
                            "query_indexes": [0],
                            "section": "",
                            "block_type": "",
                            "block_title": "",
                            "raw_match_count": 1,
                        }
                    ],
                    "accepted_matches": [],
                    "discarded_matches": [],
                }
            ],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": [],
        },
    }


def _sample_vacancy_evidence_adjudication(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_evidence_adjudication.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-24T10:37:30Z",
        "items": [
            {
                "item_id": "resp_1234567890",
                "item_index": 0,
                "group": "responsibilities",
                "group_code": "resp",
                "raw_text": "Liderar backlog de datos",
                "criterion_type": "leadership",
                "priority": "important",
                "alignment_status": "direct",
                "evidence_strength": "high",
                "proof_summary": "La experiencia descrita prueba liderazgo directo sobre backlog.",
                "best_supporting_evidence": [
                    {
                        "source_ref": "cv-chunk-1",
                        "block_title": "Experiencia",
                        "section": "experience",
                        "snippet": "Lidere backlog y priorizacion trimestral",
                        "support_scope": "direct",
                        "support_note_short": "Demuestra liderazgo operativo del backlog.",
                    }
                ],
                "weak_or_discarded_evidence": [],
                "limitations": [],
                "candidate_risk": "low",
                "cv_improvement_opportunity": "Hacer mas visible el impacto del backlog.",
                "confidence": "high",
            }
        ],
        "warnings": [],
    }


def _sample_vacancy_alignment_summary(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_alignment_summary.v1",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-24T10:38:00Z",
        "source_artifact_version": "vacancy_evidence_analysis.v1",
        "thresholds": {
            "strong_min": 0.75,
            "useful_min": 0.45,
            "review_min": 0.30,
        },
        "summary": {
            "overall": {
                "total_items": 1,
                "strong_evidence_count": 1,
                "useful_evidence_count": 0,
                "review_count": 0,
                "no_evidence_count": 0,
            },
            "groups": {
                "responsibilities": {
                    "total_items": 1,
                    "strong_evidence_count": 1,
                    "useful_evidence_count": 0,
                    "review_count": 0,
                    "no_evidence_count": 0,
                },
                "required_criteria": {
                    "total_items": 0,
                    "strong_evidence_count": 0,
                    "useful_evidence_count": 0,
                    "review_count": 0,
                    "no_evidence_count": 0,
                },
                "desirable_criteria": {
                    "total_items": 0,
                    "strong_evidence_count": 0,
                    "useful_evidence_count": 0,
                    "review_count": 0,
                    "no_evidence_count": 0,
                },
            },
            "strengths": [
                {
                    "group": "responsibilities",
                    "item_id": "resp_1234567890",
                    "item_index": 0,
                    "raw_text": "Liderar backlog de datos",
                    "item_status": "strong_evidence",
                    "best_score": 0.84,
                }
            ],
            "gaps": [],
            "review_items": [],
        },
    }


def _sample_vacancy_alignment_summary_v2(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_alignment_summary.v2",
        "vacancy_id": opportunity_id,
        "generated_at": "2026-04-24T10:38:30Z",
        "source_artifact_version": "vacancy_evidence_adjudication.v1",
        "summary": {
            "overall": {
                "total_items": 1,
                "direct_count": 1,
                "partial_count": 0,
                "indirect_count": 0,
                "not_evidenced_count": 0,
                "conflict_count": 0,
                "not_applicable_count": 0,
            },
            "groups": {
                "required_criteria": {
                    "total_items": 0,
                    "direct_count": 0,
                    "partial_count": 0,
                    "indirect_count": 0,
                    "not_evidenced_count": 0,
                    "conflict_count": 0,
                    "not_applicable_count": 0,
                },
                "responsibilities": {
                    "total_items": 1,
                    "direct_count": 1,
                    "partial_count": 0,
                    "indirect_count": 0,
                    "not_evidenced_count": 0,
                    "conflict_count": 0,
                    "not_applicable_count": 0,
                },
                "desirable_criteria": {
                    "total_items": 0,
                    "direct_count": 0,
                    "partial_count": 0,
                    "indirect_count": 0,
                    "not_evidenced_count": 0,
                    "conflict_count": 0,
                    "not_applicable_count": 0,
                },
                "work_conditions": {
                    "total_items": 0,
                    "direct_count": 0,
                    "partial_count": 0,
                    "indirect_count": 0,
                    "not_evidenced_count": 0,
                    "conflict_count": 0,
                    "not_applicable_count": 0,
                },
            },
            "strengths": [
                {
                    "item_id": "resp_1234567890",
                    "raw_text": "Liderar backlog de datos",
                    "alignment_status": "direct",
                    "evidence_strength": "high",
                    "proof_summary": "La experiencia recuperada soporta directamente el criterio.",
                }
            ],
            "gaps": [],
            "review_items": [],
            "risks": [],
        },
    }


def _sample_vacancy_alignment_report(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_alignment_report.v1",
        "vacancy_id": opportunity_id,
        "person_id": "p-001",
        "generated_at": "2026-04-24T10:39:00Z",
        "source_artifacts": {
            "alignment_summary_version": "vacancy_alignment_summary.v1",
            "evidence_analysis_version": "vacancy_evidence_analysis.v1",
        },
        "report": {
            "executive_summary": "Buen encaje general con una validacion pendiente.",
            "decision_table": {
                "alineacion_general": {
                    "resultado": "Avanzar con reservas",
                    "descripcion_corta": "Buen fit con una brecha abierta.",
                }
            },
            "vacancy_fit_matrix": [
                {
                    "criterio": "Liderar backlog de datos",
                    "categoria": "Responsabilidades",
                    "origen_del_criterio": "Vacante obligatoria",
                    "estado": "🟢 Cumple",
                    "lo_que_solicita_la_vacante": "Liderar backlog de datos",
                    "evidencia_del_candidato": "Lidere backlog y priorizacion trimestral",
                    "descripcion_corta": "Evidencia directa en experiencia previa.",
                }
            ],
            "candidate_preference_matrix": [],
            "fit_answer": "Encaja con la vacante y conviene avanzar con validaciones puntuales.",
            "strengths": ["Experiencia demostrada en backlog."],
            "gaps": ["Cloud no esta demostrado."],
            "preference_conflicts": [],
            "improvement_actions": {
                "reinforce_in_cv_or_profile": ["Resaltar impacto en backlog."],
                "validate_with_recruiter": ["Confirmar stack cloud."],
                "application_narrative": ["Conectar backlog con resultados."],
            },
            "alerts_and_conflicts": ["La vacante no aclara modalidad."],
            "actionable_conclusion": {
                "final_decision": "Avanzar con reservas",
                "main_reason": "El core tecnico encaja y la brecha es validable.",
                "recommended_next_step": "Validar stack cloud con reclutador.",
            },
        },
        "rendered_markdown": "## Resumen ejecutivo\n\nBuen encaje general.",
    }


def _sample_vacancy_alignment_report_v2(opportunity_id: str) -> dict[str, Any]:
    return {
        "contract_version": "vacancy_alignment_report.v2",
        "vacancy_id": opportunity_id,
        "person_id": "p-001",
        "generated_at": "2026-04-24T10:39:30Z",
        "source_artifacts": {
            "evidence_adjudication_version": "vacancy_evidence_adjudication.v1",
            "alignment_summary_version": "vacancy_alignment_summary.v2",
            "evidence_analysis_version": "vacancy_evidence_analysis.v1",
        },
        "report": {
            "executive_summary": {
                "fit_level": "medio_alto",
                "final_recommendation": "Avanzar con reservas",
                "summary": "Buen ajuste general con un deseable abierto.",
                "main_strength": "La experiencia base del rol esta cubierta.",
                "main_gap_or_risk": "No se observa certificacion formal.",
                "confidence": "media",
            },
            "decision_table": {
                "alineacion_general": {
                    "resultado": "🟡 Parcial",
                    "descripcion_corta": "Buen ajuste con un deseable no evidenciado.",
                },
                "recomendacion": {
                    "resultado": "Avanzar con reservas",
                    "descripcion_corta": "Avanzar, validando el deseable.",
                },
            },
            "vacancy_fit_matrix": [
                {
                    "item_id": "resp_1234567890",
                    "criterio": "Liderar backlog de datos",
                    "categoria": "Responsabilidades",
                    "origen_del_criterio": "Vacante obligatoria",
                    "prioridad": "Importante",
                    "estado": "🟢 Cumple",
                    "lo_que_solicita_la_vacante": "Liderar backlog de datos",
                    "evidencia_del_candidato": "Lidere backlog y priorizacion trimestral",
                    "tipo_de_evidencia": "directa",
                    "fuerza_de_evidencia": "alta",
                    "descripcion_corta": "El criterio queda cubierto.",
                    "riesgo_para_la_postulacion": "bajo",
                    "fuentes": ["cv-chunk-1"],
                }
            ],
            "candidate_preference_matrix": [],
            "fit_answer": {
                "encaja": "sí",
                "respuesta_para_el_candidato": "La postulacion es defendible.",
            },
            "strengths": [
                {
                    "fortaleza": "Liderazgo directo de backlog",
                    "por_que_importa": "Es central para el rol.",
                    "evidencia": "Lidere backlog y priorizacion trimestral",
                }
            ],
            "gaps": [],
            "preference_conflicts": [],
            "improvement_actions": {
                "reinforce_in_cv_or_profile": ["Resaltar impacto del backlog."],
                "validate_with_recruiter": ["Confirmar peso real del deseable."],
                "application_narrative": ["Conectar backlog con resultados de negocio."],
            },
            "alerts_and_conflicts": [],
            "actionable_conclusion": {
                "final_decision": "Avanzar con reservas",
                "main_reason": "El core del rol encaja y el resto es validable.",
                "recommended_next_step": "Validar con reclutador el peso de los deseables.",
                "confidence": "media",
            },
        },
        "rendered_markdown": "## Resumen ejecutivo\n\nBuen ajuste general.",
    }


async def _collect_sse_text(streaming_response: Any) -> str:
    chunks: list[str] = []
    async for chunk in streaming_response.body_iterator:
        if isinstance(chunk, bytes):
            chunks.append(chunk.decode("utf-8"))
        else:
            chunks.append(str(chunk))
    return "".join(chunks)


def _parse_sse_events(raw: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        event_name = ""
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if not event_name:
            continue
        payload = json.loads("\n".join(data_lines)) if data_lines else {}
        events.append((event_name, payload))
    return events


class VacancyV2EndpointsTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PERSISTENCE_BACKEND"] = "memory"
        get_settings.cache_clear()
        _clear_in_memory_state()
        seed_persons()
        self.session = SessionData(
            username="tutor",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    def tearDown(self) -> None:
        get_settings.cache_clear()
        _clear_in_memory_state()

    def test_recompute_vacancy_blocks_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Engineer",
            company="Acme",
            location="Remote",
            raw_text="Vacante con requerimientos de datos.",
        )
        opportunity_id = created["opportunity_id"]
        blocks = _sample_vacancy_blocks(opportunity_id)

        with patch.object(opportunities_api, "extract_vacancy_blocks", return_value=blocks):
            response = opportunities_api.recompute_vacancy_blocks(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_blocks_status, "draft")
        self.assertEqual(
            response.vacancy_blocks_artifact["flow"]["contract_version"],
            "vacancy_blocks.v2",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_blocks_status"], "draft")

    def test_recompute_vacancy_blocks_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Engineer",
            company="Acme",
            location="Remote",
            raw_text="Vacante con requerimientos de datos.",
        )
        opportunity_id = created["opportunity_id"]

        with patch.object(
            opportunities_api,
            "extract_vacancy_blocks",
            side_effect=VacancyBlocksExtractionError("Step 2 invalid payload"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_blocks(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 2 invalid payload", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_blocks_status"], "error")

    def test_update_rejects_invalid_vacancy_v2_status_values(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Data Engineer",
            company="Acme",
            location="Remote",
            raw_text="Vacante con requerimientos de datos.",
        )
        opportunity_id = created["opportunity_id"]

        with self.assertRaises(HTTPException) as invalid_blocks_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_blocks_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_blocks_status.exception.status_code, 422)
        self.assertEqual(invalid_blocks_status.exception.detail, "Invalid vacancy_blocks_status")

        with self.assertRaises(HTTPException) as invalid_dimensions_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_dimensions_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_dimensions_status.exception.status_code, 422)
        self.assertEqual(invalid_dimensions_status.exception.detail, "Invalid vacancy_dimensions_status")

        with self.assertRaises(HTTPException) as invalid_salary_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_salary_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_salary_status.exception.status_code, 422)
        self.assertEqual(invalid_salary_status.exception.detail, "Invalid vacancy_salary_status")

        with self.assertRaises(HTTPException) as invalid_comparable_conditions_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(
                    vacancy_comparable_conditions_status="invalid"
                ),
                _=self.session,
            )
        self.assertEqual(invalid_comparable_conditions_status.exception.status_code, 422)
        self.assertEqual(
            invalid_comparable_conditions_status.exception.detail,
            "Invalid vacancy_comparable_conditions_status",
        )

        with self.assertRaises(HTTPException) as invalid_candidate_preference_checks_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(
                    candidate_preference_checks_status="invalid"
                ),
                _=self.session,
            )
        self.assertEqual(invalid_candidate_preference_checks_status.exception.status_code, 422)
        self.assertEqual(
            invalid_candidate_preference_checks_status.exception.detail,
            "Invalid candidate_preference_checks_status",
        )

        with self.assertRaises(HTTPException) as invalid_vacancy_fit_presentation_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(
                    vacancy_fit_presentation_status="invalid"
                ),
                _=self.session,
            )
        self.assertEqual(invalid_vacancy_fit_presentation_status.exception.status_code, 422)
        self.assertEqual(
            invalid_vacancy_fit_presentation_status.exception.detail,
            "Invalid vacancy_fit_presentation_status",
        )

        with self.assertRaises(HTTPException) as invalid_enriched_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_dimensions_enriched_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_enriched_status.exception.status_code, 422)
        self.assertEqual(
            invalid_enriched_status.exception.detail,
            "Invalid vacancy_dimensions_enriched_status",
        )

        with self.assertRaises(HTTPException) as invalid_queries_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_retrieval_queries_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_queries_status.exception.status_code, 422)
        self.assertEqual(
            invalid_queries_status.exception.detail,
            "Invalid vacancy_retrieval_queries_status",
        )

        with self.assertRaises(HTTPException) as invalid_evidence_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_retrieval_evidence_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_evidence_status.exception.status_code, 422)
        self.assertEqual(
            invalid_evidence_status.exception.detail,
            "Invalid vacancy_retrieval_evidence_status",
        )

        with self.assertRaises(HTTPException) as invalid_analysis_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_evidence_analysis_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_analysis_status.exception.status_code, 422)
        self.assertEqual(
            invalid_analysis_status.exception.detail,
            "Invalid vacancy_evidence_analysis_status",
        )

        with self.assertRaises(HTTPException) as invalid_adjudication_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_evidence_adjudication_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_adjudication_status.exception.status_code, 422)
        self.assertEqual(
            invalid_adjudication_status.exception.detail,
            "Invalid vacancy_evidence_adjudication_status",
        )

        with self.assertRaises(HTTPException) as invalid_summary_v2_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_alignment_summary_v2_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_summary_v2_status.exception.status_code, 422)
        self.assertEqual(
            invalid_summary_v2_status.exception.detail,
            "Invalid vacancy_alignment_summary_v2_status",
        )

        with self.assertRaises(HTTPException) as invalid_report_v2_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_alignment_report_v2_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_report_v2_status.exception.status_code, 422)
        self.assertEqual(
            invalid_report_v2_status.exception.detail,
            "Invalid vacancy_alignment_report_v2_status",
        )

        with self.assertRaises(HTTPException) as invalid_summary_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_alignment_summary_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_summary_status.exception.status_code, 422)
        self.assertEqual(
            invalid_summary_status.exception.detail,
            "Invalid vacancy_alignment_summary_status",
        )

        with self.assertRaises(HTTPException) as invalid_report_status:
            opportunities_api.update_opportunity(
                person_id="p-001",
                opportunity_id=opportunity_id,
                payload=opportunities_api.UpdateOpportunityRequest(vacancy_alignment_report_status="invalid"),
                _=self.session,
            )
        self.assertEqual(invalid_report_status.exception.status_code, 422)
        self.assertEqual(
            invalid_report_status.exception.detail,
            "Invalid vacancy_alignment_report_status",
        )

    def test_recompute_vacancy_dimensions_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con condiciones y responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        blocks = _sample_vacancy_blocks(opportunity_id)
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_blocks_artifact=blocks,
            vacancy_blocks_status="approved",
        )
        assert updated is not None
        dimensions = _sample_vacancy_dimensions(opportunity_id)

        with patch.object(opportunities_api, "extract_vacancy_dimensions", return_value=dimensions):
            response = opportunities_api.recompute_vacancy_dimensions(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_dimensions_status, "draft")
        self.assertEqual(response.vacancy_dimensions_artifact["contract_version"], "vacancy_dimensions.v2")
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_status"], "draft")

    def test_recompute_vacancy_salary_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con salario.",
        )
        opportunity_id = created["opportunity_id"]
        dimensions = _sample_vacancy_dimensions(opportunity_id)
        dimensions["vacancy_dimensions"]["work_conditions"] = [
            {"raw_text": "Salario COP 12M a 18M mensual"}
        ]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=dimensions,
            vacancy_dimensions_status="approved",
        )
        assert updated is not None
        salary_artifact = _sample_vacancy_salary(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_salary_normalization",
            return_value=salary_artifact,
        ):
            response = opportunities_api.recompute_vacancy_salary(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_salary_status, "draft")
        self.assertEqual(
            response.vacancy_salary_artifact["contract_version"],
            "vacancy_salary_normalization.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_salary_status"], "draft")

    def test_recompute_vacancy_salary_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con salario.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_salary_normalization",
            side_effect=VacancySalaryNormalizationError("Step 3.1 requires salary raw text"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_salary(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 3.1 requires salary raw text", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_salary_status"], "error")

    def test_recompute_vacancy_salary_without_salary_signal_stays_draft(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante sin salario publicado.",
        )
        opportunity_id = created["opportunity_id"]
        dimensions = _sample_vacancy_dimensions(opportunity_id)
        dimensions["vacancy_dimensions"]["work_conditions"] = [
            {"raw_text": "Modalidad: Hibrido 3x2"},
            {"raw_text": "Ubicacion: Bogota"},
        ]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=dimensions,
            vacancy_dimensions_status="approved",
        )
        assert updated is not None

        response = opportunities_api.recompute_vacancy_salary(
            person_id="p-001",
            opportunity_id=opportunity_id,
            _=self.session,
            settings=get_settings(),
        )

        self.assertEqual(response.vacancy_salary_status, "draft")
        self.assertEqual(
            response.vacancy_salary_artifact["contract_version"],
            "vacancy_salary_normalization.v1",
        )
        self.assertEqual(response.vacancy_salary_artifact["salary"]["raw_text"], "")
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_salary_status"], "draft")

    def test_recompute_vacancy_comparable_conditions_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Gerente de Tecnologia",
            company="Asssiprex",
            location="Bogota, Colombia",
            raw_text="Vacante con modalidad, salario y tipo de contrato.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
            vacancy_salary_artifact=_sample_vacancy_salary(opportunity_id),
            vacancy_salary_status="approved",
        )
        assert updated is not None
        artifact = _sample_vacancy_comparable_conditions(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_comparable_conditions",
            return_value=artifact,
        ):
            response = opportunities_api.recompute_vacancy_comparable_conditions(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
            )

        self.assertEqual(response.vacancy_comparable_conditions_status, "draft")
        self.assertEqual(
            response.vacancy_comparable_conditions_artifact["contract_version"],
            "vacancy_comparable_conditions.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_comparable_conditions_status"], "draft")

    def test_recompute_vacancy_comparable_conditions_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Gerente de Tecnologia",
            company="Asssiprex",
            location="Bogota, Colombia",
            raw_text="Vacante con modalidad y salario.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_comparable_conditions",
            side_effect=VacancyComparableConditionsBuildError(
                "C1 requires a valid vacancy_dimensions.v2 artifact."
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_comparable_conditions(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("C1 requires a valid vacancy_dimensions.v2 artifact.", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_comparable_conditions_status"], "error")

    def test_recompute_candidate_preference_checks_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Gerente de Tecnologia",
            company="Asssiprex",
            location="Bogota, Colombia",
            raw_text="Vacante comparable.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_comparable_conditions_artifact=_sample_vacancy_comparable_conditions(opportunity_id),
            vacancy_comparable_conditions_status="approved",
        )
        assert updated is not None
        person_store.update_candidate_preference_profile(
            "p-001",
            artifact={
                "contract_version": "candidate_preference_profile.v1",
                "person_id": "p-001",
                "generated_at": "2026-04-21T10:02:35Z",
                "comparable_preferences": {
                    "current_location": "Bogota, Colombia",
                    "accepted_locations": ["Bogota"],
                    "accepted_modalities": ["hybrid", "remote"],
                    "contract_types_accepted": ["indefinite"],
                    "salary_expectation": {
                        "min": 10000000,
                        "max": 14000000,
                        "currency": "COP",
                        "period": "monthly",
                    },
                    "relocation_willingness": "no",
                    "travel_willingness": "yes",
                    "hard_constraints": [],
                },
                "warnings": [],
            },
            status="approved",
        )
        artifact = _sample_candidate_preference_checks("p-001", opportunity_id)

        with patch.object(
            opportunities_api,
            "build_candidate_preference_checks",
            return_value=artifact,
        ):
            response = opportunities_api.recompute_candidate_preference_checks(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
            )

        self.assertEqual(response.candidate_preference_checks_status, "draft")
        self.assertEqual(
            response.candidate_preference_checks_artifact["contract_version"],
            "candidate_preference_checks.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["candidate_preference_checks_status"], "draft")

    def test_recompute_candidate_preference_checks_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Gerente de Tecnologia",
            company="Asssiprex",
            location="Bogota, Colombia",
            raw_text="Vacante comparable.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_comparable_conditions_artifact=_sample_vacancy_comparable_conditions(opportunity_id),
            vacancy_comparable_conditions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_candidate_preference_checks",
            side_effect=CandidatePreferenceChecksBuildError(
                "C2 requires a valid candidate_preference_profile.v1 artifact."
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_candidate_preference_checks(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn(
            "C2 requires a valid candidate_preference_profile.v1 artifact.",
            str(ctx.exception.detail),
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["candidate_preference_checks_status"], "error")

    def test_recompute_vacancy_fit_presentation_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con matriz profesional.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
        )
        assert updated is not None
        artifact = _sample_vacancy_fit_presentation(opportunity_id)

        with patch.object(opportunities_api, "build_vacancy_fit_presentation", return_value=artifact):
            response = opportunities_api.recompute_vacancy_fit_presentation(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
            )

        self.assertEqual(response.vacancy_fit_presentation_status, "draft")
        self.assertEqual(
            response.vacancy_fit_presentation_artifact["contract_version"],
            "vacancy_fit_presentation.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_fit_presentation_status"], "draft")

    def test_recompute_vacancy_fit_presentation_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con matriz profesional.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_fit_presentation",
            side_effect=VacancyFitPresentationBuildError(
                "P1 requires a valid vacancy_evidence_adjudication.v1 artifact."
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_fit_presentation(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn(
            "P1 requires a valid vacancy_evidence_adjudication.v1 artifact.",
            str(ctx.exception.detail),
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_fit_presentation_status"], "error")

    def test_recompute_vacancy_dimensions_enriched_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None
        enriched_artifact = _sample_vacancy_dimensions_enriched(opportunity_id)

        with patch.object(
            opportunities_api,
            "enrich_vacancy_dimensions_artifact",
            return_value=enriched_artifact,
        ):
            response = opportunities_api.recompute_vacancy_dimensions_enriched(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
            )

        self.assertEqual(response.vacancy_dimensions_enriched_status, "draft")
        self.assertEqual(
            response.vacancy_dimensions_enriched_artifact["contract_version"],
            "vacancy_dimensions_enriched.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_enriched_status"], "draft")

    def test_recompute_vacancy_dimensions_enriched_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "enrich_vacancy_dimensions_artifact",
            side_effect=VacancyDimensionsEnrichmentError("Step 3.9 produced no enrichable atomic items"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_dimensions_enriched(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 3.9 produced no enrichable atomic items", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_enriched_status"], "error")

    def test_recompute_vacancy_retrieval_queries_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
            vacancy_salary_artifact=_sample_vacancy_salary(opportunity_id),
            vacancy_salary_status="approved",
        )
        assert updated is not None
        queries_artifact = _sample_vacancy_retrieval_queries(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_retrieval_queries",
            return_value=queries_artifact,
        ):
            response = opportunities_api.recompute_vacancy_retrieval_queries(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_retrieval_queries_status, "draft")
        self.assertEqual(
            response.vacancy_retrieval_queries_artifact["contract_version"],
            "vacancy_retrieval_queries.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_queries_status"], "draft")

    def test_recompute_vacancy_retrieval_queries_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_retrieval_queries",
            side_effect=VacancyRetrievalQueriesExtractionError("Step 4 requires a valid vacancy_dimensions_enriched.v1 artifact."),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_retrieval_queries(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 4 requires a valid vacancy_dimensions_enriched.v1 artifact.", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_queries_status"], "error")

    def test_recompute_vacancy_retrieval_evidence_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_queries_artifact=_sample_vacancy_retrieval_queries(opportunity_id),
            vacancy_retrieval_queries_status="approved",
        )
        assert updated is not None
        evidence_artifact = _sample_vacancy_retrieval_evidence(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_retrieval_evidence",
            return_value=evidence_artifact,
        ):
            response = opportunities_api.recompute_vacancy_retrieval_evidence(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_retrieval_evidence_status, "draft")
        self.assertEqual(
            response.vacancy_retrieval_evidence_artifact["contract_version"],
            "vacancy_retrieval_evidence.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_evidence_status"], "draft")

    def test_recompute_vacancy_retrieval_evidence_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_queries_artifact=_sample_vacancy_retrieval_queries(opportunity_id),
            vacancy_retrieval_queries_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_retrieval_evidence",
            side_effect=VacancyRetrievalEvidenceBuildError("Step 5 requires an indexed active CV before retrieval can run."),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_retrieval_evidence(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 5 requires an indexed active CV before retrieval can run.", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_evidence_status"], "error")

    def test_recompute_vacancy_evidence_analysis_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con evidencia de retrieval.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_evidence_artifact=_sample_vacancy_retrieval_evidence(opportunity_id),
            vacancy_retrieval_evidence_status="approved",
        )
        assert updated is not None
        analysis_artifact = _sample_vacancy_evidence_analysis(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_analysis",
            return_value=analysis_artifact,
        ):
            response = opportunities_api.recompute_vacancy_evidence_analysis(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
            )

        self.assertEqual(response.vacancy_evidence_analysis_status, "draft")
        self.assertEqual(
            response.vacancy_evidence_analysis_artifact["contract_version"],
            "vacancy_evidence_analysis.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_evidence_analysis_status"], "draft")

    def test_recompute_vacancy_evidence_analysis_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con evidencia de retrieval.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_evidence_artifact=_sample_vacancy_retrieval_evidence(opportunity_id),
            vacancy_retrieval_evidence_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_analysis",
            side_effect=VacancyEvidenceAnalysisBuildError("Step 6 requires at least one retrieval match in Step 5 evidence."),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_evidence_analysis(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 6 requires at least one retrieval match in Step 5 evidence.", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_evidence_analysis_status"], "error")

    def test_recompute_vacancy_evidence_adjudication_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con adjudicacion grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None
        adjudication_artifact = _sample_vacancy_evidence_adjudication(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_adjudication",
            return_value=adjudication_artifact,
        ):
            response = opportunities_api.recompute_vacancy_evidence_adjudication(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_evidence_adjudication_status, "draft")
        self.assertEqual(
            response.vacancy_evidence_adjudication_artifact["contract_version"],
            "vacancy_evidence_adjudication.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_evidence_adjudication_status"], "draft")

    def test_recompute_vacancy_evidence_adjudication_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con adjudicacion grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_adjudication",
            side_effect=VacancyEvidenceAdjudicationBuildError(
                "Step 6.5 requires a valid vacancy_dimensions_enriched.v1 artifact."
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_evidence_adjudication(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn(
            "Step 6.5 requires a valid vacancy_dimensions_enriched.v1 artifact.",
            str(ctx.exception.detail),
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_evidence_adjudication_status"], "error")

    def test_recompute_vacancy_alignment_summary_v2_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con resumen grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
        )
        assert updated is not None
        summary_v2_artifact = _sample_vacancy_alignment_summary_v2(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary_v2",
            return_value=summary_v2_artifact,
        ):
            response = opportunities_api.recompute_vacancy_alignment_summary_v2(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
            )

        self.assertEqual(response.vacancy_alignment_summary_v2_status, "draft")
        self.assertEqual(
            response.vacancy_alignment_summary_v2_artifact["contract_version"],
            "vacancy_alignment_summary.v2",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_summary_v2_status"], "draft")

    def test_recompute_vacancy_alignment_summary_v2_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con resumen grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary_v2",
            side_effect=VacancyAlignmentSummaryV2BuildError(
                "Step 7 v2 requires a valid vacancy_evidence_adjudication.v1 artifact."
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_alignment_summary_v2(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn(
            "Step 7 v2 requires a valid vacancy_evidence_adjudication.v1 artifact.",
            str(ctx.exception.detail),
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_summary_v2_status"], "error")

    def test_recompute_vacancy_alignment_report_v2_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con reporte grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
            vacancy_alignment_summary_v2_artifact=_sample_vacancy_alignment_summary_v2(opportunity_id),
            vacancy_alignment_summary_v2_status="approved",
            vacancy_fit_presentation_artifact=_sample_vacancy_fit_presentation(opportunity_id),
            vacancy_fit_presentation_status="approved",
            candidate_preference_checks_artifact=_sample_candidate_preference_checks("p-001", opportunity_id),
            candidate_preference_checks_status="approved",
        )
        assert updated is not None
        report_artifact = _sample_vacancy_alignment_report_v2(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_alignment_report_v2",
            return_value=report_artifact,
        ):
            response = opportunities_api.recompute_vacancy_alignment_report_v2(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        self.assertEqual(response.vacancy_alignment_report_v2_status, "draft")
        self.assertEqual(
            response.vacancy_alignment_report_v2_artifact["contract_version"],
            "vacancy_alignment_report.v2",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_report_v2_status"], "draft")

    def test_recompute_vacancy_alignment_report_v2_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con reporte grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
            vacancy_alignment_summary_v2_artifact=_sample_vacancy_alignment_summary_v2(opportunity_id),
            vacancy_alignment_summary_v2_status="approved",
            vacancy_fit_presentation_artifact=_sample_vacancy_fit_presentation(opportunity_id),
            vacancy_fit_presentation_status="approved",
            candidate_preference_checks_artifact=_sample_candidate_preference_checks("p-001", opportunity_id),
            candidate_preference_checks_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_alignment_report_v2",
            side_effect=VacancyAlignmentReportV2BuildError(
                "Step 8 v2 requires a valid vacancy_alignment_summary.v2 artifact."
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_alignment_report_v2(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn(
            "Step 8 v2 requires a valid vacancy_alignment_summary.v2 artifact.",
            str(ctx.exception.detail),
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_report_v2_status"], "error")

    def test_recompute_vacancy_alignment_summary_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con resumen de alineacion.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None
        summary_artifact = _sample_vacancy_alignment_summary(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary",
            return_value=summary_artifact,
        ):
            response = opportunities_api.recompute_vacancy_alignment_summary(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
            )

        self.assertEqual(response.vacancy_alignment_summary_status, "draft")
        self.assertEqual(
            response.vacancy_alignment_summary_artifact["contract_version"],
            "vacancy_alignment_summary.v1",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_summary_status"], "draft")

    def test_recompute_vacancy_alignment_summary_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con resumen de alineacion.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary",
            side_effect=VacancyAlignmentSummaryBuildError("Step 7 requires a valid vacancy_evidence_analysis.v1 artifact."),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_alignment_summary(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 7 requires a valid vacancy_evidence_analysis.v1 artifact.", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_summary_status"], "error")

    def test_recompute_vacancy_alignment_report_success_sets_draft_artifact(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con reporte final.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
            vacancy_alignment_summary_artifact=_sample_vacancy_alignment_summary(opportunity_id),
            vacancy_alignment_summary_status="approved",
        )
        assert updated is not None
        report_artifact = _sample_vacancy_alignment_report(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_alignment_report",
            return_value=report_artifact,
        ) as extract_report_mock:
            response = opportunities_api.recompute_vacancy_alignment_report(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
            )

        self.assertEqual(response.vacancy_alignment_report_status, "draft")
        self.assertEqual(
            response.vacancy_alignment_report_artifact["contract_version"],
            "vacancy_alignment_report.v1",
        )
        self.assertEqual(
            extract_report_mock.call_args.kwargs["person"]["person_id"],
            "p-001",
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_report_status"], "draft")

    def test_recompute_vacancy_alignment_report_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con reporte final.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
            vacancy_alignment_summary_artifact=_sample_vacancy_alignment_summary(opportunity_id),
            vacancy_alignment_summary_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_alignment_report",
            side_effect=VacancyAlignmentReportBuildError(
                "Step 8 requires a valid vacancy_alignment_summary.v1 artifact."
            ),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_alignment_report(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn(
            "Step 8 requires a valid vacancy_alignment_summary.v1 artifact.",
            str(ctx.exception.detail),
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_report_status"], "error")

    def test_recompute_vacancy_dimensions_uses_persisted_vacancy_blocks_input(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con condiciones y responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        blocks = _sample_vacancy_blocks(opportunity_id)
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_blocks_artifact=blocks,
            vacancy_blocks_status="approved",
        )
        assert updated is not None
        dimensions = _sample_vacancy_dimensions(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_dimensions",
            return_value=dimensions,
        ) as extract_mock:
            opportunities_api.recompute_vacancy_dimensions(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        kwargs = extract_mock.call_args.kwargs
        self.assertEqual(
            kwargs["vacancy_blocks_artifact"]["flow"]["contract_version"],
            "vacancy_blocks.v2",
        )
        self.assertEqual(kwargs["vacancy_blocks_artifact"]["vacancy_id"], opportunity_id)

    def test_recompute_vacancy_dimensions_failure_sets_error_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con condiciones y responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]

        with patch.object(
            opportunities_api,
            "extract_vacancy_dimensions",
            side_effect=VacancyDimensionsExtractionError("Step 3 requires valid Step 2"),
        ):
            with self.assertRaises(HTTPException) as ctx:
                opportunities_api.recompute_vacancy_dimensions(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Step 3 requires valid Step 2", str(ctx.exception.detail))
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_status"], "error")

    def test_recompute_vacancy_v2_preserves_legacy_vacancy_profile(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con condiciones y responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        legacy_profile = {"must_have": ["Python", "FastAPI"], "nice_to_have": ["AWS"]}
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_profile=legacy_profile,
            vacancy_profile_status="approved",
        )
        assert updated is not None

        blocks = _sample_vacancy_blocks(opportunity_id)
        dimensions = _sample_vacancy_dimensions(opportunity_id)
        with patch.object(opportunities_api, "extract_vacancy_blocks", return_value=blocks):
            opportunities_api.recompute_vacancy_blocks(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )
        with patch.object(opportunities_api, "extract_vacancy_dimensions", return_value=dimensions):
            opportunities_api.recompute_vacancy_dimensions(
                person_id="p-001",
                opportunity_id=opportunity_id,
                _=self.session,
                settings=get_settings(),
            )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_profile"], legacy_profile)
        self.assertEqual(stored["vacancy_profile_status"], "approved")

    def test_vacancy_blocks_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con plataformas y datos.",
        )
        opportunity_id = created["opportunity_id"]
        blocks = _sample_vacancy_blocks(opportunity_id)

        with patch.object(opportunities_api, "extract_vacancy_blocks", return_value=blocks):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_blocks_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_blocks_recompute_started", stages)
        self.assertIn("vacancy_blocks_extracting", stages)
        self.assertIn("vacancy_blocks_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["opportunity"]["vacancy_blocks_status"], "draft")

    def test_vacancy_blocks_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con plataformas y datos.",
        )
        opportunity_id = created["opportunity_id"]

        with patch.object(
            opportunities_api,
            "extract_vacancy_blocks",
            side_effect=VacancyBlocksExtractionError("Step 2 blocked by invalid source"),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_blocks_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn("Step 2 blocked by invalid source", str(error_payload.get("detail", "")))

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_blocks_status"], "error")

    def test_vacancy_dimensions_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con plataformas y datos.",
        )
        opportunity_id = created["opportunity_id"]
        blocks = _sample_vacancy_blocks(opportunity_id)
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_blocks_artifact=blocks,
            vacancy_blocks_status="approved",
        )
        assert updated is not None
        dimensions = _sample_vacancy_dimensions(opportunity_id)

        with patch.object(opportunities_api, "extract_vacancy_dimensions", return_value=dimensions):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_dimensions_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_dimensions_recompute_started", stages)
        self.assertIn("vacancy_dimensions_extracting", stages)
        self.assertIn("vacancy_dimensions_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["opportunity"]["vacancy_dimensions_status"], "draft")

    def test_vacancy_dimensions_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con plataformas y datos.",
        )
        opportunity_id = created["opportunity_id"]

        with patch.object(
            opportunities_api,
            "extract_vacancy_dimensions",
            side_effect=VacancyDimensionsExtractionError("Step 3 blocked by invalid Step 2"),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_dimensions_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn("Step 3 blocked by invalid Step 2", str(error_payload.get("detail", "")))

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_status"], "error")

    def test_vacancy_salary_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con salario.",
        )
        opportunity_id = created["opportunity_id"]
        dimensions = _sample_vacancy_dimensions(opportunity_id)
        dimensions["vacancy_dimensions"]["work_conditions"] = [
            {"raw_text": "Salario COP 12M a 18M mensual"}
        ]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=dimensions,
            vacancy_dimensions_status="approved",
        )
        assert updated is not None
        salary_artifact = _sample_vacancy_salary(opportunity_id)

        with patch.object(opportunities_api, "extract_vacancy_salary_normalization", return_value=salary_artifact):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_salary_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_salary_recompute_started", stages)
        self.assertIn("vacancy_salary_extracting", stages)
        self.assertIn("vacancy_salary_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["vacancy_salary_status"], "draft")

    def test_vacancy_salary_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con salario.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_salary_normalization",
            side_effect=VacancySalaryNormalizationError("Step 3.1 requires salary raw text"),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_salary_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn("Step 3.1 requires salary raw text", str(error_payload.get("detail", "")))

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_salary_status"], "error")

    def test_vacancy_comparable_conditions_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Gerente de Tecnologia",
            company="Asssiprex",
            location="Bogota, Colombia",
            raw_text="Rol con modalidad, salario y contrato.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
            vacancy_salary_artifact=_sample_vacancy_salary(opportunity_id),
            vacancy_salary_status="approved",
        )
        assert updated is not None
        artifact = _sample_vacancy_comparable_conditions(opportunity_id)

        with patch.object(opportunities_api, "build_vacancy_comparable_conditions", return_value=artifact):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_comparable_conditions_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_comparable_conditions_recompute_started", stages)
        self.assertIn("vacancy_comparable_conditions_building", stages)
        self.assertIn("vacancy_comparable_conditions_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_comparable_conditions_status"],
            "draft",
        )

    def test_vacancy_comparable_conditions_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Gerente de Tecnologia",
            company="Asssiprex",
            location="Bogota, Colombia",
            raw_text="Rol con modalidad y salario.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_comparable_conditions",
            side_effect=VacancyComparableConditionsBuildError(
                "C1 requires a valid vacancy_dimensions.v2 artifact."
            ),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_comparable_conditions_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn("C1 requires a valid vacancy_dimensions.v2 artifact.", str(error_payload.get("detail", "")))

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_comparable_conditions_status"], "error")

    def test_candidate_preference_checks_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Gerente de Tecnologia",
            company="Asssiprex",
            location="Bogota, Colombia",
            raw_text="Vacante comparable.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_comparable_conditions_artifact=_sample_vacancy_comparable_conditions(opportunity_id),
            vacancy_comparable_conditions_status="approved",
        )
        assert updated is not None
        person_store.update_candidate_preference_profile(
            "p-001",
            artifact={
                "contract_version": "candidate_preference_profile.v1",
                "person_id": "p-001",
                "generated_at": "2026-04-21T10:02:35Z",
                "comparable_preferences": {
                    "current_location": "Bogota, Colombia",
                    "accepted_locations": ["Bogota"],
                    "accepted_modalities": ["hybrid", "remote"],
                    "contract_types_accepted": ["indefinite"],
                    "salary_expectation": {
                        "min": 10000000,
                        "max": 14000000,
                        "currency": "COP",
                        "period": "monthly",
                    },
                    "relocation_willingness": "no",
                    "travel_willingness": "yes",
                    "hard_constraints": [],
                },
                "warnings": [],
            },
            status="approved",
        )
        artifact = _sample_candidate_preference_checks("p-001", opportunity_id)

        with patch.object(opportunities_api, "build_candidate_preference_checks", return_value=artifact):
            response = asyncio.run(
                opportunities_api.recompute_candidate_preference_checks_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("candidate_preference_checks_recompute_started", stages)
        self.assertIn("candidate_preference_checks_building", stages)
        self.assertIn("candidate_preference_checks_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["candidate_preference_checks_status"],
            "draft",
        )

    def test_candidate_preference_checks_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Gerente de Tecnologia",
            company="Asssiprex",
            location="Bogota, Colombia",
            raw_text="Vacante comparable.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_comparable_conditions_artifact=_sample_vacancy_comparable_conditions(opportunity_id),
            vacancy_comparable_conditions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_candidate_preference_checks",
            side_effect=CandidatePreferenceChecksBuildError(
                "C2 requires a valid candidate_preference_profile.v1 artifact."
            ),
        ):
            response = asyncio.run(
                opportunities_api.recompute_candidate_preference_checks_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn(
            "C2 requires a valid candidate_preference_profile.v1 artifact.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["candidate_preference_checks_status"], "error")

    def test_vacancy_fit_presentation_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con matriz profesional.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
        )
        assert updated is not None
        artifact = _sample_vacancy_fit_presentation(opportunity_id)

        with patch.object(opportunities_api, "build_vacancy_fit_presentation", return_value=artifact):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_fit_presentation_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))

        events = _parse_sse_events(raw)
        stages = [payload["stage"] for event_name, payload in events if event_name == "tool_status"]
        self.assertIn("vacancy_fit_presentation_recompute_started", stages)
        self.assertIn("vacancy_fit_presentation_building", stages)
        self.assertIn("vacancy_fit_presentation_saving", stages)
        complete_payload = next(payload for event_name, payload in events if event_name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_fit_presentation_status"],
            "draft",
        )

    def test_vacancy_fit_presentation_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Backend Engineer",
            company="Acme",
            location="Hybrid",
            raw_text="Vacante con matriz profesional.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_fit_presentation",
            side_effect=VacancyFitPresentationBuildError(
                "P1 requires a valid vacancy_evidence_adjudication.v1 artifact."
            ),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_fit_presentation_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))

        events = _parse_sse_events(raw)
        error_payload = next(payload for event_name, payload in events if event_name == "error")
        self.assertIn(
            "P1 requires a valid vacancy_evidence_adjudication.v1 artifact.",
            error_payload["detail"],
        )
        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_fit_presentation_status"], "error")

    def test_vacancy_dimensions_enriched_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None
        enriched_artifact = _sample_vacancy_dimensions_enriched(opportunity_id)

        with patch.object(opportunities_api, "enrich_vacancy_dimensions_artifact", return_value=enriched_artifact):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_dimensions_enriched_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_dimensions_enriched_recompute_started", stages)
        self.assertIn("vacancy_dimensions_enriched_building", stages)
        self.assertIn("vacancy_dimensions_enriched_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(complete_payload["vacancy_dimensions_enriched_status"], "draft")

    def test_vacancy_dimensions_enriched_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_artifact=_sample_vacancy_dimensions(opportunity_id),
            vacancy_dimensions_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "enrich_vacancy_dimensions_artifact",
            side_effect=VacancyDimensionsEnrichmentError("Step 3.9 produced no enrichable atomic items"),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_dimensions_enriched_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn("Step 3.9 produced no enrichable atomic items", str(error_payload.get("detail", "")))

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_dimensions_enriched_status"], "error")

    def test_vacancy_retrieval_queries_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
            vacancy_salary_artifact=_sample_vacancy_salary(opportunity_id),
            vacancy_salary_status="approved",
        )
        assert updated is not None
        queries_artifact = _sample_vacancy_retrieval_queries(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_retrieval_queries",
            return_value=queries_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_retrieval_queries_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_retrieval_queries_recompute_started", stages)
        self.assertIn("vacancy_retrieval_queries_extracting", stages)
        self.assertIn("vacancy_retrieval_queries_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_retrieval_queries_status"],
            "draft",
        )

    def test_vacancy_retrieval_queries_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_retrieval_queries",
            side_effect=VacancyRetrievalQueriesExtractionError("Step 4 requires a valid vacancy_dimensions_enriched.v1 artifact."),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_retrieval_queries_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn(
            "Step 4 requires a valid vacancy_dimensions_enriched.v1 artifact.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_queries_status"], "error")

    def test_vacancy_retrieval_evidence_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_queries_artifact=_sample_vacancy_retrieval_queries(opportunity_id),
            vacancy_retrieval_queries_status="approved",
        )
        assert updated is not None
        evidence_artifact = _sample_vacancy_retrieval_evidence(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_retrieval_evidence",
            return_value=evidence_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_retrieval_evidence_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_retrieval_evidence_recompute_started", stages)
        self.assertIn("vacancy_retrieval_evidence_building", stages)
        self.assertIn("vacancy_retrieval_evidence_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_retrieval_evidence_status"],
            "draft",
        )

    def test_vacancy_retrieval_evidence_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con responsabilidades.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_queries_artifact=_sample_vacancy_retrieval_queries(opportunity_id),
            vacancy_retrieval_queries_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_retrieval_evidence",
            side_effect=VacancyRetrievalEvidenceBuildError("Step 5 requires an active CV before retrieval can run."),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_retrieval_evidence_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn(
            "Step 5 requires an active CV before retrieval can run.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_retrieval_evidence_status"], "error")

    def test_vacancy_evidence_analysis_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con evidencia recuperada.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_evidence_artifact=_sample_vacancy_retrieval_evidence(opportunity_id),
            vacancy_retrieval_evidence_status="approved",
        )
        assert updated is not None
        analysis_artifact = _sample_vacancy_evidence_analysis(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_analysis",
            return_value=analysis_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_evidence_analysis_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_evidence_analysis_recompute_started", stages)
        self.assertIn("vacancy_evidence_analysis_building", stages)
        self.assertIn("vacancy_evidence_analysis_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_evidence_analysis_status"],
            "draft",
        )

    def test_vacancy_evidence_analysis_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con evidencia recuperada.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_retrieval_evidence_artifact=_sample_vacancy_retrieval_evidence(opportunity_id),
            vacancy_retrieval_evidence_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_analysis",
            side_effect=VacancyEvidenceAnalysisBuildError("Step 6 requires at least one retrieval match in Step 5 evidence."),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_evidence_analysis_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn(
            "Step 6 requires at least one retrieval match in Step 5 evidence.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_evidence_analysis_status"], "error")

    def test_vacancy_evidence_adjudication_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con adjudicacion grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None
        adjudication_artifact = _sample_vacancy_evidence_adjudication(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_adjudication",
            return_value=adjudication_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_evidence_adjudication_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_evidence_adjudication_recompute_started", stages)
        self.assertIn("vacancy_evidence_adjudication_extracting", stages)
        self.assertIn("vacancy_evidence_adjudication_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_evidence_adjudication_status"],
            "draft",
        )

    def test_vacancy_evidence_adjudication_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con adjudicacion grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_dimensions_enriched_artifact=_sample_vacancy_dimensions_enriched(opportunity_id),
            vacancy_dimensions_enriched_status="approved",
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_evidence_adjudication",
            side_effect=VacancyEvidenceAdjudicationBuildError(
                "Step 6.5 requires a valid vacancy_dimensions_enriched.v1 artifact."
            ),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_evidence_adjudication_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn(
            "Step 6.5 requires a valid vacancy_dimensions_enriched.v1 artifact.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_evidence_adjudication_status"], "error")

    def test_vacancy_alignment_summary_v2_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con resumen grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
        )
        assert updated is not None
        summary_v2_artifact = _sample_vacancy_alignment_summary_v2(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary_v2",
            return_value=summary_v2_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_alignment_summary_v2_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_alignment_summary_v2_recompute_started", stages)
        self.assertIn("vacancy_alignment_summary_v2_building", stages)
        self.assertIn("vacancy_alignment_summary_v2_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_alignment_summary_v2_status"],
            "draft",
        )

    def test_vacancy_alignment_summary_v2_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con resumen grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary_v2",
            side_effect=VacancyAlignmentSummaryV2BuildError(
                "Step 7 v2 requires a valid vacancy_evidence_adjudication.v1 artifact."
            ),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_alignment_summary_v2_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn(
            "Step 7 v2 requires a valid vacancy_evidence_adjudication.v1 artifact.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_summary_v2_status"], "error")

    def test_vacancy_alignment_report_v2_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con reporte grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
            vacancy_alignment_summary_v2_artifact=_sample_vacancy_alignment_summary_v2(opportunity_id),
            vacancy_alignment_summary_v2_status="approved",
            vacancy_fit_presentation_artifact=_sample_vacancy_fit_presentation(opportunity_id),
            vacancy_fit_presentation_status="approved",
            candidate_preference_checks_artifact=_sample_candidate_preference_checks("p-001", opportunity_id),
            candidate_preference_checks_status="approved",
        )
        assert updated is not None
        report_artifact = _sample_vacancy_alignment_report_v2(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_alignment_report_v2",
            return_value=report_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_alignment_report_v2_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_alignment_report_v2_recompute_started", stages)
        self.assertIn("vacancy_alignment_report_v2_extracting", stages)
        self.assertIn("vacancy_alignment_report_v2_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_alignment_report_v2_status"],
            "draft",
        )

    def test_vacancy_alignment_report_v2_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con reporte grounded.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
            vacancy_evidence_adjudication_artifact=_sample_vacancy_evidence_adjudication(opportunity_id),
            vacancy_evidence_adjudication_status="approved",
            vacancy_alignment_summary_v2_artifact=_sample_vacancy_alignment_summary_v2(opportunity_id),
            vacancy_alignment_summary_v2_status="approved",
            vacancy_fit_presentation_artifact=_sample_vacancy_fit_presentation(opportunity_id),
            vacancy_fit_presentation_status="approved",
            candidate_preference_checks_artifact=_sample_candidate_preference_checks("p-001", opportunity_id),
            candidate_preference_checks_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_alignment_report_v2",
            side_effect=VacancyAlignmentReportV2BuildError(
                "Step 8 v2 requires a valid vacancy_alignment_summary.v2 artifact."
            ),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_alignment_report_v2_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                    settings=get_settings(),
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn(
            "Step 8 v2 requires a valid vacancy_alignment_summary.v2 artifact.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_report_v2_status"], "error")

    def test_vacancy_alignment_summary_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con resumen de alineacion.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None
        summary_artifact = _sample_vacancy_alignment_summary(opportunity_id)

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary",
            return_value=summary_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_alignment_summary_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_alignment_summary_recompute_started", stages)
        self.assertIn("vacancy_alignment_summary_building", stages)
        self.assertIn("vacancy_alignment_summary_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_alignment_summary_status"],
            "draft",
        )

    def test_vacancy_alignment_summary_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con resumen de alineacion.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "build_vacancy_alignment_summary",
            side_effect=VacancyAlignmentSummaryBuildError("Step 7 requires a valid vacancy_evidence_analysis.v1 artifact."),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_alignment_summary_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn(
            "Step 7 requires a valid vacancy_evidence_analysis.v1 artifact.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_summary_status"], "error")

    def test_vacancy_alignment_report_stream_emits_stages_and_message_complete(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con reporte final de alineacion.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
            vacancy_alignment_summary_artifact=_sample_vacancy_alignment_summary(opportunity_id),
            vacancy_alignment_summary_status="approved",
        )
        assert updated is not None
        report_artifact = _sample_vacancy_alignment_report(opportunity_id)

        with patch.object(
            opportunities_api,
            "extract_vacancy_alignment_report",
            return_value=report_artifact,
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_alignment_report_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        stages = [payload.get("stage", "") for name, payload in events if name == "tool_status"]
        self.assertIn("vacancy_alignment_report_recompute_started", stages)
        self.assertIn("vacancy_alignment_report_extracting", stages)
        self.assertIn("vacancy_alignment_report_saving", stages)
        complete_payload = next(payload for name, payload in events if name == "message_complete")
        self.assertEqual(
            complete_payload["opportunity"]["vacancy_alignment_report_status"],
            "draft",
        )

    def test_vacancy_alignment_report_stream_emits_error_and_marks_status(self) -> None:
        created = opportunity_store.import_text_opportunity(
            person_id="p-001",
            title="Platform Engineer",
            company="Acme",
            location="Remote",
            raw_text="Rol con reporte final de alineacion.",
        )
        opportunity_id = created["opportunity_id"]
        updated = opportunity_store.update_opportunity(
            person_id="p-001",
            opportunity_id=opportunity_id,
            status=None,
            notes=None,
            vacancy_evidence_analysis_artifact=_sample_vacancy_evidence_analysis(opportunity_id),
            vacancy_evidence_analysis_status="approved",
            vacancy_alignment_summary_artifact=_sample_vacancy_alignment_summary(opportunity_id),
            vacancy_alignment_summary_status="approved",
        )
        assert updated is not None

        with patch.object(
            opportunities_api,
            "extract_vacancy_alignment_report",
            side_effect=VacancyAlignmentReportBuildError(
                "Step 8 requires a valid vacancy_alignment_summary.v1 artifact."
            ),
        ):
            response = asyncio.run(
                opportunities_api.recompute_vacancy_alignment_report_stream(
                    person_id="p-001",
                    opportunity_id=opportunity_id,
                    _=self.session,
                )
            )
            raw = asyncio.run(_collect_sse_text(response))
            events = _parse_sse_events(raw)

        names = [name for name, _ in events]
        self.assertIn("tool_status", names)
        self.assertIn("error", names)
        error_payload = next(payload for name, payload in events if name == "error")
        self.assertIn(
            "Step 8 requires a valid vacancy_alignment_summary.v1 artifact.",
            str(error_payload.get("detail", "")),
        )

        stored = opportunity_store.find_opportunity("p-001", opportunity_id)
        assert stored is not None
        self.assertEqual(stored["vacancy_alignment_report_status"], "error")


if __name__ == "__main__":
    unittest.main()
