import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException

import app.api.search_provider_admin as search_provider_admin_api
import app.services.search_service as search_service
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import person_store
from app.services.person_store import get_person, seed_persons
from app.services.search_provider_store import (
    PROVIDER_ADZUNA,
    PROVIDER_TAVILY,
    get_search_provider_config,
    reset_search_provider_configs,
)


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    reset_search_provider_configs()


class SearchProviderAdminTests(unittest.TestCase):
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

    def test_list_search_provider_configs_returns_defaults(self) -> None:
        response = search_provider_admin_api.list_configs(_=self.session)
        keys = {item.provider_key for item in response.items}
        self.assertEqual(keys, {"adzuna", "remotive", "tavily"})
        self.assertTrue(all(item.is_enabled for item in response.items))

    def test_patch_search_provider_config_updates_flag(self) -> None:
        updated = search_provider_admin_api.patch_config(
            provider_key=PROVIDER_ADZUNA,
            payload=search_provider_admin_api.UpdateSearchProviderConfigRequest(is_enabled=False),
            session=self.session,
        )
        self.assertFalse(updated.is_enabled)
        self.assertEqual(updated.updated_by, "tutor")

        refreshed = get_search_provider_config(PROVIDER_ADZUNA)
        self.assertFalse(refreshed["is_enabled"])

    def test_patch_search_provider_config_rejects_unknown_provider(self) -> None:
        with self.assertRaises(HTTPException) as unknown:
            search_provider_admin_api.patch_config(
                provider_key="unknown",
                payload=search_provider_admin_api.UpdateSearchProviderConfigRequest(is_enabled=False),
                session=self.session,
            )
        self.assertEqual(unknown.exception.status_code, 404)

    def test_search_respects_disabled_tavily_provider(self) -> None:
        person = get_person("p-001")
        assert person is not None
        settings = get_settings()
        settings.tavily_api_key = "test-key"
        search_provider_admin_api.patch_config(
            provider_key=PROVIDER_TAVILY,
            payload=search_provider_admin_api.UpdateSearchProviderConfigRequest(is_enabled=False),
            session=self.session,
        )

        with patch.object(search_service, "_adzuna_search_via_rapidapi", return_value=[]):
            with patch.object(search_service, "_remotive_search", return_value=[]):
                with patch.object(search_service, "_tavily_search", return_value=[]) as mocked_tavily:
                    payload = search_service.search_opportunities(
                        person=person,
                        query="ux designer",
                        max_results=6,
                        settings=settings,
                    )

        self.assertFalse(mocked_tavily.called)
        self.assertTrue(
            any("Tavily provider disabled from admin config" in warning for warning in payload["warnings"])
        )
        tavily_status = next(
            (item for item in payload["provider_status"] if item["provider_key"] == "tavily"),
            None,
        )
        self.assertIsNotNone(tavily_status)
        self.assertEqual(tavily_status["status"], "skipped")
        self.assertEqual(tavily_status["reason"], "disabled_from_admin")
        self.assertFalse(tavily_status["attempted"])

    def test_search_truncates_tavily_query_to_400_chars(self) -> None:
        person = get_person("p-001")
        assert person is not None
        settings = get_settings()
        settings.tavily_api_key = "test-key"
        settings.rapidapi_key = ""
        settings.rapidapi_adzuna_host = ""

        captured_query: dict[str, str] = {}

        def _capture_tavily(query: str, max_results: int, settings_arg):  # noqa: ARG001
            captured_query["value"] = query
            return []

        with patch.object(search_service, "build_prompt_query", return_value="x" * 520):
            with patch.object(search_service, "_remotive_search", return_value=[]):
                with patch.object(search_service, "_tavily_search", side_effect=_capture_tavily):
                    payload = search_service.search_opportunities(
                        person=person,
                        query="ux designer",
                        max_results=6,
                        settings=settings,
                    )

        self.assertEqual(len(captured_query.get("value", "")), 400)
        self.assertTrue(
            any("Tavily query exceeded 400 chars and was truncated" in warning for warning in payload["warnings"])
        )
        tavily_status = next(
            (item for item in payload["provider_status"] if item["provider_key"] == "tavily"),
            None,
        )
        self.assertIsNotNone(tavily_status)
        self.assertEqual(tavily_status["status"], "ok")
        self.assertTrue(tavily_status["attempted"])
        self.assertTrue(tavily_status.get("query_truncated"))


if __name__ == "__main__":
    unittest.main()
