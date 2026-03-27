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
    billing_monthly_price_xtr: int = 1199
    billing_yearly_price_xtr: int = 9599
    billing_paywall_enabled: bool = True

    # Billing / Gumroad
    gumroad_enabled: bool = False
    gumroad_access_token: Optional[str] = None
    gumroad_seller_id: Optional[str] = None
    gumroad_product_permalink: Optional[str] = None
    gumroad_webhook_secret: Optional[str] = None
    gumroad_claim_secret: Optional[str] = None
    gumroad_monthly_price_cents: int = 999
    gumroad_yearly_price_cents: int = 8999

    # Billing / Paddle
    paddle_enabled: bool = False
    paddle_environment: str = "sandbox"  # "sandbox" | "production"
    paddle_api_key: Optional[str] = None
    paddle_webhook_secret: Optional[str] = None
    paddle_client_side_token: Optional[str] = None
    paddle_price_id_monthly: Optional[str] = None
    paddle_price_id_yearly: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
