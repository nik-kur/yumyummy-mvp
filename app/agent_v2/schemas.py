"""
Agent v2 result schemas.

The public result shape mirrors app/schemas/ai.py:WorkflowRunResponse so v2
outputs are directly comparable with v1 eval results and could be persisted by
the existing agent_persist path unchanged if v2 ever ships.
"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class NullTolerantModel(BaseModel):
    """LLMs sometimes emit null for optional strings/numbers despite the schema."""

    @field_validator("*", mode="before")
    @classmethod
    def _null_to_default(cls, v, info):
        if v is None:
            field = cls.model_fields.get(info.field_name)
            if field is not None and field.annotation in (str, float, int, bool):
                if field.is_required():
                    return {str: "", float: 0.0, int: 0, bool: False}[field.annotation]
                return field.get_default()
        return v


class Totals(BaseModel):
    calories_kcal: float = 0
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0


class Item(BaseModel):
    name: str
    grams: Optional[float] = None
    calories_kcal: float = 0
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0
    source_url: Optional[str] = None


class StageUsage(BaseModel):
    """Usage/cost for one provider call inside a pipeline."""
    stage: str                      # e.g. "parse", "branded_search", "fdc_lookup"
    provider: str
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    search_queries: int = 0
    duration_ms: float = 0
    cost_usd: float = 0


class Assessment(BaseModel):
    """HOW the numbers were obtained — machine-readable, additive on the wire
    (25(1)+). The mobile app renders a localized human sentence from `method`.

    Methods: label (read off a label/menu in the photo), off (barcode DB),
    official (brand's official site), web (other live verified page),
    usda (matched to USDA FDC), usda_components (dish decomposed into USDA
    components), photo (visual ID, per-item sources vary), estimate (pure AI
    guess, nothing verifiable).
    """
    method: str = "estimate"
    # Domain the main source lives on (vkusvill.ru, fdc.nal.usda.gov, ...).
    domain: Optional[str] = None
    # True when the portion size was assumed/eyeballed rather than stated.
    portion_estimated: bool = False
    # How many breakdown lines carry a verifiable source, out of how many.
    verified_items: int = 0
    total_items: int = 0


class V2Result(BaseModel):
    intent: str
    message_text: str = ""
    confidence: Optional[str] = None
    totals: Totals = Field(default_factory=Totals)
    items: List[Item] = Field(default_factory=list)
    source_url: Optional[str] = None
    # Additive (25(1)+): how the numbers were obtained. Survives to the wire.
    assessment: Optional[Assessment] = None

    # v2 extras (not part of the v1 wire format)
    variant: str = ""
    stages: List[StageUsage] = Field(default_factory=list)
    total_duration_ms: float = 0
    total_cost_usd: float = 0
    error: Optional[str] = None
    # Domains confirmed by provider citations/grounding — for eval scoring.
    cited_domains: List[str] = Field(default_factory=list)

    def add_stage(self, stage: StageUsage) -> None:
        self.stages.append(stage)
        self.total_cost_usd = round(self.total_cost_usd + stage.cost_usd, 6)

    def to_v1_dict(self) -> dict:
        """The exact WorkflowRunResponse-compatible payload (+ additive fields)."""
        return {
            "intent": self.intent,
            "message_text": self.message_text,
            "confidence": self.confidence,
            "totals": self.totals.model_dump(),
            "items": [i.model_dump() for i in self.items],
            "source_url": self.source_url,
            "assessment": self.assessment.model_dump() if self.assessment else None,
        }


# ---------------------------------------------------------------------------
# LLM-facing structured-output schemas (kept minimal and provider-agnostic).
# Empty string "" is used instead of null so the same JSON Schema works across
# Gemini / Perplexity / OpenAI structured-output dialects.
# ---------------------------------------------------------------------------

class ParsedItem(NullTolerantModel):
    """One food item extracted from free text / photo by the parse call."""
    name: str                       # user-facing name, user's language
    grams: float                    # best-estimate portion in grams
    explicit_grams: bool = False    # True if the user stated the amount
    fdc_query: str                  # concise ENGLISH generic-food query for USDA FDC
    is_branded: bool = False        # True if tied to a brand/restaurant
    brand: str = ""
    # Photo pipeline: "label" | "label_partial" | "estimate" (see llm_schemas).
    nutrition_source: str = "estimate"
    # Model's own macro estimate — fallback when FDC has no confident match.
    est_calories_kcal: float = 0
    est_protein_g: float = 0
    est_fat_g: float = 0
    est_carbs_g: float = 0


class ParseResult(NullTolerantModel):
    intent: str = "log_meal"        # router decision when parse doubles as router
    items: List[ParsedItem]
    language: str = "ru"
    note: str = ""


class BrandedItem(NullTolerantModel):
    name: str
    grams: float = 0
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    source_url: str = ""


class BrandedResult(NullTolerantModel):
    items: List[BrandedItem]
    confidence: str                 # "HIGH" | "ESTIMATE"
    source_url: str = ""
    official_domain: str = ""       # brand's official site per the model
    note: str = ""


class AdvisorOption(NullTolerantModel):
    name: str
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    source_url: str = ""


class AdvisorResult(NullTolerantModel):
    message_text: str
    items: List[AdvisorOption]
    source_url: str = ""
