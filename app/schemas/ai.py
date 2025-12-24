from typing import Optional

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


class AgentResponse(BaseModel):
    """Ответ агента."""
    intent: str  # "log_meal" | "show_today" | "show_week" | "needs_clarification" | "error"
    reply_text: str
    meal: Optional[dict] = None
    day_summary: Optional[dict] = None
    week_summary: Optional[dict] = None
