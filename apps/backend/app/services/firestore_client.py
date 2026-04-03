from threading import Lock

import firebase_admin
from firebase_admin import credentials, firestore

from app.core.settings import Settings


_client_lock = Lock()
_firestore_client: firestore.Client | None = None


def _certificate_payload(settings: Settings) -> dict[str, str]:
    return {
        "type": "service_account",
        "project_id": settings.firebase_project_id,
        "client_email": settings.firebase_client_email,
        "private_key": settings.firebase_private_key.replace("\\n", "\n"),
        "token_uri": "https://oauth2.googleapis.com/token",
    }


def _build_credentials(settings: Settings) -> credentials.Base:
    if settings.firebase_credentials_file:
        return credentials.Certificate(settings.firebase_credentials_file)

    if (
        settings.firebase_project_id
        and settings.firebase_client_email
        and settings.firebase_private_key
    ):
        return credentials.Certificate(_certificate_payload(settings))

    raise RuntimeError(
        "Firestore backend requires FIREBASE_CREDENTIALS_FILE or "
        "FIREBASE_PROJECT_ID + FIREBASE_CLIENT_EMAIL + FIREBASE_PRIVATE_KEY",
    )


def get_firestore_client(settings: Settings) -> firestore.Client:
    global _firestore_client

    with _client_lock:
        if _firestore_client is not None:
            return _firestore_client

        app_name = f"app-{settings.firebase_project_id or 'default'}"
        try:
            firebase_app = firebase_admin.get_app(app_name)
        except ValueError:
            firebase_app = firebase_admin.initialize_app(
                credential=_build_credentials(settings),
                options={"projectId": settings.firebase_project_id or None},
                name=app_name,
            )

        _firestore_client = firestore.client(app=firebase_app)
        return _firestore_client
