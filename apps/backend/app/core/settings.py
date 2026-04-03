from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_TUTOR_PASSWORD_HASH = (
    "d67eb631bc4496840bbb59e74f57e9e6f36f3f4f2367d7fad81f4f652d49a6b5"
)


class Settings(BaseSettings):
    app_env: str = "local"
    session_cookie_name: str = "session_id"
    session_ttl_minutes: int = 480
    session_cookie_secure: bool = False
    tutor_username: str = "tutor"
    tutor_password_hash: str = DEFAULT_TUTOR_PASSWORD_HASH
    session_secret: str = "change-this-session-secret"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
