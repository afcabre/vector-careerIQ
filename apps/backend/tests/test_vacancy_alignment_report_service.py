import unittest
from unittest.mock import patch

from app.services.prompt_config_store import (
    FLOW_GUARDRAILS_CORE,
    FLOW_SYSTEM_IDENTITY,
    FLOW_TASK_VACANCY_ALIGNMENT_REPORT,
)
from app.services.vacancy_alignment_report_contract import CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT
from app.services.vacancy_alignment_report_service import (
    VacancyAlignmentReportBuildError,
    extract_vacancy_alignment_report,
)


def _person() -> dict[str, object]:
    return {
        "person_id": "p-001",
        "full_name": "Maria Gomez",
        "target_roles": ["Senior Data Analyst"],
        "location": "Bogota",
        "years_experience": 6,
        "skills": ["Python", "SQL", "Power BI"],
        "salary_expectation_min": 12000000,
        "salary_expectation_max": 16000000,
        "salary_currency": "COP",
        "salary_period": "monthly",
        "culture_preferences": ["colaboracion", "aprendizaje"],
        "cultural_fit_preferences": {},
        "culture_preferences_notes": "Busca liderazgo claro.",
    }


def _opportunity() -> dict[str, object]:
    return {
        "opportunity_id": "o-r-001",
        "person_id": "p-001",
        "title": "Senior Data Analyst",
        "company": "Acme",
        "location": "Bogota",
        "source_url": "https://example.com/jobs/da-1",
        "snapshot_raw_text": "Rol senior con Python, SQL y Power BI.",
        "vacancy_dimensions_artifact": {
            "contract_version": "vacancy_dimensions.v2",
            "vacancy_id": "o-r-001",
        },
        "vacancy_salary_artifact": {
            "contract_version": "vacancy_salary_normalization.v1",
            "vacancy_id": "o-r-001",
        },
    }


def _alignment_summary() -> dict[str, object]:
    return {
        "contract_version": "vacancy_alignment_summary.v1",
        "vacancy_id": "o-r-001",
        "generated_at": "2026-04-24T10:38:00Z",
        "source_artifact_version": "vacancy_evidence_analysis.v1",
        "thresholds": {
            "strong_min": 0.75,
            "useful_min": 0.45,
            "review_min": 0.30,
        },
        "summary": {
            "overall": {
                "total_items": 2,
                "strong_evidence_count": 1,
                "useful_evidence_count": 1,
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
                    "total_items": 1,
                    "strong_evidence_count": 0,
                    "useful_evidence_count": 1,
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
                    "item_id": "resp_1",
                    "item_index": 0,
                    "raw_text": "Liderar backlog de analitica",
                    "item_status": "strong_evidence",
                    "best_score": 0.84,
                }
            ],
            "gaps": [],
            "review_items": [],
        },
    }


def _evidence_analysis() -> dict[str, object]:
    return {
        "contract_version": "vacancy_evidence_analysis.v1",
        "vacancy_id": "o-r-001",
        "generated_at": "2026-04-24T10:37:00Z",
        "thresholds": {
            "strong_min": 0.75,
            "useful_min": 0.45,
            "review_min": 0.30,
        },
        "analysis": {
            "responsibilities": [
                {
                    "item_id": "resp_1",
                    "item_index": 0,
                    "group_code": "resp",
                    "raw_text": "Liderar backlog de analitica",
                    "item_status": "strong_evidence",
                    "best_score": 0.84,
                    "raw_match_count": 1,
                    "accepted_match_count": 1,
                    "discarded_match_count": 0,
                    "distinct_query_hits": 1,
                    "best_evidence": [
                        {
                            "source_ref": "cv:chunk:1",
                            "snippet": "Lidere backlog y priorizacion trimestral.",
                            "best_score": 0.84,
                            "query_texts": ["liderazgo de backlog"],
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
            "required_criteria": [
                {
                    "item_id": "req_1",
                    "item_index": 1,
                    "group_code": "req",
                    "raw_text": "Python avanzado",
                    "item_status": "useful_evidence",
                    "best_score": 0.51,
                    "raw_match_count": 1,
                    "accepted_match_count": 1,
                    "discarded_match_count": 0,
                    "distinct_query_hits": 1,
                    "best_evidence": [
                        {
                            "source_ref": "cv:chunk:2",
                            "snippet": "Desarrollo de modelos en Python.",
                            "best_score": 0.51,
                            "query_texts": ["experiencia desarrollando soluciones en Python"],
                            "query_indexes": [1],
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
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": [],
        },
    }


class VacancyAlignmentReportServiceTests(unittest.TestCase):
    def test_extract_success_returns_normalized_report_contract(self) -> None:
        llm_response = (
            "{"
            "\"report\":{"
            "\"executive_summary\":\"Buen ajuste general con una brecha puntual en cloud.\","
            "\"decision_table\":{\"alineacion_general\":{\"resultado\":\"Avanzar con reservas\",\"descripcion_corta\":\"Buen fit con una brecha visible.\"}},"
            "\"vacancy_fit_matrix\":[{\"criterio\":\"Python avanzado\",\"categoria\":\"Herramientas\",\"origen_del_criterio\":\"Vacante obligatoria\",\"estado\":\"🟢 Cumple\",\"lo_que_solicita_la_vacante\":\"Python avanzado\",\"evidencia_del_candidato\":\"Desarrollo de modelos en Python.\",\"descripcion_corta\":\"Evidencia semantica util.\"}],"
            "\"candidate_preference_matrix\":[{\"criterio\":\"Modalidad\",\"categoria\":\"Condiciones laborales\",\"origen_del_criterio\":\"Preferencia del candidato\",\"estado\":\"⚪ Sin informacion\",\"lo_que_ofrece_o_define_la_vacante\":\"La vacante no lo especifica\",\"preferencia_o_condicion_del_candidato\":\"Prefiere remoto o hibrido\",\"descripcion_corta\":\"Falta definicion de modalidad.\"}],"
            "\"fit_answer\":\"Encaja con la vacante y conviene avanzar con validacion.\","
            "\"strengths\":[\"Experiencia demostrada en Python y backlog.\"],"
            "\"gaps\":[\"Cloud no esta demostrado.\"],"
            "\"preference_conflicts\":[],"
            "\"improvement_actions\":{\"reinforce_in_cv_or_profile\":[\"Resaltar impacto en Python.\"],\"validate_with_recruiter\":[\"Confirmar stack cloud.\"],\"application_narrative\":[\"Conectar backlog con resultados de negocio.\"]},"
            "\"alerts_and_conflicts\":[\"La vacante no aclara modalidad.\"],"
            "\"actionable_conclusion\":{\"final_decision\":\"Avanzar con reservas\",\"main_reason\":\"El core tecnico encaja y la brecha abierta es validable.\",\"recommended_next_step\":\"Validar cloud y modalidad con reclutador.\"}"
            "},"
            "\"rendered_markdown\":\"## Resumen ejecutivo\\n\\nBuen ajuste general.\""
            "}"
        )

        with patch(
            "app.services.vacancy_alignment_report_service.complete_prompt",
            return_value=llm_response,
        ):
            contract = extract_vacancy_alignment_report(
                person=_person(),
                opportunity=_opportunity(),
                vacancy_alignment_summary_artifact=_alignment_summary(),
                vacancy_evidence_analysis_artifact=_evidence_analysis(),
                settings=object(),
            )

        self.assertEqual(contract["contract_version"], CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT)
        self.assertEqual(contract["vacancy_id"], "o-r-001")
        self.assertEqual(contract["person_id"], "p-001")
        self.assertEqual(contract["source_artifacts"]["alignment_summary_version"], "vacancy_alignment_summary.v1")
        self.assertEqual(contract["report"]["vacancy_fit_matrix"][0]["criterio"], "Python avanzado")
        self.assertTrue(contract["rendered_markdown"])

    def test_extract_requires_valid_summary_and_analysis_inputs(self) -> None:
        with self.assertRaises(VacancyAlignmentReportBuildError):
            extract_vacancy_alignment_report(
                person=_person(),
                opportunity=_opportunity(),
                vacancy_alignment_summary_artifact={},
                vacancy_evidence_analysis_artifact=_evidence_analysis(),
                settings=object(),
            )

        with self.assertRaises(VacancyAlignmentReportBuildError):
            extract_vacancy_alignment_report(
                person=_person(),
                opportunity=_opportunity(),
                vacancy_alignment_summary_artifact=_alignment_summary(),
                vacancy_evidence_analysis_artifact={},
                settings=object(),
            )

    def test_extract_uses_dedicated_prompt_flow(self) -> None:
        llm_response = (
            "{"
            "\"report\":{"
            "\"executive_summary\":\"Resumen\","
            "\"decision_table\":{},"
            "\"vacancy_fit_matrix\":[{\"criterio\":\"Python\",\"categoria\":\"Herramientas\",\"origen_del_criterio\":\"Vacante obligatoria\",\"estado\":\"🟢 Cumple\",\"lo_que_solicita_la_vacante\":\"Python\",\"evidencia_del_candidato\":\"Python\",\"descripcion_corta\":\"Directo\"}],"
            "\"candidate_preference_matrix\":[],"
            "\"fit_answer\":\"Si\","
            "\"strengths\":[],"
            "\"gaps\":[],"
            "\"preference_conflicts\":[],"
            "\"improvement_actions\":{},"
            "\"alerts_and_conflicts\":[],"
            "\"actionable_conclusion\":{}"
            "},"
            "\"rendered_markdown\":\"## Resumen ejecutivo\\n\\nTexto\""
            "}"
        )

        with patch(
            "app.services.vacancy_alignment_report_service.build_prompt_text",
            side_effect=lambda flow_key, context, fallback: f"prompt::{flow_key}",
        ) as prompt_builder_mock:
            with patch(
                "app.services.vacancy_alignment_report_service.complete_prompt",
                return_value=llm_response,
            ) as complete_prompt_mock:
                extract_vacancy_alignment_report(
                    person=_person(),
                    opportunity=_opportunity(),
                    vacancy_alignment_summary_artifact=_alignment_summary(),
                    vacancy_evidence_analysis_artifact=_evidence_analysis(),
                    settings=object(),
                )

        flow_keys = [call.kwargs["flow_key"] for call in prompt_builder_mock.call_args_list]
        self.assertIn(FLOW_GUARDRAILS_CORE, flow_keys)
        self.assertIn(FLOW_SYSTEM_IDENTITY, flow_keys)
        self.assertIn(FLOW_TASK_VACANCY_ALIGNMENT_REPORT, flow_keys)
        task_call = next(
            call for call in prompt_builder_mock.call_args_list
            if call.kwargs["flow_key"] == FLOW_TASK_VACANCY_ALIGNMENT_REPORT
        )
        self.assertIn("alignment_summary_json", task_call.kwargs["context"])
        self.assertIn("evidence_analysis_json", task_call.kwargs["context"])
        self.assertEqual(complete_prompt_mock.call_args.kwargs["flow_key"], FLOW_TASK_VACANCY_ALIGNMENT_REPORT)
        self.assertIn("prompt::guardrails_core", complete_prompt_mock.call_args.args[0])
        self.assertIn("prompt::system_identity", complete_prompt_mock.call_args.args[0])

    def test_extract_invalid_json_raises_controlled_error(self) -> None:
        with patch(
            "app.services.vacancy_alignment_report_service.complete_prompt",
            return_value="not-json",
        ):
            with self.assertRaises(VacancyAlignmentReportBuildError):
                extract_vacancy_alignment_report(
                    person=_person(),
                    opportunity=_opportunity(),
                    vacancy_alignment_summary_artifact=_alignment_summary(),
                    vacancy_evidence_analysis_artifact=_evidence_analysis(),
                    settings=object(),
                )


if __name__ == "__main__":
    unittest.main()
