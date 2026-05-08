import unittest

from app.services.vacancy_alignment_summary_v2_service import (
    VacancyAlignmentSummaryV2BuildError,
    build_vacancy_alignment_summary_v2,
)


def _opportunity() -> dict[str, str]:
    return {
        "opportunity_id": "o-s7v2-001",
        "person_id": "p-001",
        "title": "Lider Transformacion Digital",
        "company": "Acme",
        "location": "Bogota",
    }


def _vacancy_evidence_adjudication() -> dict[str, object]:
    return {
        "contract_version": "vacancy_evidence_adjudication.v1",
        "vacancy_id": "o-s7v2-001",
        "generated_at": "2026-05-08T17:00:00Z",
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
                "item_id": "resp_1",
                "item_index": 1,
                "group": "responsibilities",
                "group_code": "resp",
                "raw_text": "Asegurar la excelencia tecnica",
                "criterion_type": "leadership",
                "priority": "critical",
                "alignment_status": "partial",
                "evidence_strength": "medium",
                "proof_summary": "Hay evidencia transferible en arquitectura y gobierno tecnico.",
                "best_supporting_evidence": [],
                "weak_or_discarded_evidence": [],
                "limitations": ["No aparece el nombre literal del area."],
                "candidate_risk": "medium",
                "cv_improvement_opportunity": "",
                "confidence": "medium",
            },
            {
                "item_id": "des_1",
                "item_index": 2,
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


class VacancyAlignmentSummaryV2ServiceTests(unittest.TestCase):
    def test_build_summary_v2_success_returns_adjudication_rollup(self) -> None:
        contract = build_vacancy_alignment_summary_v2(
            opportunity=_opportunity(),
            vacancy_evidence_adjudication_artifact=_vacancy_evidence_adjudication(),
        )

        self.assertEqual(contract["summary"]["overall"]["total_items"], 3)
        self.assertEqual(contract["summary"]["overall"]["direct_count"], 1)
        self.assertEqual(contract["summary"]["overall"]["partial_count"], 1)
        self.assertEqual(contract["summary"]["overall"]["not_evidenced_count"], 1)
        self.assertEqual(contract["summary"]["strengths"][0]["item_id"], "req_1")
        self.assertEqual(contract["summary"]["gaps"][0]["item_id"], "resp_1")
        self.assertEqual(contract["summary"]["risks"][0]["severity"], "medium")

    def test_build_summary_v2_requires_valid_adjudication_artifact(self) -> None:
        with self.assertRaises(VacancyAlignmentSummaryV2BuildError):
            build_vacancy_alignment_summary_v2(
                opportunity=_opportunity(),
                vacancy_evidence_adjudication_artifact={},
            )

    def test_build_summary_v2_requires_relevant_items(self) -> None:
        artifact = _vacancy_evidence_adjudication()
        artifact["items"] = [
            {
                "item_id": "ben_1",
                "item_index": 0,
                "group": "benefits",
                "group_code": "ben",
                "raw_text": "Seguro medico",
                "criterion_type": "other",
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
            }
        ]
        with self.assertRaises(VacancyAlignmentSummaryV2BuildError):
            build_vacancy_alignment_summary_v2(
                opportunity=_opportunity(),
                vacancy_evidence_adjudication_artifact=artifact,
            )


if __name__ == "__main__":
    unittest.main()
