import unittest

from app.services.vacancy_fit_presentation_contract import (
    empty_vacancy_fit_presentation_contract,
    normalize_vacancy_fit_presentation_contract,
)


class VacancyFitPresentationContractTests(unittest.TestCase):
    def test_empty_contract_has_expected_shape(self) -> None:
        artifact = empty_vacancy_fit_presentation_contract()

        self.assertEqual(artifact["contract_version"], "vacancy_fit_presentation.v1")
        self.assertEqual(artifact["groups"]["required_criteria"], [])
        self.assertEqual(artifact["groups"]["responsibilities"], [])
        self.assertEqual(artifact["groups"]["desirable_criteria"], [])

    def test_normalize_contract_dedupes_rows_and_defaults_invalid_state(self) -> None:
        normalized = normalize_vacancy_fit_presentation_contract(
            {
                "contract_version": "vacancy_fit_presentation.v1",
                "vacancy_id": "o-001",
                "generated_at": "2026-05-11T10:00:00Z",
                "groups": {
                    "required_criteria": [
                        {
                            "item_id": "req_1",
                            "item_index": 0,
                            "group": "required_criteria",
                            "group_code": "req",
                            "type_label": "Obligatorio",
                            "criterion": "Ingenieria de sistemas",
                            "state": "bad",
                            "why": "Texto",
                            "evidence_count": 1,
                            "evidence": [{"source_ref": "cv-1", "snippet": "Ingeniero", "block_title": "", "section": "", "why_it_supports": ""}],
                            "limitations": ["limitacion"],
                            "confidence": "BAD",
                            "candidate_risk": "BAD",
                        },
                        {
                            "item_id": "req_1",
                            "item_index": 1,
                            "group": "required_criteria",
                            "group_code": "req",
                            "type_label": "Obligatorio",
                            "criterion": "Duplicado",
                            "state": "🟢 Cumple",
                            "why": "Duplicado",
                            "evidence_count": 0,
                            "evidence": [],
                            "limitations": [],
                            "confidence": "high",
                            "candidate_risk": "low",
                        },
                    ],
                },
                "warnings": ["a", "a"],
            }
        )

        self.assertEqual(len(normalized["groups"]["required_criteria"]), 1)
        row = normalized["groups"]["required_criteria"][0]
        self.assertEqual(row["state"], "⚪ Sin informacion")
        self.assertEqual(row["confidence"], "none")
        self.assertEqual(row["candidate_risk"], "none")
        self.assertEqual(normalized["warnings"], ["a"])


if __name__ == "__main__":
    unittest.main()
