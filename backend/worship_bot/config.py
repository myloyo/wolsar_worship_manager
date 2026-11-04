from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = Field(default="", repr=False)
    database_username: str = "worship_bot"
    database_password: SecretStr = SecretStr("")
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "worship_bot"
    web_url: str = "http://localhost:5173"
    cookie_secure: bool = False
    vapid_private_key: SecretStr | None = None
    vapid_public_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-6.1-sol"
    telegram_bot_token: SecretStr | None = None
    vk_bot_token: SecretStr | None = None

    @model_validator(mode="after")
    def configure_database(self) -> "Settings":
        if not self.database_url:
            self.database_url = URL.create(
                "postgresql+asyncpg",
                username=self.database_username,
                password=self.database_password.get_secret_value(),
                host=self.database_host,
                port=self.database_port,
                database=self.database_name,
            ).render_as_string(hide_password=False)
        return self

    bot_service_token: SecretStr | None = None
    jwt_secret: SecretStr | None = None
    jwt_lifetime_minutes: int = Field(default=10080, gt=0)
    registration_consent_version: str = "2026-10"
    registration_draft_lifetime_minutes: int = 1440
    initial_developer_provider: str | None = None
    initial_developer_external_user_id: str | None = None

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
