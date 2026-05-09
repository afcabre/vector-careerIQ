import unittest
from unittest.mock import patch

from app.services.prompt_config_store import FLOW_TASK_VACANCY_ALIGNMENT_REPORT_V2
from app.services.vacancy_alignment_report_v2_contract import CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT_V2
from app.services.vacancy_alignment_report_v2_service import (
    VacancyAlignmentReportV2BuildError,
    extract_vacancy_alignment_report_v2,
)


def _person() -> dict[str, object]:
    return {
        "person_id": "p-001",
        "full_name": "Maria Gomez",
        "target_roles": ["Director TI"],
        "location": "Bogota",
        "years_experience": 20,
        "skills": ["Transformacion digital", "Arquitectura"],
        "salary_expectation_min": 18000000,
        "salary_expectation_max": 25000000,
        "salary_currency": "COP",
        "salary_period": "monthly",
        "culture_preferences": ["claridad", "impacto"],
        "cultural_fit_preferences": {},
        "culture_preferences_notes": "Busca liderazgo claro.",
    }


def _opportunity() -> dict[str, object]:
    return {
        "opportunity_id": "o-r2-001",
        "person_id": "p-001",
        "title": "Lider Estrategico en Transformacion Digital",
        "company": "Acme",
        "location": "Bogota",
        "source_url": "https://example.com/jobs/1",
        "snapshot_raw_text": "Rol de liderazgo tecnico y transformacion digital.",
        "vacancy_dimensions_artifact": {
            "contract_version": "vacancy_dimensions.v2",
            "vacancy_id": "o-r2-001",
        },
        "vacancy_salary_artifact": {
            "contract_version": "vacancy_salary_normalization.v1",
            "vacancy_id": "o-r2-001",
        },
    }


def _adjudication() -> dict[str, object]:
    return {
        "contract_version": "vacancy_evidence_adjudication.v1",
        "vacancy_id": "o-r2-001",
        "generated_at": "2026-05-08T18:00:00Z",
        "items": [
            {
                "item_id": "req_1",
                "item_index": 0,
                "group": "required_criteria",
                "group_code": "req",
                "raw_text": "Minimo 5 anos de experiencia profesional",
                "criterion_type": "years_experience",
                "priority": "important",
                "alignment_status": "direct",
                "evidence_strength": "high",
                "proof_summary": "El CV declara 20 anos de experiencia profesional.",
                "best_supporting_evidence": [],
                "weak_or_discarded_evidence": [],
                "limitations": [],
                "candidate_risk": "low",
                "cv_improvement_opportunity": "",
                "confidence": "high",
            },
            {
                "item_id": "des_1",
                "item_index": 1,
                "group": "desirable_criteria",
                "group_code": "des",
                "raw_text": "Certificacion PMP o Scrum",
                "criterion_type": "certification",
                "priority": "desirable",
                "alignment_status": "not_evidenced",
                "evidence_strength": "none",
                "proof_summary": "No se observa certificacion formal en los snippets.",
                "best_supporting_evidence": [],
                "weak_or_discarded_evidence": [],
                "limitations": [],
                "candidate_risk": "low",
                "cv_improvement_opportunity": "",
                "confidence": "medium",
            },
        ],
        "warnings": [],
    }


def _summary_v2() -> dict[str, object]:
    return {
        "contract_version": "vacancy_alignment_summary.v2",
        "vacancy_id": "o-r2-001",
        "generated_at": "2026-05-08T18:01:00Z",
        "source_artifact_version": "vacancy_evidence_adjudication.v1",
        "summary": {
            "overall": {
                "total_items": 2,
                "direct_count": 1,
                "partial_count": 0,
                "indirect_count": 0,
                "not_evidenced_count": 1,
                "conflict_count": 0,
                "not_applicable_count": 0,
            },
            "groups": {
                "required_criteria": {
                    "total_items": 1,
                    "direct_count": 1,
                    "partial_count": 0,
                    "indirect_count": 0,
                    "not_evidenced_count": 0,
                    "conflict_count": 0,
                    "not_applicable_count": 0,
                },
                "responsibilities": {
                    "total_items": 0,
                    "direct_count": 0,
                    "partial_count": 0,
                    "indirect_count": 0,
                    "not_evidenced_count": 0,
                    "conflict_count": 0,
                    "not_applicable_count": 0,
                },
                "desirable_criteria": {
                    "total_items": 1,
                    "direct_count": 0,
                    "partial_count": 0,
                    "indirect_count": 0,
                    "not_evidenced_count": 1,
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
            "strengths": [],
            "gaps": [],
            "review_items": [],
            "risks": [],
        },
    }


def _analysis() -> dict[str, object]:
    return {
        "contract_version": "vacancy_evidence_analysis.v1",
        "vacancy_id": "o-r2-001",
        "generated_at": "2026-05-08T17:59:00Z",
        "thresholds": {
            "strong_min": 0.75,
            "useful_min": 0.45,
            "review_min": 0.30,
        },
        "analysis": {
            "responsibilities": [],
            "required_criteria": [],
            "desirable_criteria": [],
            "benefits": [],
            "about_the_company": [],
            "work_conditions": [],
        },
    }


class VacancyAlignmentReportV2ServiceTests(unittest.TestCase):
    def test_extract_success_returns_normalized_report_contract(self) -> None:
        llm_response = (
            "{"
            "\"report\":{"
            "\"executive_summary\":{\"fit_level\":\"medio_alto\",\"final_recommendation\":\"Avanzar con reservas\",\"summary\":\"Buen ajuste general con un deseable abierto.\",\"main_strength\":\"La trayectoria profesional cubre el requisito clave.\",\"main_gap_or_risk\":\"No se evidencia certificacion formal.\",\"confidence\":\"media\"},"
            "\"decision_table\":{\"alineacion_general\":{\"resultado\":\"🟡 Parcial\",\"descripcion_corta\":\"Buen ajuste con un deseable no evidenciado.\"},\"recomendacion\":{\"resultado\":\"Avanzar con reservas\",\"descripcion_corta\":\"Avanzar, validando el peso real del deseable.\"}},"
            "\"vacancy_fit_matrix\":["
            "{\"item_id\":\"req_1\",\"criterio\":\"Minimo 5 anos de experiencia profesional\",\"categoria\":\"Experiencia\",\"origen_del_criterio\":\"Vacante obligatoria\",\"prioridad\":\"Importante\",\"estado\":\"🟢 Cumple\",\"lo_que_solicita_la_vacante\":\"Minimo 5 anos de experiencia profesional\",\"evidencia_del_candidato\":\"El CV declara 20 anos de experiencia profesional.\",\"tipo_de_evidencia\":\"directa\",\"fuerza_de_evidencia\":\"alta\",\"descripcion_corta\":\"El requisito queda cubierto.\",\"riesgo_para_la_postulacion\":\"bajo\",\"fuentes\":[\"cv:chunk:1\"]},"
            "{\"item_id\":\"des_1\",\"criterio\":\"Certificacion PMP o Scrum\",\"categoria\":\"Certificaciones\",\"origen_del_criterio\":\"Vacante deseable\",\"prioridad\":\"Deseable\",\"estado\":\"🔵 Deseable no evidenciado\",\"lo_que_solicita_la_vacante\":\"Certificacion PMP o Scrum\",\"evidencia_del_candidato\":\"No se observa certificacion formal en los snippets.\",\"tipo_de_evidencia\":\"no evidenciada\",\"fuerza_de_evidencia\":\"ninguna\",\"descripcion_corta\":\"Es un deseable no demostrado.\",\"riesgo_para_la_postulacion\":\"bajo\",\"fuentes\":[]}"
            "],"
            "\"candidate_preference_matrix\":[],"
            "\"fit_answer\":{\"encaja\":\"sí\",\"respuesta_para_el_candidato\":\"La postulacion es defendible si el deseable no es bloqueante.\"},"
            "\"strengths\":[{\"fortaleza\":\"Trayectoria profesional extensa\",\"por_que_importa\":\"Cubre el requisito base del rol.\",\"evidencia\":\"20 anos de experiencia profesional.\"}],"
            "\"gaps\":[{\"brecha\":\"No se evidencia certificacion formal\",\"tipo\":\"deseable no evidenciado\",\"impacto\":\"bajo\",\"accion_recomendada\":\"Validar si el deseable es flexible.\"}],"
            "\"preference_conflicts\":[],"
            "\"improvement_actions\":{\"reinforce_in_cv_or_profile\":[\"Resaltar trayectoria profesional.\"],\"validate_with_recruiter\":[\"Confirmar peso real del deseable.\"],\"application_narrative\":[\"Conectar trayectoria con liderazgo del rol.\"]},"
            "\"alerts_and_conflicts\":[{\"tipo\":\"alerta\",\"severidad\":\"media\",\"descripcion\":\"La vacante no explicita si el deseable es excluyente.\"}],"
            "\"actionable_conclusion\":{\"final_decision\":\"Avanzar con reservas\",\"main_reason\":\"El requisito obligatorio esta cubierto y la brecha restante es deseable.\",\"recommended_next_step\":\"Validar el peso del deseable con reclutador.\",\"confidence\":\"media\"}"
            "},"
            "\"rendered_markdown\":\"## Resumen ejecutivo\\n\\nBuen ajuste general.\""
            "}"
        )

        with patch(
            "app.services.vacancy_alignment_report_v2_service.complete_prompt",
            return_value=llm_response,
        ):
            contract = extract_vacancy_alignment_report_v2(
                person=_person(),
                opportunity=_opportunity(),
                vacancy_evidence_adjudication_artifact=_adjudication(),
                vacancy_alignment_summary_v2_artifact=_summary_v2(),
                vacancy_evidence_analysis_artifact=_analysis(),
                settings=object(),
            )

        self.assertEqual(contract["contract_version"], CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT_V2)
        self.assertEqual(contract["vacancy_id"], "o-r2-001")
        self.assertEqual(contract["person_id"], "p-001")
        self.assertEqual(
            contract["source_artifacts"]["evidence_adjudication_version"],
            "vacancy_evidence_adjudication.v1",
        )
        self.assertEqual(len(contract["report"]["vacancy_fit_matrix"]), 2)
        self.assertTrue(contract["rendered_markdown"])

    def test_extract_requires_valid_inputs(self) -> None:
        with self.assertRaises(VacancyAlignmentReportV2BuildError):
            extract_vacancy_alignment_report_v2(
                person=_person(),
                opportunity=_opportunity(),
                vacancy_evidence_adjudication_artifact={},
                vacancy_alignment_summary_v2_artifact=_summary_v2(),
                vacancy_evidence_analysis_artifact=_analysis(),
                settings=object(),
            )

    def test_extract_uses_dedicated_prompt_flow(self) -> None:
        llm_response = (
            "{"
            "\"report\":{"
            "\"executive_summary\":{\"fit_level\":\"medio\",\"final_recommendation\":\"No priorizar\",\"summary\":\"Resumen\",\"main_strength\":\"\",\"main_gap_or_risk\":\"\",\"confidence\":\"media\"},"
            "\"decision_table\":{},"
            "\"vacancy_fit_matrix\":["
            "{\"item_id\":\"req_1\",\"criterio\":\"Minimo 5 anos de experiencia profesional\",\"categoria\":\"Experiencia\",\"origen_del_criterio\":\"Vacante obligatoria\",\"prioridad\":\"Importante\",\"estado\":\"🟢 Cumple\",\"lo_que_solicita_la_vacante\":\"Minimo 5 anos de experiencia profesional\",\"evidencia_del_candidato\":\"20 anos de experiencia profesional.\",\"tipo_de_evidencia\":\"directa\",\"fuerza_de_evidencia\":\"alta\",\"descripcion_corta\":\"Directo\",\"riesgo_para_la_postulacion\":\"bajo\",\"fuentes\":[]},"
            "{\"item_id\":\"des_1\",\"criterio\":\"Certificacion PMP o Scrum\",\"categoria\":\"Certificaciones\",\"origen_del_criterio\":\"Vacante deseable\",\"prioridad\":\"Deseable\",\"estado\":\"🔵 Deseable no evidenciado\",\"lo_que_solicita_la_vacante\":\"Certificacion PMP o Scrum\",\"evidencia_del_candidato\":\"No se observa certificacion formal.\",\"tipo_de_evidencia\":\"no evidenciada\",\"fuerza_de_evidencia\":\"ninguna\",\"descripcion_corta\":\"No evidenciado\",\"riesgo_para_la_postulacion\":\"bajo\",\"fuentes\":[]}"
            "],"
            "\"candidate_preference_matrix\":[],"
            "\"fit_answer\":{\"encaja\":\"sí\",\"respuesta_para_el_candidato\":\"Si\"},"
            "\"strengths\":[],\"gaps\":[],\"preference_conflicts\":[],\"improvement_actions\":{},\"alerts_and_conflicts\":[],"
            "\"actionable_conclusion\":{\"final_decision\":\"No priorizar\",\"main_reason\":\"\",\"recommended_next_step\":\"\",\"confidence\":\"media\"}"
            "},"
            "\"rendered_markdown\":\"## Resumen ejecutivo\\n\\nTexto\""
            "}"
        )
        with patch(
            "app.services.vacancy_alignment_report_v2_service.build_prompt_text",
            side_effect=lambda flow_key, context, fallback: f"prompt::{flow_key}",
        ) as prompt_builder_mock:
            with patch(
                "app.services.vacancy_alignment_report_v2_service.complete_prompt",
                return_value=llm_response,
            ) as complete_prompt_mock:
                extract_vacancy_alignment_report_v2(
                    person=_person(),
                    opportunity=_opportunity(),
                    vacancy_evidence_adjudication_artifact=_adjudication(),
                    vacancy_alignment_summary_v2_artifact=_summary_v2(),
                    vacancy_evidence_analysis_artifact=_analysis(),
                    settings=object(),
                )

        flow_keys = [call.kwargs["flow_key"] for call in prompt_builder_mock.call_args_list]
        self.assertIn(FLOW_TASK_VACANCY_ALIGNMENT_REPORT_V2, flow_keys)
        task_call = next(
            call for call in prompt_builder_mock.call_args_list
            if call.kwargs["flow_key"] == FLOW_TASK_VACANCY_ALIGNMENT_REPORT_V2
        )
        self.assertIn("evidence_adjudication_json", task_call.kwargs["context"])
        self.assertIn("alignment_summary_json", task_call.kwargs["context"])
        self.assertEqual(
            complete_prompt_mock.call_args.kwargs["flow_key"],
            FLOW_TASK_VACANCY_ALIGNMENT_REPORT_V2,
        )

    def test_extract_fails_when_fit_matrix_is_incomplete(self) -> None:
        llm_response = (
            "{"
            "\"report\":{"
            "\"executive_summary\":{\"fit_level\":\"medio\",\"final_recommendation\":\"No priorizar\",\"summary\":\"Resumen\",\"main_strength\":\"\",\"main_gap_or_risk\":\"\",\"confidence\":\"media\"},"
            "\"decision_table\":{},"
            "\"vacancy_fit_matrix\":["
            "{\"item_id\":\"req_1\",\"criterio\":\"Minimo 5 anos de experiencia profesional\",\"categoria\":\"Experiencia\",\"origen_del_criterio\":\"Vacante obligatoria\",\"prioridad\":\"Importante\",\"estado\":\"🟢 Cumple\",\"lo_que_solicita_la_vacante\":\"Minimo 5 anos de experiencia profesional\",\"evidencia_del_candidato\":\"20 anos de experiencia profesional.\",\"tipo_de_evidencia\":\"directa\",\"fuerza_de_evidencia\":\"alta\",\"descripcion_corta\":\"Directo\",\"riesgo_para_la_postulacion\":\"bajo\",\"fuentes\":[]}"
            "],"
            "\"candidate_preference_matrix\":[],"
            "\"fit_answer\":{\"encaja\":\"sí\",\"respuesta_para_el_candidato\":\"Si\"},"
            "\"strengths\":[],\"gaps\":[],\"preference_conflicts\":[],\"improvement_actions\":{},\"alerts_and_conflicts\":[],"
            "\"actionable_conclusion\":{\"final_decision\":\"No priorizar\",\"main_reason\":\"\",\"recommended_next_step\":\"\",\"confidence\":\"media\"}"
            "},"
            "\"rendered_markdown\":\"## Resumen ejecutivo\\n\\nTexto\""
            "}"
        )
        with patch(
            "app.services.vacancy_alignment_report_v2_service.complete_prompt",
            return_value=llm_response,
        ):
            with self.assertRaises(VacancyAlignmentReportV2BuildError):
                extract_vacancy_alignment_report_v2(
                    person=_person(),
                    opportunity=_opportunity(),
                    vacancy_evidence_adjudication_artifact=_adjudication(),
                    vacancy_alignment_summary_v2_artifact=_summary_v2(),
                    vacancy_evidence_analysis_artifact=_analysis(),
                    settings=object(),
                )


if __name__ == "__main__":
    unittest.main()
