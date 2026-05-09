import unittest

from app.services.candidate_preference_profile_contract import (
    CONTRACT_VERSION_CANDIDATE_PREFERENCE_PROFILE,
    is_candidate_preference_profile_contract,
    normalize_candidate_preference_profile_contract,
)


class CandidatePreferenceProfileContractTests(unittest.TestCase):
    def test_normalize_contract_cleans_and_defaults(self) -> None:
        normalized = normalize_candidate_preference_profile_contract(
            {
                "contract_version": CONTRACT_VERSION_CANDIDATE_PREFERENCE_PROFILE,
                "person_id": " p-001 ",
                "generated_at": "2026-05-09T10:00:00Z",
                "comparable_preferences": {
                    "current_location": " Bogota ",
                    "accepted_locations": [" Bogota ", "Bogota"],
                    "accepted_modalities": ["remote", "remote", "hybrid", "invalid"],
                    "remote_accepted": True,
                    "salary_expectation": {
                        "min": "12000000",
                        "max": None,
                        "currency": "cop",
                        "period": "monthly",
                    },
                    "relocation_willingness": "not_captured",
                    "travel_willingness": "unknown",
                    "hard_constraints": ["Remote only", "Remote only"],
                },
                "contrastable_company_preferences": [
                    {
                        "field_id": "company_scale",
                        "selected_values": ["multinational", "multinational"],
                        "criticality": "high_penalty",
                    }
                ],
                "warnings": ["accepted_locations_not_captured", "accepted_locations_not_captured"],
            }
        )

        self.assertEqual(normalized["person_id"], "p-001")
        self.assertEqual(normalized["comparable_preferences"]["accepted_locations"], ["Bogota"])
        self.assertEqual(
            normalized["comparable_preferences"]["accepted_modalities"],
            ["remote", "hybrid"],
        )
        self.assertEqual(normalized["comparable_preferences"]["salary_expectation"]["currency"], "COP")
        self.assertEqual(normalized["warnings"], ["accepted_locations_not_captured"])

    def test_contract_detector_requires_exact_version(self) -> None:
        self.assertTrue(
            is_candidate_preference_profile_contract(
                {"contract_version": CONTRACT_VERSION_CANDIDATE_PREFERENCE_PROFILE}
            )
        )
        self.assertFalse(is_candidate_preference_profile_contract({}))


if __name__ == "__main__":
    unittest.main()
