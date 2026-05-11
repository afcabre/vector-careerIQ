import unittest

from app.services.vacancy_fit_presentation_service import (
    VacancyFitPresentationBuildError,
    build_vacancy_fit_presentation,
)


def _opportunity() -> dict[str, str]:
    return {"opportunity_id": "o-001"}


def _adjudication() -> dict[str, object]:
    return {
        "contract_version": "vacancy_evidence_adjudication.v1",
        "vacancy_id": "o-001",
        "generated_at": "2026-05-11T10:00:00Z",
        "items": [
            {
                "item_id": "req_1",
                "item_index": 0,
                "group": "required_criteria",
                "group_code": "req",
                "raw_text": "Profesional en Ingenieria de Sistemas",
                "criterion_type": "education",
                "priority": "critical",
                "alignment_status": "direct",
                "evidence_strength": "high",
                "proof_summary": "La formacion reportada coincide con el requisito.",
                "best_supporting_evidence": [
                    {
                        "source_ref": "cv-1",
                        "block_title": "Educacion",
                        "section": "education",
                        "snippet": "Ingeniero de Sistemas",
                        "why_it_supports": "Demuestra el titulo exigido.",
                    }
                ],
                "weak_or_discarded_evidence": [],
                "limitations": [],
                "candidate_risk": "low",
                "cv_improvement_opportunity": "",
                "confidence": "high",
            },
            {
                "item_id": "resp_1",
                "item_index": 1,
                "group": "responsibilities",
                "group_code": "resp",
                "raw_text": "Liderar equipos multidisciplinarios",
                "criterion_type": "leadership",
                "priority": "important",
                "alignment_status": "partial",
                "evidence_strength": "medium",
                "proof_summary": "La evidencia cubre liderazgo, pero no todos los contextos esperados.",
                "best_supporting_evidence": [],
                "weak_or_discarded_evidence": [],
                "limitations": ["No explicita tamano del equipo."],
                "candidate_risk": "medium",
                "cv_improvement_opportunity": "",
                "confidence": "medium",
            },
            {
                "item_id": "des_1",
                "item_index": 2,
                "group": "desirable_criteria",
                "group_code": "des",
                "raw_text": "Certificacion PMP",
                "criterion_type": "certification",
                "priority": "desirable",
                "alignment_status": "not_evidenced",
                "evidence_strength": "none",
                "proof_summary": "No hay evidencia suficiente de la certificacion en los snippets.",
                "best_supporting_evidence": [],
                "weak_or_discarded_evidence": [],
                "limitations": [],
                "candidate_risk": "low",
                "cv_improvement_opportunity": "",
                "confidence": "low",
            },
            {
                "item_id": "cond_1",
                "item_index": 3,
                "group": "work_conditions",
                "group_code": "cond",
                "raw_text": "Modalidad hibrida 4x1",
                "criterion_type": "condition",
                "priority": "contextual",
                "alignment_status": "not_applicable",
                "evidence_strength": "none",
                "proof_summary": "",
                "best_supporting_evidence": [],
                "weak_or_discarded_evidence": [],
                "limitations": [],
                "candidate_risk": "none",
                "cv_improvement_opportunity": "",
                "confidence": "low",
            },
        ],
        "warnings": [],
    }


class VacancyFitPresentationServiceTests(unittest.TestCase):
    def test_build_generates_grouped_rows_from_adjudication(self) -> None:
        artifact = build_vacancy_fit_presentation(
            opportunity=_opportunity(),
            vacancy_evidence_adjudication_artifact=_adjudication(),
        )

        self.assertEqual(artifact["contract_version"], "vacancy_fit_presentation.v1")
        self.assertEqual(len(artifact["groups"]["required_criteria"]), 1)
        self.assertEqual(len(artifact["groups"]["responsibilities"]), 1)
        self.assertEqual(len(artifact["groups"]["desirable_criteria"]), 1)
        self.assertEqual(
            artifact["groups"]["required_criteria"][0]["state"],
            "🟢 Cumple",
        )
        self.assertEqual(
            artifact["groups"]["responsibilities"][0]["state"],
            "🟡 Parcial",
        )
        self.assertEqual(
            artifact["groups"]["desirable_criteria"][0]["state"],
            "🔵 Deseable no evidenciado",
        )
        self.assertEqual(
            artifact["groups"]["required_criteria"][0]["evidence_count"],
            1,
        )
        self.assertIn("work_conditions_excluded_from_main_matrix", artifact["warnings"])

    def test_build_requires_valid_adjudication(self) -> None:
        with self.assertRaises(VacancyFitPresentationBuildError):
            build_vacancy_fit_presentation(
                opportunity=_opportunity(),
                vacancy_evidence_adjudication_artifact={},
            )


if __name__ == "__main__":
    unittest.main()
