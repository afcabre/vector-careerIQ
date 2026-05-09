import unittest

from app.services.candidate_preference_profile_service import build_candidate_preference_profile


class CandidatePreferenceProfileServiceTests(unittest.TestCase):
    def test_build_profile_derives_comparable_and_contrastable_signals(self) -> None:
        artifact = build_candidate_preference_profile(
            {
                "person_id": "p-001",
                "full_name": "Camila Torres",
                "target_roles": ["Backend Engineer"],
                "location": "Bogota, Colombia",
                "years_experience": 8,
                "skills": ["Python", "FastAPI"],
                "salary_expectation_min": 12000000,
                "salary_expectation_max": 16000000,
                "salary_currency": "COP",
                "salary_period": "monthly",
                "culture_preferences": [],
                "cultural_fit_preferences": {
                    "work_modality": {
                        "enabled": True,
                        "selected_values": ["remote", "hybrid"],
                        "criticality": "high_penalty",
                    },
                    "company_scale": {
                        "enabled": True,
                        "selected_values": ["multinational"],
                        "criticality": "normal",
                    },
                    "organizational_moment": {
                        "enabled": False,
                        "selected_values": ["transformation"],
                        "criticality": "normal",
                    },
                },
                "culture_preferences_notes": "",
                "candidate_preference_profile_artifact": {},
                "candidate_preference_profile_status": "none",
                "candidate_preference_profile_generated_at": "",
                "created_at": "",
                "updated_at": "",
            }
        )

        comparable = artifact["comparable_preferences"]
        self.assertEqual(comparable["current_location"], "Bogota, Colombia")
        self.assertEqual(comparable["accepted_locations"], [])
        self.assertEqual(comparable["accepted_modalities"], ["remote", "hybrid"])
        self.assertTrue(comparable["remote_accepted"])
        self.assertEqual(comparable["salary_expectation"]["min"], 12000000)
        self.assertEqual(
            artifact["contrastable_company_preferences"],
            [
                {
                    "field_id": "company_scale",
                    "selected_values": ["multinational"],
                    "criticality": "normal",
                }
            ],
        )
        self.assertIn("languages_not_captured_in_structured_profile", artifact["warnings"])

    def test_build_profile_keeps_unknown_when_signals_are_missing(self) -> None:
        artifact = build_candidate_preference_profile(
            {
                "person_id": "p-002",
                "full_name": "Mateo Rojas",
                "target_roles": ["Data Analyst"],
                "location": "",
                "years_experience": 4,
                "skills": ["SQL"],
                "salary_expectation_min": None,
                "salary_expectation_max": None,
                "salary_currency": "",
                "salary_period": "",
                "culture_preferences": [],
                "cultural_fit_preferences": {},
                "culture_preferences_notes": "",
                "candidate_preference_profile_artifact": {},
                "candidate_preference_profile_status": "none",
                "candidate_preference_profile_generated_at": "",
                "created_at": "",
                "updated_at": "",
            }
        )

        comparable = artifact["comparable_preferences"]
        self.assertIsNone(comparable["remote_accepted"])
        self.assertEqual(comparable["accepted_modalities"], [])
        self.assertIn("current_location_missing", artifact["warnings"])
        self.assertIn("salary_expectation_not_captured", artifact["warnings"])


if __name__ == "__main__":
    unittest.main()
