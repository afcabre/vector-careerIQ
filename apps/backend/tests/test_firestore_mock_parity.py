import copy
import os
import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from app.core.settings import get_settings
from app.services import artifact_store, opportunity_store


@dataclass
class _FakeStreamDoc:
    id: str
    _payload: dict

    def to_dict(self) -> dict:
        return copy.deepcopy(self._payload)


@dataclass
class _FakeSnapshot:
    _payload: dict | None

    @property
    def exists(self) -> bool:
        return self._payload is not None

    def to_dict(self) -> dict | None:
        if self._payload is None:
            return None
        return copy.deepcopy(self._payload)


class _FakeDocumentRef:
    def __init__(self, client: "_FakeFirestoreClient", collection_name: str, doc_id: str):
        self._client = client
        self._collection_name = collection_name
        self._doc_id = doc_id

    def set(self, payload: dict) -> None:
        self._client._data.setdefault(self._collection_name, {})
        self._client._data[self._collection_name][self._doc_id] = copy.deepcopy(payload)

    def get(self) -> _FakeSnapshot:
        payload = self._client._data.get(self._collection_name, {}).get(self._doc_id)
        return _FakeSnapshot(copy.deepcopy(payload) if payload is not None else None)

    def delete(self) -> None:
        self._client._data.setdefault(self._collection_name, {})
        self._client._data[self._collection_name].pop(self._doc_id, None)


class _FakeQuery:
    def __init__(
        self,
        client: "_FakeFirestoreClient",
        collection_name: str,
        filters: list[tuple[str, str, object]] | None = None,
        limit_count: int | None = None,
    ):
        self._client = client
        self._collection_name = collection_name
        self._filters = filters or []
        self._limit_count = limit_count

    def where(self, field: str, op: str, value: object) -> "_FakeQuery":
        return _FakeQuery(
            self._client,
            self._collection_name,
            [*self._filters, (field, op, value)],
            self._limit_count,
        )

    def limit(self, count: int) -> "_FakeQuery":
        return _FakeQuery(self._client, self._collection_name, self._filters, count)

    def stream(self):
        collection = self._client._data.get(self._collection_name, {})
        docs: list[_FakeStreamDoc] = []
        for doc_id, payload in collection.items():
            include = True
            for field, op, value in self._filters:
                if op != "==":
                    raise ValueError(f"Unsupported operation in fake query: {op}")
                if payload.get(field) != value:
                    include = False
                    break
            if include:
                docs.append(_FakeStreamDoc(id=doc_id, _payload=payload))
        if self._limit_count is not None:
            docs = docs[: self._limit_count]
        return docs


class _FakeCollectionRef:
    def __init__(self, client: "_FakeFirestoreClient", collection_name: str):
        self._client = client
        self._collection_name = collection_name

    def document(self, doc_id: str) -> _FakeDocumentRef:
        return _FakeDocumentRef(self._client, self._collection_name, doc_id)

    def where(self, field: str, op: str, value: object) -> _FakeQuery:
        return _FakeQuery(self._client, self._collection_name).where(field, op, value)

    def limit(self, count: int) -> _FakeQuery:
        return _FakeQuery(self._client, self._collection_name).limit(count)

    def stream(self):
        return _FakeQuery(self._client, self._collection_name).stream()


class _FakeFirestoreClient:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict]] = {}

    def collection(self, collection_name: str) -> _FakeCollectionRef:
        self._data.setdefault(collection_name, {})
        return _FakeCollectionRef(self, collection_name)


def _reset_memory_stores() -> None:
    opportunity_store._opportunities.clear()  # type: ignore[attr-defined]
    artifact_store._artifacts.clear()  # type: ignore[attr-defined]


def _run_common_flow() -> dict[str, object]:
    saved, created = opportunity_store.save_from_search(
        person_id="p-001",
        source_provider="tavily",
        source_url="https://example.com/jobs/backend-1",
        title="Backend Engineer",
        company="Acme",
        location="Remote",
        snippet="FastAPI and SQL",
        normalized_payload={"provider": "tavily"},
    )
    _, created_again = opportunity_store.save_from_search(
        person_id="p-001",
        source_provider="tavily",
        source_url="https://example.com/jobs/backend-1",
        title="Backend Engineer",
        company="Acme",
        location="Remote",
        snippet="FastAPI and SQL",
        normalized_payload={"provider": "tavily"},
    )
    updated = opportunity_store.update_opportunity(
        person_id="p-001",
        opportunity_id=saved["opportunity_id"],
        status="analyzed",
        notes="reviewed",
    )
    assert updated is not None

    artifact_store.upsert_current_artifact(
        person_id="p-001",
        opportunity_id=saved["opportunity_id"],
        artifact_type="cover_letter",
        content="Cover v1",
    )
    artifact_store.upsert_current_artifact(
        person_id="p-001",
        opportunity_id=saved["opportunity_id"],
        artifact_type="cover_letter",
        content="Cover v2",
    )

    opportunities = opportunity_store.list_opportunities("p-001")
    current_artifacts = artifact_store.list_current_artifacts("p-001", saved["opportunity_id"])
    cross_person = opportunity_store.find_opportunity("p-002", saved["opportunity_id"])

    return {
        "created_first": created,
        "created_second": created_again,
        "opportunities_count": len(opportunities),
        "status": opportunities[0]["status"] if opportunities else "",
        "notes": opportunities[0]["notes"] if opportunities else "",
        "current_artifacts_count": len(current_artifacts),
        "current_cover": current_artifacts[0]["content"] if current_artifacts else "",
        "cross_person_is_none": cross_person is None,
    }


class FirestoreMockParityTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PERSISTENCE_BACKEND"] = "memory"
        get_settings.cache_clear()
        _reset_memory_stores()

    def tearDown(self) -> None:
        get_settings.cache_clear()
        _reset_memory_stores()

    def test_firestore_mock_matches_memory_for_core_store_behavior(self) -> None:
        # Baseline in memory.
        memory_result = _run_common_flow()
        memory_total_artifacts = len(artifact_store._artifacts)  # type: ignore[attr-defined]

        # Same flow with firestore mocked.
        _reset_memory_stores()
        fake_client = _FakeFirestoreClient()
        fake_settings = SimpleNamespace(persistence_backend="firestore")
        with patch.object(opportunity_store, "get_settings", return_value=fake_settings):
            with patch.object(opportunity_store, "get_firestore_client", return_value=fake_client):
                with patch.object(artifact_store, "get_settings", return_value=fake_settings):
                    with patch.object(artifact_store, "get_firestore_client", return_value=fake_client):
                        firestore_result = _run_common_flow()

        firestore_total_artifacts = len(fake_client._data.get("application_artifacts", {}))

        self.assertEqual(memory_result["created_first"], True)
        self.assertEqual(memory_result["created_second"], False)
        self.assertEqual(memory_result["opportunities_count"], 1)
        self.assertEqual(memory_result["status"], "analyzed")
        self.assertEqual(memory_result["notes"], "reviewed")
        self.assertEqual(memory_result["current_artifacts_count"], 1)
        self.assertEqual(memory_result["current_cover"], "Cover v2")
        self.assertEqual(memory_result["cross_person_is_none"], True)
        self.assertEqual(memory_total_artifacts, 2)

        self.assertEqual(firestore_result, memory_result)
        self.assertEqual(firestore_total_artifacts, memory_total_artifacts)


if __name__ == "__main__":
    unittest.main()
