import copy
import unittest
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch

from app.core.security import hash_password
from app.services import operator_store


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


class _FakeCollectionRef:
    def __init__(self, client: "_FakeFirestoreClient", collection_name: str):
        self._client = client
        self._collection_name = collection_name

    def document(self, doc_id: str) -> _FakeDocumentRef:
        return _FakeDocumentRef(self._client, self._collection_name, doc_id)


class _FakeFirestoreClient:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, dict]] = {}

    def collection(self, collection_name: str) -> _FakeCollectionRef:
        self._data.setdefault(collection_name, {})
        return _FakeCollectionRef(self, collection_name)


class OperatorStoreTests(unittest.TestCase):
    def test_seed_operator_preserves_existing_hash_in_production_when_env_falls_back_to_demo_hash(
        self,
    ) -> None:
        fake_client = _FakeFirestoreClient()
        original_hash = hash_password("correct-production-password")
        fake_client.collection("operators").document("tutor").set(
            {
                "operator_id": "tutor",
                "username": "tutor",
                "password_hash": original_hash,
                "active": True,
                "created_at": "2026-04-14T00:00:00+00:00",
                "updated_at": "2026-04-14T00:00:00+00:00",
            }
        )
        settings = SimpleNamespace(
            app_env="production",
            persistence_backend="firestore",
            firestore_seed_on_startup=True,
            tutor_username="tutor",
            tutor_password_hash=operator_store.DEFAULT_TUTOR_PASSWORD_HASH,
        )

        with patch.object(operator_store, "get_settings", return_value=settings):
            with patch.object(operator_store, "get_firestore_client", return_value=fake_client):
                operator_store.seed_operator()

        stored = fake_client.collection("operators").document("tutor").get().to_dict()
        assert stored is not None
        self.assertEqual(stored["password_hash"], original_hash)
        self.assertTrue(stored["active"])

    def test_seed_operator_rejects_new_production_operator_with_demo_hash(self) -> None:
        fake_client = _FakeFirestoreClient()
        settings = SimpleNamespace(
            app_env="production",
            persistence_backend="firestore",
            firestore_seed_on_startup=True,
            tutor_username="tutor",
            tutor_password_hash=operator_store.DEFAULT_TUTOR_PASSWORD_HASH,
        )

        with patch.object(operator_store, "get_settings", return_value=settings):
            with patch.object(operator_store, "get_firestore_client", return_value=fake_client):
                with self.assertRaises(RuntimeError) as ctx:
                    operator_store.seed_operator()

        self.assertIn("default demo password hash", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
