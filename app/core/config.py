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

    # Public @username of the Telegram bot (no @). Used to build t.me deep links
    # for the reverse app->Telegram linking flow.
    telegram_bot_username: str = "yum_yummybot"

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

    # PostHog Persons API — used by the ad-platform server-side
    # bridges (TikTok Events API, Meta Conversions API) to look up a
    # user's $ttp / $ttclid / $fbp / $fbc that the LP captured into
    # their PostHog person profile. Different from posthog_api_key:
    # this needs a *personal* API key with read access to persons.
    posthog_personal_api_key: Optional[str] = None
    posthog_project_id: Optional[str] = None  # numeric, e.g. "175093"

    # TikTok Events API — server-side counterpart to the browser
    # TikTok pixel installed on yumyummy.ai. We send
    # CompleteRegistration / StartTrial / CompletePayment events
    # straight from the FastAPI backend so the TikTok ads algorithm
    # can optimize toward real paid conversions (which happen inside
    # the Telegram bot, where the browser pixel can't reach).
    # Disabled (no-op) unless both pixel_code AND access_token are set.
    tiktok_pixel_code: Optional[str] = None      # same id as the browser pixel
    tiktok_access_token: Optional[str] = None    # from TikTok Events Manager
    tiktok_test_event_code: Optional[str] = None  # optional: route to TT Test Events

    # Meta Conversions API — server-side counterpart to the browser
    # Meta Pixel installed on yumyummy.ai. Same role as the TikTok
    # bridge above: emits CompleteRegistration / StartTrial /
    # Subscribe straight from the FastAPI backend so Meta's ads
    # algorithm can optimize for real paid conversions instead of
    # only optimizing for the LP `Lead` event.
    # Disabled (no-op) unless both pixel_id AND access_token are set.
    meta_pixel_id: Optional[str] = None           # same as browser pixel id
    meta_access_token: Optional[str] = None       # from Meta Events Manager
    meta_capi_test_event_code: Optional[str] = None  # optional: TEST_xxx code
    meta_api_version: str = "v21.0"               # Graph API version

    # Internal developer allowlist. Comma-separated Telegram numeric IDs
    # allowed to run hidden dev/QA commands (e.g. /forceonboarding). When
    # unset, nobody is authorized and those commands silently no-op, so they
    # can't be discovered or abused by real users.
    dev_telegram_ids: Optional[str] = None

    # Billing / Paddle
    paddle_enabled: bool = False
    paddle_environment: str = "sandbox"  # "sandbox" | "production"
    paddle_api_key: Optional[str] = None
    paddle_webhook_secret: Optional[str] = None
    paddle_client_side_token: Optional[str] = None
    paddle_price_id_monthly: Optional[str] = None
    paddle_price_id_yearly: Optional[str] = None

    # ------------------------------------------------------------------
    # Mobile app — authentication (JWT)
    # ------------------------------------------------------------------
    # HS256 signing secret for the access tokens we mint for the iOS/Android
    # app. Leave unset in environments that don't serve the app (the auth
    # endpoints will return 503 rather than mint insecure tokens).
    jwt_secret: Optional[str] = None
    jwt_access_ttl_days: int = 30

    # Sign in with Apple / Google — the `aud` we expect in the provider's
    # identity/ID token. Comma-separated values are accepted (e.g. an iOS
    # client id plus a web client id for Google).
    apple_client_id: Optional[str] = None   # iOS bundle id / Apple Services ID
    google_client_id: Optional[str] = None

    # Passwordless email login (one-time 6-digit code).
    auth_email_code_ttl_minutes: int = 15
    # DEV ONLY: when true, the request endpoint returns the code in its JSON
    # response so flows can be tested before an email provider is wired up.
    auth_email_debug_return_code: bool = False

    # Telegram <-> app linking code lifetime.
    auth_link_code_ttl_minutes: int = 15

    # ------------------------------------------------------------------
    # Mobile app — trial & Adapty
    # ------------------------------------------------------------------
    # Default free-trial length for app sign-ups. Adapty drives the actual
    # value per A/B cohort (we currently test 3 vs 7), validated against the
    # allow-list below.
    app_trial_days_default: int = 3
    app_trial_days_allowed: str = "3,7"

    adapty_enabled: bool = False
    # Shared secret Adapty sends in the webhook's Authorization header.
    adapty_webhook_secret: Optional[str] = None
    # Map Adapty vendor product ids -> our internal plan ids.
    adapty_product_monthly: Optional[str] = None
    adapty_product_yearly: Optional[str] = None

    # ------------------------------------------------------------------
    # Object storage (Cloudflare R2 / AWS S3) for meal photos
    # ------------------------------------------------------------------
    storage_enabled: bool = False
    storage_bucket: Optional[str] = None
    storage_region: Optional[str] = None
    storage_endpoint_url: Optional[str] = None   # set this for Cloudflare R2
    storage_access_key_id: Optional[str] = None
    storage_secret_access_key: Optional[str] = None
    storage_public_base_url: Optional[str] = None  # CDN / public read base
    storage_presign_ttl_seconds: int = 900

    @property
    def app_trial_days_allowed_set(self) -> set[int]:
        out: set[int] = set()
        for part in (self.app_trial_days_allowed or "").split(","):
            part = part.strip()
            if part.isdigit():
                out.add(int(part))
        out.add(self.app_trial_days_default)
        return out

    @property
    def apple_client_id_set(self) -> set[str]:
        return {p.strip() for p in (self.apple_client_id or "").split(",") if p.strip()}

    @property
    def google_client_id_set(self) -> set[str]:
        return {p.strip() for p in (self.google_client_id or "").split(",") if p.strip()}

    @property
    def dev_telegram_id_set(self) -> set[int]:
        """Parsed set of authorized developer Telegram IDs."""
        if not self.dev_telegram_ids:
            return set()
        out: set[int] = set()
        for part in self.dev_telegram_ids.split(","):
            part = part.strip()
            if part.isdigit():
                out.add(int(part))
        return out

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
