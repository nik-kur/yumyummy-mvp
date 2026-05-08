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
    
    # Internal API token for agent tools (also reused by /admin/billing)
    internal_api_token: Optional[str] = None

    # Internal API token used between the Telegram bot and FastAPI backend
    # (for /billing/*, /agent/run, /ai/agent). Kept separate from
    # internal_api_token to avoid colliding with the admin token already
    # provisioned on Render.
    internal_api_token_backend: Optional[str] = None

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

    # Sentry / observability
    sentry_dsn: Optional[str] = None
    sentry_environment: Optional[str] = None  # e.g. "production" / "staging" / "dev"
    sentry_traces_sample_rate: float = 0.0    # 0.0 disables perf tracing; bump later if needed

    # PostHog / product analytics. Same project key as the marketing
    # site so backend-emitted events land on the same user profiles
    # captured on the LP. Leave ``posthog_api_key`` unset in dev to
    # disable backend capture (the SDK will no-op).
    posthog_api_key: Optional[str] = None
    posthog_host: str = "https://eu.i.posthog.com"

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
