import unittest

from app.services.vacancy_alignment_report_contract import (
    CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT,
    normalize_vacancy_alignment_report_contract,
)


class VacancyAlignmentReportContractTests(unittest.TestCase):
    def test_normalize_contract_preserves_report_shape(self) -> None:
        normalized = normalize_vacancy_alignment_report_contract(
            {
                "contract_version": CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT,
                "vacancy_id": "o-1",
                "person_id": "p-1",
                "generated_at": "2026-04-24T18:00:00Z",
                "source_artifacts": {
                    "alignment_summary_version": "vacancy_alignment_summary.v1",
                    "evidence_analysis_version": "vacancy_evidence_analysis.v1",
                },
                "report": {
                    "executive_summary": "Buen encaje con una brecha visible en cloud.",
                    "decision_table": {
                        "alineacion_general": {
                            "resultado": "Avanzar con reservas",
                            "descripcion_corta": "Buen ajuste con una brecha critica.",
                        }
                    },
                    "vacancy_fit_matrix": [
                        {
                            "criterio": "Python",
                            "categoria": "Herramientas",
                            "origen_del_criterio": "Vacante obligatoria",
                            "estado": "🟢 Cumple",
                            "lo_que_solicita_la_vacante": "Experiencia con Python",
                            "evidencia_del_candidato": "Proyecto con modelos en Python",
                            "descripcion_corta": "Evidencia directa en experiencia reciente.",
                        }
                    ],
                    "candidate_preference_matrix": [
                        {
                            "criterio": "Modalidad",
                            "categoria": "Condiciones laborales",
                            "origen_del_criterio": "Preferencia del candidato",
                            "estado": "⚪ Sin informacion",
                            "lo_que_ofrece_o_define_la_vacante": "No lo especifica",
                            "preferencia_o_condicion_del_candidato": "Prefiere remoto o hibrido",
                            "descripcion_corta": "La vacante no aclara modalidad.",
                        }
                    ],
                    "fit_answer": "Encaja con la vacante, pero debe validarse cloud.",
                    "strengths": ["Python y analitica ya demostrados."],
                    "gaps": ["Cloud no esta demostrado."],
                    "preference_conflicts": [],
                    "improvement_actions": {
                        "reinforce_in_cv_or_profile": ["Destacar proyectos en Python."],
                        "validate_with_recruiter": ["Confirmar stack cloud del rol."],
                        "application_narrative": ["Enfatizar impacto con datos."],
                    },
                    "alerts_and_conflicts": ["Falta evidencia explicita de cloud."],
                    "actionable_conclusion": {
                        "final_decision": "Avanzar con reservas",
                        "main_reason": "El core tecnico encaja, pero cloud sigue abierto.",
                        "recommended_next_step": "Validar con reclutador antes de priorizar.",
                    },
                },
                "rendered_markdown": "## Resumen ejecutivo\n\nTexto",
            }
        )

        self.assertEqual(
            normalized["contract_version"],
            CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT,
        )
        self.assertEqual(normalized["report"]["vacancy_fit_matrix"][0]["criterio"], "Python")
        self.assertEqual(
            normalized["report"]["candidate_preference_matrix"][0]["estado"],
            "⚪ Sin informacion",
        )
        self.assertEqual(normalized["rendered_markdown"], "## Resumen ejecutivo\n\nTexto")

    def test_normalize_contract_preserves_markdown_tables_and_line_breaks(self) -> None:
        normalized = normalize_vacancy_alignment_report_contract(
            {
                "contract_version": CONTRACT_VERSION_VACANCY_ALIGNMENT_REPORT,
                "vacancy_id": "o-1",
                "person_id": "p-1",
                "generated_at": "2026-04-25T18:00:00Z",
                "source_artifacts": {},
                "report": {},
                "rendered_markdown": (
                    "## Resumen ejecutivo\n\n"
                    "| Indicador | Resultado |\n"
                    "|---|---|\n"
                    "| Alineacion general | 🟡 Parcial |\n"
                ),
            }
        )

        self.assertIn("| Indicador | Resultado |", normalized["rendered_markdown"])
        self.assertIn("|---|---|", normalized["rendered_markdown"])
        self.assertIn("\n| Alineacion general | 🟡 Parcial |", normalized["rendered_markdown"])


if __name__ == "__main__":
    unittest.main()
