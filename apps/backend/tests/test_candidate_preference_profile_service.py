import unittest

from app.services.candidate_preference_profile_service import build_candidate_preference_profile


class CandidatePreferenceProfileServiceTests(unittest.TestCase):
    def test_build_profile_derives_explicit_comparable_signals(self) -> None:
        artifact = build_candidate_preference_profile(
            {
                "person_id": "p-001",
                "full_name": "Camila Torres",
                "target_roles": ["Backend Engineer"],
                "location": "Bogota, Colombia",
                "years_experience": 8,
                "skills": ["Python", "FastAPI"],
                "languages": [{"language": "English", "level": "B2"}],
                "tools_technologies": ["Azure"],
                "certifications": ["PMP"],
                "accepted_locations": ["Bogota", "Medellin"],
                "accepted_modalities": ["remote", "hybrid"],
                "contract_types_accepted": ["indefinite", "fixed_term"],
                "relocation_willingness": "yes",
                "travel_willingness": "no",
                "hard_constraints": ["No night shifts"],
                "salary_expectation_min": 12000000,
                "salary_expectation_max": 16000000,
                "salary_currency": "COP",
                "salary_period": "monthly",
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
        self.assertEqual(comparable["current_location"], "Bogota, Colombia")
        self.assertEqual(comparable["accepted_locations"], ["Bogota", "Medellin"])
        self.assertEqual(comparable["accepted_modalities"], ["remote", "hybrid"])
        self.assertEqual(comparable["contract_types_accepted"], ["indefinite", "fixed_term"])
        self.assertEqual(comparable["relocation_willingness"], "yes")
        self.assertEqual(comparable["travel_willingness"], "no")
        self.assertEqual(comparable["hard_constraints"], ["No night shifts"])
        self.assertEqual(comparable["salary_expectation"]["min"], 12000000)
        self.assertNotIn("languages_not_captured_in_structured_profile", artifact["warnings"])
        self.assertNotIn("accepted_locations_not_captured", artifact["warnings"])
        self.assertNotIn("contract_types_accepted_not_captured", artifact["warnings"])

    def test_build_profile_keeps_unknown_when_signals_are_missing(self) -> None:
        artifact = build_candidate_preference_profile(
            {
                "person_id": "p-002",
                "full_name": "Mateo Rojas",
                "target_roles": ["Data Analyst"],
                "location": "",
                "years_experience": 4,
                "skills": ["SQL"],
                "languages": [],
                "tools_technologies": [],
                "certifications": [],
                "accepted_locations": [],
                "accepted_modalities": [],
                "contract_types_accepted": [],
                "relocation_willingness": "unknown",
                "travel_willingness": "unknown",
                "hard_constraints": [],
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
        self.assertEqual(comparable["accepted_modalities"], [])
        self.assertEqual(comparable["contract_types_accepted"], [])
        self.assertIn("current_location_missing", artifact["warnings"])
        self.assertIn("accepted_locations_not_captured", artifact["warnings"])
        self.assertIn("accepted_modalities_not_captured", artifact["warnings"])
        self.assertIn("contract_types_accepted_not_captured", artifact["warnings"])
        self.assertIn("salary_expectation_not_captured", artifact["warnings"])
        self.assertIn("languages_not_captured_in_structured_profile", artifact["warnings"])


if __name__ == "__main__":
    unittest.main()
