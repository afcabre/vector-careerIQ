import os
import unittest

from app.core.settings import get_settings
from app.services import person_store
from app.services.person_store import CULTURAL_FIELD_OPTIONS, create_person, sanitize_cultural_fit_preferences


def _reset_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]


class CulturalFitValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PERSISTENCE_BACKEND"] = "memory"
        get_settings.cache_clear()
        _reset_state()

    def tearDown(self) -> None:
        get_settings.cache_clear()
        _reset_state()

    def test_sanitize_returns_defaults_when_input_is_not_dict(self) -> None:
        sanitized = sanitize_cultural_fit_preferences(raw_value=None)
        self.assertEqual(set(sanitized.keys()), set(CULTURAL_FIELD_OPTIONS.keys()))

        for field_id in CULTURAL_FIELD_OPTIONS:
            self.assertEqual(sanitized[field_id]["enabled"], False)
            self.assertEqual(sanitized[field_id]["selected_values"], [])
            self.assertEqual(sanitized[field_id]["criticality"], "normal")

    def test_sanitize_filters_unknown_options_and_invalid_criticality(self) -> None:
        raw_value = {
            "work_modality": {
                "enabled": True,
                "selected_values": ["remote", "invalid", " remote ", "hybrid"],
                "criticality": "non_negotiable",
            },
            "schedule_flexibility": "bad-shape",
            "organization_structure_level": {
                "enabled": 1,
                "selected_values": ["medium_high", "unknown", 123],
                "criticality": "critical",
            },
            "unknown_field": {
                "enabled": True,
                "selected_values": ["x"],
                "criticality": "non_negotiable",
            },
        }

        sanitized = sanitize_cultural_fit_preferences(raw_value)
        self.assertEqual(set(sanitized.keys()), set(CULTURAL_FIELD_OPTIONS.keys()))

        self.assertEqual(
            sanitized["work_modality"],
            {
                "enabled": True,
                "selected_values": ["remote", "hybrid"],
                "criticality": "non_negotiable",
            },
        )
        self.assertEqual(
            sanitized["schedule_flexibility"],
            {
                "enabled": False,
                "selected_values": [],
                "criticality": "normal",
            },
        )
        self.assertEqual(
            sanitized["organization_structure_level"],
            {
                "enabled": True,
                "selected_values": ["medium_high"],
                "criticality": "normal",
            },
        )

    def test_create_person_persists_sanitized_cultural_preferences(self) -> None:
        created = create_person(
            full_name="Test User",
            target_roles=["Backend Engineer"],
            location="Bogota",
            years_experience=5,
            skills=["Python"],
            cultural_fit_preferences={
                "work_intensity": {
                    "enabled": True,
                    "selected_values": ["high", "invalid"],
                    "criticality": "high_penalty",
                },
                "company_scale": {
                    "enabled": True,
                    "selected_values": ["multinational", "local", "multinational"],
                    "criticality": "oops",
                },
            },
        )

        cultural = created["cultural_fit_preferences"]
        self.assertEqual(
            cultural["work_intensity"],
            {
                "enabled": True,
                "selected_values": ["high"],
                "criticality": "high_penalty",
            },
        )
        self.assertEqual(
            cultural["company_scale"],
            {
                "enabled": True,
                "selected_values": ["multinational", "local"],
                "criticality": "normal",
            },
        )
        self.assertEqual(
            cultural["cultural_formality"],
            {
                "enabled": False,
                "selected_values": [],
                "criticality": "normal",
            },
        )


if __name__ == "__main__":
    unittest.main()
