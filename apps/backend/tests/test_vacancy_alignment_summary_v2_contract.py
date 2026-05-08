import unittest

from app.services.vacancy_alignment_summary_v2_contract import (
    CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY_V2,
    normalize_vacancy_alignment_summary_v2_contract,
)


class VacancyAlignmentSummaryV2ContractTests(unittest.TestCase):
    def test_normalize_contract_preserves_summary_shape(self) -> None:
        normalized = normalize_vacancy_alignment_summary_v2_contract(
            {
                "contract_version": CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY_V2,
                "vacancy_id": "o-1",
                "generated_at": "2026-05-08T18:00:00Z",
                "source_artifact_version": "vacancy_evidence_adjudication.v1",
                "summary": {
                    "overall": {
                        "total_items": 3,
                        "direct_count": 1,
                        "partial_count": 1,
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
                        }
                    },
                    "strengths": [
                        {
                            "item_id": "req_1",
                            "raw_text": "Minimo 5 anos de experiencia",
                            "alignment_status": "direct",
                            "evidence_strength": "high",
                            "proof_summary": "Se evidencia de forma directa.",
                        }
                    ],
                    "gaps": [
                        {
                            "item_id": "des_1",
                            "raw_text": "PMP",
                            "gap_type": "desirable_not_evidenced",
                            "impact": "low",
                            "explanation": "No aparece evidencia suficiente.",
                        }
                    ],
                    "review_items": [
                        {
                            "item_id": "resp_1",
                            "raw_text": "Excelencia tecnica",
                            "reason": "La evidencia es transferible, pero no literal.",
                        }
                    ],
                    "risks": [
                        {
                            "item_id": "resp_1",
                            "risk": "La cobertura es parcial en el liderazgo del area.",
                            "severity": "medium",
                        }
                    ],
                },
            }
        )

        self.assertEqual(
            normalized["contract_version"],
            CONTRACT_VERSION_VACANCY_ALIGNMENT_SUMMARY_V2,
        )
        self.assertEqual(normalized["summary"]["overall"]["total_items"], 3)
        self.assertEqual(normalized["summary"]["strengths"][0]["item_id"], "req_1")
        self.assertEqual(normalized["summary"]["gaps"][0]["gap_type"], "desirable_not_evidenced")


if __name__ == "__main__":
    unittest.main()
