import unittest

from app.services.candidate_preference_checks_service import (
    CandidatePreferenceChecksBuildError,
    build_candidate_preference_checks,
)


def _person() -> dict[str, str]:
    return {"person_id": "p-001"}


def _opportunity() -> dict[str, str]:
    return {"opportunity_id": "o-001"}


def _candidate_preference_profile() -> dict[str, object]:
    return {
        "contract_version": "candidate_preference_profile.v1",
        "person_id": "p-001",
        "generated_at": "2026-05-09T10:00:00Z",
        "comparable_preferences": {
            "current_location": "Bogota, Colombia",
            "accepted_locations": ["Bogota", "Medellin"],
            "accepted_modalities": ["hybrid", "remote"],
            "contract_types_accepted": ["indefinite"],
            "salary_expectation": {
                "min": 10000000,
                "max": 14000000,
                "currency": "COP",
                "period": "monthly",
            },
            "relocation_willingness": "no",
            "travel_willingness": "yes",
            "hard_constraints": ["No night shifts"],
        },
        "warnings": [],
    }


def _vacancy_comparable_conditions() -> dict[str, object]:
    return {
        "contract_version": "vacancy_comparable_conditions.v1",
        "vacancy_id": "o-001",
        "generated_at": "2026-05-09T10:01:00Z",
        "location": {
            "raw": "Bogota D.C.",
            "normalized_city": "Bogota",
            "normalized_country": "Colombia",
            "confidence": "high",
        },
        "modality": {
            "raw": "Hibrido 4x1",
            "mode": "hybrid",
            "intensity": "4x1",
            "confidence": "high",
        },
        "compensation": {
            "raw": "$12.000.000 COP + comisiones",
            "currency": "COP",
            "min_amount": 12000000,
            "max_amount": 12000000,
            "period": "monthly",
            "has_variable_component": True,
            "variable_component_type": "commission",
            "variable_component_note": "comisiones",
            "confidence": "high",
        },
        "contract_type": {
            "raw": "Contrato indefinido",
            "value": "indefinite",
            "confidence": "high",
        },
        "warnings": [],
    }


class CandidatePreferenceChecksServiceTests(unittest.TestCase):
    def test_build_generates_four_deterministic_rows(self) -> None:
        artifact = build_candidate_preference_checks(
            person=_person(),
            opportunity=_opportunity(),
            candidate_preference_profile_artifact=_candidate_preference_profile(),
            vacancy_comparable_conditions_artifact=_vacancy_comparable_conditions(),
        )

        self.assertEqual(artifact["contract_version"], "candidate_preference_checks.v1")
        self.assertEqual(artifact["vacancy_id"], "o-001")
        self.assertEqual(artifact["person_id"], "p-001")
        self.assertEqual(len(artifact["rows"]), 4)
        rows = {row["criterion_key"]: row for row in artifact["rows"]}
        self.assertEqual(rows["location"]["state"], "🟢 Cumple")
        self.assertEqual(rows["modality"]["state"], "🟢 Cumple")
        self.assertEqual(rows["contract_type"]["state"], "🟢 Cumple")
        self.assertIn(rows["compensation"]["state"], {"🟢 Cumple", "🟡 Parcial"})
        self.assertIn("travel_willingness_captured_but_not_compared_yet", artifact["warnings"])

    def test_remote_vacancy_does_not_block_by_city(self) -> None:
        vacancy = _vacancy_comparable_conditions()
        vacancy["location"]["normalized_city"] = "Cali"
        vacancy["location"]["normalized_country"] = "Colombia"
        vacancy["modality"]["mode"] = "remote"
        vacancy["modality"]["raw"] = "Remoto"

        artifact = build_candidate_preference_checks(
            person=_person(),
            opportunity=_opportunity(),
            candidate_preference_profile_artifact=_candidate_preference_profile(),
            vacancy_comparable_conditions_artifact=vacancy,
        )

        rows = {row["criterion_key"]: row for row in artifact["rows"]}
        self.assertEqual(rows["location"]["state"], "🟢 Cumple")

    def test_location_can_conflict_when_city_differs_and_no_relocation(self) -> None:
        vacancy = _vacancy_comparable_conditions()
        vacancy["location"]["normalized_city"] = "Cali"
        vacancy["location"]["raw"] = "Cali"
        artifact = build_candidate_preference_checks(
            person=_person(),
            opportunity=_opportunity(),
            candidate_preference_profile_artifact=_candidate_preference_profile(),
            vacancy_comparable_conditions_artifact=vacancy,
        )
        rows = {row["criterion_key"]: row for row in artifact["rows"]}
        self.assertEqual(rows["location"]["state"], "🔴 En conflicto")

    def test_build_requires_valid_input_artifacts(self) -> None:
        with self.assertRaises(CandidatePreferenceChecksBuildError):
            build_candidate_preference_checks(
                person=_person(),
                opportunity=_opportunity(),
                candidate_preference_profile_artifact={},
                vacancy_comparable_conditions_artifact=_vacancy_comparable_conditions(),
            )

        with self.assertRaises(CandidatePreferenceChecksBuildError):
            build_candidate_preference_checks(
                person=_person(),
                opportunity=_opportunity(),
                candidate_preference_profile_artifact=_candidate_preference_profile(),
                vacancy_comparable_conditions_artifact={},
            )


if __name__ == "__main__":
    unittest.main()
