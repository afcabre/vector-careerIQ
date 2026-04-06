import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException

import app.api.request_traces as request_traces_api
import app.services.search_service as search_service
from app.core.security import SessionData
from app.core.settings import get_settings
from app.services import person_store
from app.services.person_store import get_person, seed_persons
from app.services.request_trace_store import add_request_trace, list_request_traces, reset_request_traces


def _clear_in_memory_state() -> None:
    person_store._persons.clear()  # type: ignore[attr-defined]
    reset_request_traces()


class RequestTracesTests(unittest.TestCase):
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

    def test_request_traces_endpoint_filters_by_person_destination_and_opportunity(self) -> None:
        add_request_trace(
            person_id="p-001",
            opportunity_id="o-001",
            destination="openai",
            flow_key="chat_stream",
            request_payload={"messages": [{"role": "user", "content": "hola"}]},
        )
        add_request_trace(
            person_id="p-001",
            opportunity_id="o-001",
            destination="tavily",
            flow_key="search_culture_tavily",
            request_payload={"body": {"query": "culture company"}},
        )
        add_request_trace(
            person_id="p-001",
            destination="remotive",
            flow_key="search_jobs_remotive",
            request_payload={"url": "https://remotive.com/api/remote-jobs?search=python"},
        )
        add_request_trace(
            person_id="p-002",
            destination="openai",
            flow_key="chat_stream",
            request_payload={"messages": [{"role": "user", "content": "otro"}]},
        )

        all_items = request_traces_api.list_person_request_traces(
            person_id="p-001",
            destination=None,
            opportunity_id=None,
            limit=50,
            _=self.session,
        )
        self.assertEqual(len(all_items.items), 3)
        self.assertTrue(all(item.person_id == "p-001" for item in all_items.items))

        openai_items = request_traces_api.list_person_request_traces(
            person_id="p-001",
            destination="openai",
            opportunity_id=None,
            limit=50,
            _=self.session,
        )
        self.assertEqual(len(openai_items.items), 1)
        self.assertEqual(openai_items.items[0].destination, "openai")
        self.assertEqual(openai_items.items[0].flow_key, "chat_stream")

        opportunity_items = request_traces_api.list_person_request_traces(
            person_id="p-001",
            destination=None,
            opportunity_id="o-001",
            limit=50,
            _=self.session,
        )
        self.assertEqual(len(opportunity_items.items), 2)
        self.assertTrue(all(item.opportunity_id == "o-001" for item in opportunity_items.items))

    def test_request_traces_endpoint_rejects_unknown_person(self) -> None:
        with self.assertRaises(HTTPException) as missing_person:
            request_traces_api.list_person_request_traces(
                person_id="p-unknown",
                destination=None,
                opportunity_id=None,
                limit=50,
                _=self.session,
            )
        self.assertEqual(missing_person.exception.status_code, 404)
        self.assertEqual(missing_person.exception.detail, "Person not found")

    def test_search_registers_provider_request_traces(self) -> None:
        person = get_person("p-001")
        assert person is not None
        settings = get_settings()
        settings.rapidapi_key = "test-key"
        settings.rapidapi_adzuna_host = "test-host"
        settings.tavily_api_key = "test-key"

        with patch.object(search_service, "_adzuna_search_via_rapidapi", return_value=[]):
            with patch.object(search_service, "_remotive_search", return_value=[]):
                with patch.object(search_service, "_tavily_search", return_value=[]):
                    search_service.search_opportunities(
                        person=person,
                        query="python backend",
                        max_results=6,
                        settings=settings,
                    )

        traces = list_request_traces(person_id="p-001", limit=50)
        destinations = {item["destination"] for item in traces}
        self.assertIn("adzuna", destinations)
        self.assertIn("remotive", destinations)
        self.assertIn("tavily", destinations)


if __name__ == "__main__":
    unittest.main()
