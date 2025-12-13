from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    telegram_bot_token: str
    backend_base_url: str
    openai_api_key: str

    # чтобы .env мог содержать ключ, даже если фича временно не используется
    tavily_api_key: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
