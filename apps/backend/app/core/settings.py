from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_TUTOR_PASSWORD_HASH = (
    "fb86fb757d1241d512865070e05ccb5d17dfaa11a4b2ca04b89bacad17530ad4"
)


class Settings(BaseSettings):
    app_env: str = "local"
    persistence_backend: str = "memory"
    session_cookie_name: str = "session_id"
    session_ttl_minutes: int = 480
    session_cookie_secure: bool = False
    login_rate_limit_window_seconds: int = 300
    login_rate_limit_max_attempts: int = 5
    login_rate_limit_block_seconds: int = 900
    tutor_username: str = "tutor"
    tutor_password_hash: str = DEFAULT_TUTOR_PASSWORD_HASH
    session_secret: str = "change-this-session-secret"
    firebase_project_id: str = ""
    firebase_client_email: str = ""
    firebase_private_key: str = ""
    firebase_credentials_file: str = ""
    firestore_seed_on_startup: bool = True
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    pinecone_api_key: str = ""
    pinecone_index_name: str = ""
    pinecone_index_host: str = ""
    tavily_api_key: str = ""
    rapidapi_key: str = ""
    rapidapi_adzuna_host: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    remotive_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
