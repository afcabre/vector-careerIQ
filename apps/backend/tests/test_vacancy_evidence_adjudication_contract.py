import unittest

from app.services.vacancy_evidence_adjudication_contract import (
    CONTRACT_VERSION_VACANCY_EVIDENCE_ADJUDICATION,
    normalize_vacancy_evidence_adjudication_contract,
)


class VacancyEvidenceAdjudicationContractTests(unittest.TestCase):
    def test_normalize_contract_preserves_item_shape(self) -> None:
        normalized = normalize_vacancy_evidence_adjudication_contract(
            {
                "contract_version": CONTRACT_VERSION_VACANCY_EVIDENCE_ADJUDICATION,
                "vacancy_id": "o-1",
                "generated_at": "2026-05-08T12:00:00Z",
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
                        "best_supporting_evidence": [
                            {
                                "source_ref": "cv:chunk:1",
                                "block_title": "Perfil profesional",
                                "section": "profile_summary",
                                "snippet": "Profesional con 20 anos de experiencia.",
                                "why_it_supports": "Declara de forma explicita la antiguedad profesional.",
                            }
                        ],
                        "weak_or_discarded_evidence": [
                            {
                                "source_ref": "cv:chunk:9",
                                "block_title": "Otros estudios",
                                "reason": "No prueba anos de experiencia profesional.",
                            }
                        ],
                        "limitations": ["No especifica anos por sector."],
                        "candidate_risk": "low",
                        "cv_improvement_opportunity": "Resaltar anos de experiencia en el resumen inicial.",
                        "confidence": "high",
                    }
                ],
                "warnings": ["Ninguna"],
            }
        )

        self.assertEqual(
            normalized["contract_version"],
            CONTRACT_VERSION_VACANCY_EVIDENCE_ADJUDICATION,
        )
        self.assertEqual(normalized["items"][0]["item_id"], "req_1")
        self.assertEqual(normalized["items"][0]["alignment_status"], "direct")
        self.assertEqual(
            normalized["items"][0]["best_supporting_evidence"][0]["section"],
            "profile_summary",
        )


if __name__ == "__main__":
    unittest.main()
