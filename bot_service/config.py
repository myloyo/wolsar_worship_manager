from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    telegram_bot_token: SecretStr = SecretStr("")
    bot_service_token: SecretStr = SecretStr("")
    backend_url: str = "http://localhost:8000/api/v1"
    web_url: str = "http://localhost:8080"
    offset_file: str = "bot-data/offset.txt"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
