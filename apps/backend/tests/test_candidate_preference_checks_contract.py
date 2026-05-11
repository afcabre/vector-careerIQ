import unittest

from app.services.candidate_preference_checks_contract import (
    CONTRACT_VERSION_CANDIDATE_PREFERENCE_CHECKS,
    empty_candidate_preference_checks_contract,
    is_candidate_preference_checks_contract,
    normalize_candidate_preference_checks_contract,
)


class CandidatePreferenceChecksContractTests(unittest.TestCase):
    def test_empty_contract_uses_stable_defaults(self) -> None:
        contract = empty_candidate_preference_checks_contract()

        self.assertEqual(
            contract["contract_version"],
            CONTRACT_VERSION_CANDIDATE_PREFERENCE_CHECKS,
        )
        self.assertEqual(contract["vacancy_id"], "")
        self.assertEqual(contract["person_id"], "")
        self.assertEqual(contract["rows"], [])
        self.assertEqual(contract["warnings"], [])

    def test_normalize_contract_accepts_valid_rows(self) -> None:
        normalized = normalize_candidate_preference_checks_contract(
            {
                "vacancy_id": " VAC-1 ",
                "person_id": " P-1 ",
                "generated_at": " 2026-05-09T10:00:00Z ",
                "rows": [
                    {
                        "criterion_key": " location ",
                        "criterion": " Ubicacion ",
                        "state": " 🟢 Cumple ",
                        "vacancy_value": " Bogota, Colombia ",
                        "candidate_value": " Bogota ",
                        "why": " Coincide ",
                        "confidence": " high ",
                    },
                    {
                        "criterion_key": "invalid",
                        "criterion": "Ignorar",
                        "state": "bad",
                        "vacancy_value": "",
                        "candidate_value": "",
                        "why": "",
                        "confidence": "bad",
                    },
                ],
                "warnings": [" hard_constraints_captured_but_not_compared_yet "],
            }
        )

        self.assertEqual(normalized["vacancy_id"], "VAC-1")
        self.assertEqual(normalized["person_id"], "P-1")
        self.assertEqual(len(normalized["rows"]), 1)
        self.assertEqual(normalized["rows"][0]["criterion_key"], "location")
        self.assertEqual(normalized["warnings"], ["hard_constraints_captured_but_not_compared_yet"])

    def test_is_contract_detects_version(self) -> None:
        self.assertTrue(
            is_candidate_preference_checks_contract(
                {"contract_version": CONTRACT_VERSION_CANDIDATE_PREFERENCE_CHECKS}
            )
        )
        self.assertFalse(is_candidate_preference_checks_contract({"contract_version": "legacy"}))
        self.assertFalse(is_candidate_preference_checks_contract({}))


if __name__ == "__main__":
    unittest.main()
