from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class ParseMealRequest(BaseModel):
    text: str


class MealParsed(BaseModel):
    description: str
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    accuracy_level: str
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProductMealRequest(BaseModel):
    """Запрос на парсинг продукта по штрихкоду или названию."""
    barcode: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    store: Optional[str] = None
    locale: str = "ru-RU"


class RestaurantMealRequest(BaseModel):
    """Запрос на парсинг блюда из ресторана."""
    restaurant: str
    dish: str
    locale: str = "ru-RU"


class RestaurantTextRequest(BaseModel):
    """Запрос на парсинг блюда из ресторана по свободному тексту."""
    text: str
    locale: str = "ru-RU"


class AgentRequest(BaseModel):
    """Запрос к агенту."""
    user_id: int
    text: str
    date: Optional[str] = None  # YYYY-MM-DD format, defaults to today
    conversation_context: Optional[str] = None  # Previous conversation context for clarifications


class AgentResponse(BaseModel):
    """Ответ агента."""
    intent: str  # "log_meal" | "show_today" | "show_week" | "needs_clarification" | "error"
    reply_text: str
    meal: Optional[dict] = None
    day_summary: Optional[dict] = None
    week_summary: Optional[dict] = None


class WorkflowRunRequest(BaseModel):
    """Запрос на запуск workflow."""
    telegram_id: str
    text: str
    image_url: Optional[str] = None


class WorkflowTotals(BaseModel):
    """Итоговые значения КБЖУ."""
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float


class WorkflowItem(BaseModel):
    """Элемент в результате workflow."""
    name: str
    grams: Optional[float] = None
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    source_url: Optional[str] = None


class WorkflowRunResponse(BaseModel):
    """Ответ workflow."""
    intent: str
    message_text: str
    confidence: Optional[str] = None
    totals: WorkflowTotals
    items: List[WorkflowItem]
    source_url: Optional[str] = None


# Context API schemas for agent tools
class ContextDayTotals(BaseModel):
    """Totals for a day."""
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float


class ContextDayItem(BaseModel):
    """Meal entry item for context API."""
    name: str
    grams: Optional[float] = None
    calories_kcal: float
    protein_g: float
    fat_g: float
    carbs_g: float
    created_at: str  # ISO datetime


class ContextDayResponse(BaseModel):
    """Response for GET /context/day."""
    date: str  # YYYY-MM-DD
    telegram_id: str
    entries_count: int
    totals: ContextDayTotals
    items: List[ContextDayItem]


class MealsRecentResponse(BaseModel):
    """Response for GET /meals/recent."""
    telegram_id: str
    limit: int
    items: List[ContextDayItem]
