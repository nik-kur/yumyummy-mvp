"""
Agent v2 configuration.

Reads keys straight from the environment (.env is loaded lazily so the module
can be imported without side effects in tests). Never imports app.core.config
to stay decoupled from the production Settings object.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Optional

from dotenv import load_dotenv

_loaded = False


def _ensure_env() -> None:
    global _loaded
    if not _loaded:
        load_dotenv()  # no-op if already loaded / absent
        _loaded = True


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    _ensure_env()
    return os.environ.get(name, default)


# ---------------------------------------------------------------------------
# Model registry per variant
# ---------------------------------------------------------------------------
# Variant ids used across pipelines and the eval runner:
#   v2g   — Gemini 3 Flash (fast, cheap; grounding via Google Search)
#   v2g35 — Gemini 3.5 Flash (smarter, pricier; grounding via Google Search)
#   v2s   — Perplexity Sonar for branded search; Gemini Flash-Lite for parse
#   v2o   — OpenAI single-call control (gpt-5-mini + web_search, capped)

GEMINI_FLASH = "gemini-3-flash-preview"
GEMINI_FLASH_35 = "gemini-3.5-flash"
GEMINI_FLASH_LITE = "gemini-3.1-flash-lite"
SONAR = "sonar"
SONAR_PRO = "sonar-pro"
OPENAI_MINI = "gpt-5-mini"
OPENAI_NANO = "gpt-5-nano"


@dataclass
class VariantSpec:
    variant: str
    branded_provider: str          # "gemini" | "perplexity" | "openai"
    branded_model: str
    parse_provider: str            # cheap model for generic parse
    parse_model: str
    photo_provider: str
    photo_model: str


VARIANTS: Dict[str, VariantSpec] = {
    "v2g": VariantSpec(
        variant="v2g",
        branded_provider="gemini", branded_model=GEMINI_FLASH,
        parse_provider="gemini", parse_model=GEMINI_FLASH,
        photo_provider="gemini", photo_model=GEMINI_FLASH,
    ),
    "v2g35": VariantSpec(
        variant="v2g35",
        branded_provider="gemini", branded_model=GEMINI_FLASH_35,
        parse_provider="gemini", parse_model=GEMINI_FLASH,
        photo_provider="gemini", photo_model=GEMINI_FLASH_35,
    ),
    "v2s": VariantSpec(
        variant="v2s",
        branded_provider="perplexity", branded_model=SONAR,
        parse_provider="gemini", parse_model=GEMINI_FLASH,
        photo_provider="gemini", photo_model=GEMINI_FLASH,
    ),
    "v2o": VariantSpec(
        variant="v2o",
        branded_provider="openai", branded_model=OPENAI_MINI,
        parse_provider="openai", parse_model=OPENAI_NANO,
        photo_provider="openai", photo_model=OPENAI_MINI,
    ),
}


# ---------------------------------------------------------------------------
# Pricing (USD per 1M tokens unless stated). July 2026.
# ---------------------------------------------------------------------------
@dataclass
class Rates:
    input_per_m: float
    output_per_m: float
    # per single web-search query (grounding / tool call)
    search_per_call: float = 0.0
    # flat request fee (Perplexity charges per request by context size)
    request_fee: float = 0.0


PRICING: Dict[str, Rates] = {
    GEMINI_FLASH: Rates(0.50, 3.00, search_per_call=0.014),
    GEMINI_FLASH_35: Rates(1.50, 9.00, search_per_call=0.014),
    GEMINI_FLASH_LITE: Rates(0.25, 1.50, search_per_call=0.014),
    SONAR: Rates(1.00, 1.00, request_fee=0.008),       # medium context
    SONAR_PRO: Rates(3.00, 15.00, request_fee=0.010),
    OPENAI_MINI: Rates(0.25, 2.00, search_per_call=0.010),
    OPENAI_NANO: Rates(0.05, 0.40, search_per_call=0.010),
}

FDC_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"
OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}"

DEFAULT_TIMEOUT_S = float(env("AGENT_V2_TIMEOUT_S", "60") or 60)
