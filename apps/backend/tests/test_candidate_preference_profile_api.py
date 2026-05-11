import os
import unittest
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException

import app.api.persons as persons_api
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import person_store
from app.services.person_store import seed_persons


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]


class CandidatePreferenceProfileApiTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PERSISTENCE_BACKEND"] = "memory"
        get_settings.cache_clear()
        _clear_in_memory_state()
        seed_persons()
        self.session = SessionData(
            username="tutor",
            expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    def tearDown(self) -> None:
        get_settings.cache_clear()
        _clear_in_memory_state()

    def test_recompute_candidate_preference_profile_persists_artifact(self) -> None:
        response = persons_api.recompute_candidate_preference_profile("p-001", self.session)
        self.assertEqual(response.status, "draft")
        self.assertEqual(response.artifact["person_id"], "p-001")
        self.assertEqual(
            response.artifact["contract_version"],
            "candidate_preference_profile.v1",
        )

        fetched = persons_api.get_candidate_preference_profile("p-001", self.session)
        self.assertEqual(fetched.status, "draft")
        self.assertEqual(fetched.artifact["person_id"], "p-001")

    def test_recompute_candidate_preference_profile_404s_for_unknown_person(self) -> None:
        with self.assertRaises(HTTPException) as error:
            persons_api.recompute_candidate_preference_profile("p-missing", self.session)
        self.assertEqual(error.exception.status_code, 404)

    def test_update_person_recomputes_candidate_preference_profile(self) -> None:
        response = persons_api.update_person(
            "p-001",
            persons_api.UpdatePersonRequest(
                accepted_locations=["Bogotá D.C."],
                accepted_modalities=["hybrid", "remote"],
                contract_types_accepted=["indefinite", "service_contract"],
                salary_expectation_min=16000000,
                salary_currency="COP",
                salary_period="monthly",
            ),
            self.session,
        )

        self.assertEqual(response.candidate_preference_profile_status, "draft")
        fetched = persons_api.get_candidate_preference_profile("p-001", self.session)
        self.assertEqual(fetched.status, "draft")
        self.assertEqual(
            fetched.artifact["comparable_preferences"]["accepted_modalities"],
            ["hybrid", "remote"],
        )
        self.assertEqual(
            fetched.artifact["comparable_preferences"]["contract_types_accepted"],
            ["indefinite", "service_contract"],
        )


if __name__ == "__main__":
    unittest.main()
