import unittest

from app.services.vacancy_alignment_report_v2_contract import (
    CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT_V2,
    normalize_vacancy_alignment_report_v2_contract,
)


class VacancyAlignmentReportV2ContractTests(unittest.TestCase):
    def test_normalize_contract_preserves_report_shape(self) -> None:
        normalized = normalize_vacancy_alignment_report_v2_contract(
            {
                "contract_version": CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT_V2,
                "vacancy_id": "o-1",
                "person_id": "p-1",
                "generated_at": "2026-05-08T18:00:00Z",
                "source_artifacts": {
                    "evidence_adjudication_version": "vacancy_evidence_adjudication.v1",
                    "alignment_summary_version": "vacancy_alignment_summary.v2",
                    "evidence_analysis_version": "vacancy_evidence_analysis.v1",
                },
                "report": {
                    "executive_summary": {
                        "fit_level": "medio_alto",
                        "final_recommendation": "Avanzar con reservas",
                        "summary": "Buen ajuste general con una brecha acotada.",
                        "main_strength": "Experiencia directa en liderazgo tecnico.",
                        "main_gap_or_risk": "No se evidencia certificacion formal.",
                        "confidence": "media",
                    },
                    "decision_table": {
                        "alineacion_general": {
                            "resultado": "🟡 Parcial",
                            "descripcion_corta": "Buen ajuste con una brecha no bloqueante.",
                        }
                    },
                    "vacancy_fit_matrix": [
                        {
                            "item_id": "req_1",
                            "criterio": "Minimo 5 anos de experiencia",
                            "categoria": "Experiencia",
                            "origen_del_criterio": "Vacante obligatoria",
                            "prioridad": "Importante",
                            "estado": "🟢 Cumple",
                            "lo_que_solicita_la_vacante": "Minimo 5 anos de experiencia profesional",
                            "evidencia_del_candidato": "Profesional con 20 anos de experiencia.",
                            "tipo_de_evidencia": "directa",
                            "fuerza_de_evidencia": "alta",
                            "descripcion_corta": "El criterio queda cubierto de forma directa.",
                            "riesgo_para_la_postulacion": "bajo",
                            "fuentes": ["cv:chunk:1"],
                        }
                    ],
                    "candidate_preference_matrix": [],
                    "fit_answer": {
                        "encaja": "sí",
                        "respuesta_para_el_candidato": "La postulacion es defendible.",
                    },
                    "strengths": [
                        {
                            "fortaleza": "Trayectoria profesional extensa",
                            "por_que_importa": "Cubre un requisito base del rol.",
                            "evidencia": "20 anos de experiencia profesional.",
                        }
                    ],
                    "gaps": [
                        {
                            "brecha": "No se evidencia certificacion formal",
                            "tipo": "deseable no evidenciado",
                            "impacto": "bajo",
                            "accion_recomendada": "Confirmar si el deseable es flexible.",
                        }
                    ],
                    "preference_conflicts": [],
                    "improvement_actions": {
                        "reinforce_in_cv_or_profile": ["Resaltar experiencia liderando equipos."],
                        "validate_with_recruiter": ["Confirmar peso real del deseable de certificacion."],
                        "application_narrative": ["Conectar liderazgo tecnico con resultados."],
                    },
                    "alerts_and_conflicts": [
                        {
                            "tipo": "alerta",
                            "severidad": "media",
                            "descripcion": "La vacante no especifica modalidad.",
                        }
                    ],
                    "actionable_conclusion": {
                        "final_decision": "Avanzar con reservas",
                        "main_reason": "El core del rol encaja, pero queda un deseable abierto.",
                        "recommended_next_step": "Validar el peso del deseable con reclutador.",
                        "confidence": "media",
                    },
                },
                "rendered_markdown": "## Resumen ejecutivo\n\nTexto",
            }
        )

        self.assertEqual(normalized["contract_version"], CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT_V2)
        self.assertEqual(normalized["report"]["vacancy_fit_matrix"][0]["item_id"], "req_1")
        self.assertEqual(normalized["report"]["executive_summary"]["fit_level"], "medio_alto")


if __name__ == "__main__":
    unittest.main()
