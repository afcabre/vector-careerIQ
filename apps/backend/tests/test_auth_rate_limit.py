import os
import unittest

from fastapi import HTTPException
from fastapi.responses import Response
from starlette.requests import Request

import app.api.auth as auth_api
from app.core.security import hash_password
from app.core.settings import get_settings
from app.services import session_store
from app.services.login_rate_limit_store import reset_login_rate_limits


def _fake_request(ip: str = "127.0.0.1") -> Request:
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "path": "/api/auth/login",
        "headers": [],
        "client": (ip, 12345),
        "scheme": "http",
        "query_string": b"",
    }
    return Request(scope)


def _clear_state() -> None:
    session_store._sessions.clear()  # type: ignore[attr-defined]
    reset_login_rate_limits()


class AuthRateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["PERSISTENCE_BACKEND"] = "memory"
        os.environ["TUTOR_USERNAME"] = "tutor"
        os.environ["TUTOR_PASSWORD_HASH"] = hash_password("correct-password")
        os.environ["LOGIN_RATE_LIMIT_WINDOW_SECONDS"] = "60"
        os.environ["LOGIN_RATE_LIMIT_MAX_ATTEMPTS"] = "2"
        os.environ["LOGIN_RATE_LIMIT_BLOCK_SECONDS"] = "300"
        get_settings.cache_clear()
        _clear_state()

    def tearDown(self) -> None:
        get_settings.cache_clear()
        _clear_state()

    def test_login_blocks_after_repeated_failed_attempts_in_window(self) -> None:
        payload = auth_api.LoginRequest(username="tutor", password="wrong-password")
        settings = get_settings()

        with self.assertRaises(HTTPException) as first:
            auth_api.login(payload=payload, request=_fake_request(), response=Response(), settings=settings)
        self.assertEqual(first.exception.status_code, 401)

        with self.assertRaises(HTTPException) as second:
            auth_api.login(payload=payload, request=_fake_request(), response=Response(), settings=settings)
        self.assertEqual(second.exception.status_code, 429)

        with self.assertRaises(HTTPException) as third:
            auth_api.login(payload=payload, request=_fake_request(), response=Response(), settings=settings)
        self.assertEqual(third.exception.status_code, 429)

    def test_successful_login_clears_failure_counter_for_same_key(self) -> None:
        settings = get_settings()
        bad_payload = auth_api.LoginRequest(username="tutor", password="wrong-password")
        good_payload = auth_api.LoginRequest(username="tutor", password="correct-password")

        with self.assertRaises(HTTPException) as first:
            auth_api.login(payload=bad_payload, request=_fake_request(), response=Response(), settings=settings)
        self.assertEqual(first.exception.status_code, 401)

        ok = auth_api.login(
            payload=good_payload,
            request=_fake_request(),
            response=Response(),
            settings=settings,
        )
        self.assertTrue(ok.authenticated)
        self.assertEqual(ok.username, "tutor")

        with self.assertRaises(HTTPException) as second:
            auth_api.login(payload=bad_payload, request=_fake_request(), response=Response(), settings=settings)
        self.assertEqual(second.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
