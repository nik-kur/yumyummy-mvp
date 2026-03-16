from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file before reading environment variables
load_dotenv()


class Settings(BaseSettings):
    database_url: str
    telegram_bot_token: str
    backend_base_url: str
    openai_api_key: str

    # чтобы .env мог содержать ключ, даже если фича временно не используется
    tavily_api_key: Optional[str] = None
    
    # Internal API token for agent tools
    internal_api_token: Optional[str] = None

    # Billing / Telegram Stars
    billing_trial_days: int = 3
    billing_monthly_price_xtr: int = 350
    billing_yearly_price_xtr: int = 2940
    billing_paywall_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
