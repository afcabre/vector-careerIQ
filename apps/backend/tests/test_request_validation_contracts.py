import unittest

from pydantic import ValidationError

from app.api.auth import LoginRequest
from app.api.chat import SendMessageRequest
from app.api.opportunities import ImportTextRequest, ImportUrlRequest
from app.api.persons import CreatePersonRequest
from app.api.search import SearchRequest


class RequestValidationContractsTests(unittest.TestCase):
    def test_login_request_requires_non_empty_credentials(self) -> None:
        with self.assertRaises(ValidationError):
            LoginRequest(username="", password="secret")
        with self.assertRaises(ValidationError):
            LoginRequest(username="tutor", password="")

    def test_send_message_request_enforces_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            SendMessageRequest(message="")
        with self.assertRaises(ValidationError):
            SendMessageRequest(message="x" * 4001)

        ok = SendMessageRequest(message="mensaje valido")
        self.assertEqual(ok.message, "mensaje valido")

    def test_search_request_enforces_query_and_limits(self) -> None:
        with self.assertRaises(ValidationError):
            SearchRequest(query="a", max_results=6)
        with self.assertRaises(ValidationError):
            SearchRequest(query="python", max_results=21)

        ok = SearchRequest(query="python backend", max_results=6)
        self.assertEqual(ok.max_results, 6)

    def test_import_requests_enforce_required_min_lengths(self) -> None:
        with self.assertRaises(ValidationError):
            ImportUrlRequest(source_url="bad")
        with self.assertRaises(ValidationError):
            ImportUrlRequest(source_url="https://example.com/job/1", raw_text="corto")
        with self.assertRaises(ValidationError):
            ImportTextRequest(title="", raw_text="texto largo suficiente")
        with self.assertRaises(ValidationError):
            ImportTextRequest(title="Rol", raw_text="corto")

        ok_url = ImportUrlRequest(
            source_url="https://example.com/job/1",
            raw_text="descripcion suficiente de vacante",
        )
        self.assertTrue(ok_url.source_url.startswith("https://"))

        ok_text = ImportTextRequest(title="Backend Engineer", raw_text="texto suficientemente largo")
        self.assertEqual(ok_text.title, "Backend Engineer")

    def test_create_person_request_validates_minimum_profile(self) -> None:
        with self.assertRaises(ValidationError):
            CreatePersonRequest(
                full_name="",
                target_roles=["Backend Engineer"],
                location="Bogota",
                years_experience=5,
                skills=["Python"],
            )
        with self.assertRaises(ValidationError):
            CreatePersonRequest(
                full_name="Camila Torres",
                target_roles=[],
                location="Bogota",
                years_experience=5,
                skills=["Python"],
            )
        with self.assertRaises(ValidationError):
            CreatePersonRequest(
                full_name="Camila Torres",
                target_roles=["Backend Engineer"],
                location="Bogota",
                years_experience=81,
                skills=["Python"],
            )

        ok = CreatePersonRequest(
            full_name="Camila Torres",
            target_roles=["Backend Engineer"],
            location="Bogota",
            years_experience=5,
            skills=["Python", "FastAPI"],
        )
        self.assertEqual(ok.years_experience, 5)


if __name__ == "__main__":
    unittest.main()
