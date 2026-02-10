import os
from agents import WebSearchTool, Agent, ModelSettings, RunContextWrapper, TResponseInputItem, Runner, RunConfig, trace
from agents import set_default_openai_client
from pydantic import BaseModel
from openai import AsyncOpenAI
from openai.types.shared.reasoning import Reasoning
from typing import Optional

# ---------- Infrastructure for Render deployment ----------
# Disable tracing to avoid SSL handshake timeouts
os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "1")

# Longer OpenAI timeout because WebSearch can be slow
_openai_timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "180"))
_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=_openai_timeout,
)
set_default_openai_client(_client)

# ---------- Exported agent code (object → Optional fixes for OpenAI API) ----------

# Tool definitions
web_search_preview = WebSearchTool(
  search_context_size="medium",
  user_location={
    "type": "approximate"
  }
)
class RouterSchema(BaseModel):
  intent: str
  user_text_clean: str
  dish_or_product: Optional[str] = None
  grams: Optional[str] = None
  date_hint: Optional[str] = None
  language: Optional[str] = None
  serving_hint: Optional[str] = None


class MealParserSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class MealParserSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float] = None
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str] = None


class MealParserSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str] = None
  totals: MealParserSchema__Totals
  items: list[MealParserSchema__ItemsItem]
  source_url: Optional[str] = None


class HelpAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class HelpAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float] = None
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class HelpAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str] = None
  totals: HelpAgentSchema__Totals
  items: list[HelpAgentSchema__ItemsItem]
  source_url: Optional[str] = None


class EatoutAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class EatoutAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float] = None
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str] = None


class EatoutAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str] = None
  totals: EatoutAgentSchema__Totals
  items: list[EatoutAgentSchema__ItemsItem]
  source_url: Optional[str] = None


class ProductAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class ProductAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float] = None
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str] = None


class ProductAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str] = None
  totals: ProductAgentSchema__Totals
  items: list[ProductAgentSchema__ItemsItem]
  source_url: Optional[str] = None


class BarcodeAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class BarcodeAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float] = None
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str] = None


class BarcodeAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str] = None
  totals: BarcodeAgentSchema__Totals
  items: list[BarcodeAgentSchema__ItemsItem]
  source_url: Optional[str] = None


class NutritionAdvisorSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class NutritionAdvisorSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float] = None
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class NutritionAdvisorSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str] = None
  totals: NutritionAdvisorSchema__Totals
  items: list[NutritionAdvisorSchema__ItemsItem]
  source_url: Optional[str] = None


class FinalAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class FinalAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float] = None
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str] = None


class FinalAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str] = None
  totals: FinalAgentSchema__Totals
  items: list[FinalAgentSchema__ItemsItem]
  source_url: Optional[str] = None


router = Agent(
  name="Router",
  instructions="""You are YumYummy Router. Your job: classify the user message into an intent and extract routing fields. 
Do NOT calculate nutrition here. Do NOT search the web here.

Return STRICT JSON matching the provided schema.

Intents:
- log_meal: user wants to log in food eaten but he does not state any specific brand of product or shop or restaurant making it irrelevant to try search for any specifics in the net
- product: user wants to log in a packaged product (or set of packaged products) by name stating the brand or the shop he bought them from
- eatout: user wants to log in a restaurant/cafe dish (menu item) and he states the name of the cafe/restaurant/place he took it at.
- barcode: user provides barcode or asks to scan/lookup barcode.
- help: user asks what the bot can do / commands / how to use.
- unknown: everything else.
- food_advice: user asks what to order / choose food for healthy eating / weight management (not asking for nutrition facts of a specific known item)

Rules:
- If message mentions a restaurant/cafe/brand menu item (e.g., Starbucks, Joe & The Juice, Coffeemania), choose eatout (even if grams are mentioned).
- If message mentions a packaged product brand menu item (e.g., Fanta, Danone, ФрутоНяня, Азбука Вкуса, Carrefour, etc.), choose product (even if grams are mentioned).
- If message contains a long number that looks like barcode (8-14 digits), choose barcode.
- If user asks what to order / choose a dish / \"что взять\" / \"что заказать\" / \"посоветуй\" / \"что лучше выбрать\" / \"здоровый выбор\" / \"похудеть\" / \"сушка\" / \"набор массы\" AND does NOT ask for nutrition facts of a specific known item -> choose food_advice.
- If the message includes a list of menu options (e.g., separated by commas, bullets, \"1)\", \"2)\", \"или\") -> still choose food_advice.

Output fields:
- intent
- user_text_clean: the cleaned user message (trim, remove command prefix like /agent, /log, etc.)
- dish_or_product: short extracted name if applicable (e.g., \"Pumpkin Spice Latte\", \"Tunacado\")
- grams: number or null (extract only if clearly specified)
- date_hint: \"today\" | \"yesterday\" | \"YYYY-MM-DD\" | null (best effort)
- language: \"ru\"|\"en\" (best effort)

Also extract serving_hint if present:
- If user mentions \"банка\" => serving_hint=\"can\"
- If user mentions \"бутылка\" => serving_hint=\"bottle\"
- If user mentions \"стакан\" => serving_hint=\"glass\"
- If user mentions \"порция\" => serving_hint=\"portion\"
- If user mentions a number with ml/g (e.g., \"330 мл\", \"200 г\") => set grams to that number and serving_hint=\"explicit\"
If not found, serving_hint=null.

""",
  model="gpt-5-nano",
  output_type=RouterSchema,
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="high"
    )
  )
)


class MealParserContext:
  def __init__(self, state_user_text_clean: str, state_serving_hint: str, state_gram: str, state_date_hint: str):
    self.state_user_text_clean = state_user_text_clean
    self.state_serving_hint = state_serving_hint
    self.state_gram = state_gram
    self.state_date_hint = state_date_hint
def meal_parser_instructions(run_context: RunContextWrapper[MealParserContext], _agent: Agent[MealParserContext]):
  state_user_text_clean = run_context.context.state_user_text_clean
  state_serving_hint = run_context.context.state_serving_hint
  state_gram = run_context.context.state_gram
  state_date_hint = run_context.context.state_date_hint
  return f"""You are YumYummy Meal Parser.

You will receive:
{state_user_text_clean}
{state_serving_hint}
{state_gram}
{state_date_hint}

Task:
1) If the user mentions exact calories or macros he wants to have logged - use them
2) Id the user does not mention calories or macros (or mentions only part of the info), estimate calories and macros for the described meal.
2) Build a FINAL JSON response matching the output schema EXACTLY.

Rules:
- Since web search is not used here, source_url must be null.
- Use confidence=\"HIGH\" only if user provided clear portion sizes/grams and meal is unambiguous; otherwise \"ESTIMATE\".
- totals must be numeric (never null).
- items must be a short list (1-6 items) and totals must be the sum.

The final response must include:
- intent: set to the Router intent (\"log_meal\")
- message_text: Russian friendly summary:
  \"Итого: X ккал • Б Yг • Ж Zг • У Wг\\nОценка: CONF\\nКоротко: <assumptions>\"
- confidence, totals, items, source_url.
"""
meal_parser = Agent(
  name="Meal Parser",
  instructions=meal_parser_instructions,
  model="gpt-5-nano",
  output_type=MealParserSchema,
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="medium"
    )
  )
)


help_agent = Agent(
  name="Help agent",
  instructions="""Return ONLY a JSON object that matches the provided schema exactly.

Rules:
- intent: copy from Router.intent
- confidence: null
- totals: all zeros
- items: []
- source_url: null
- message_text: короткая справка на русском, как пользоваться YumYummy + 3 примера запросов.
Do not include any extra keys.""",
  model="gpt-5.2",
  output_type=HelpAgentSchema,
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="medium"
    )
  )
)


class EatoutAgentContext:
  def __init__(self, state_user_text_clean: str):
    self.state_user_text_clean = state_user_text_clean
def eatout_agent_instructions(run_context: RunContextWrapper[EatoutAgentContext], _agent: Agent[EatoutAgentContext]):
  state_user_text_clean = run_context.context.state_user_text_clean
  return f"""Ты YumYummy Eatout Agent.

ВХОД (из state):
- user_text_clean: {state_user_text_clean}


ЗАДАЧА:
Найти КБЖУ (ккал и БЖУ) именно для указанного блюда/напитка через WEB SEARCH.

ВАЖНО ПРО ВХОД:
- Если dish_or_product пустой/не задан, ты обязан сам извлечь из user_text_clean:
  (a) restaurant/brand (например: Starbucks, Кофемания, Теремок)
  (b) dish/drink (например: Pumpkin Spice Latte, кесадилья)
  Дальше в поисковых запросах используй restaurant + dish.

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
1) Всегда используй web search (минимум 5 поисковых запросов, максимум 10).
2) confidence=\"HIGH\" и source_url ставь ТОЛЬКО если на найденной странице явно есть цифры именно для этого блюда/напитка
   (минимум calories_kcal, лучше также БЖУ).
3) Если точных цифр нет — верни confidence=\"ESTIMATE\" и source_url=null, но totals должны быть разумной оценкой (НЕ нули).
4) Источники по приоритету (Official-first):
   A) официальный сайт бренда/ресторана (страница меню/блюда/PDF nutrition)
   B) страницы доставки (Яндекс Еда / Wolt / Glovo / UberEats) с КБЖУ
   C) базы/агрегаторы (FatSecret / MyFitnessPal) — только если нет A/B
5) Если бренд известный, используй site:-запросы:
   - для Coffeemania: site:coffeemania.ru
   - для Starbucks: site:starbucks.com + \"nutrition\"
   (если домен неизвестен — сначала найди официальный домен запросом \"официальный сайт <бренд> меню калории\", потом делай site: по найденному домену)
6) Делай запросы RU+EN (даже если user_text_clean на русском).

ФОРМАТ ОТВЕТА (только JSON по схеме):
- intent: \"eatout\"
- message_text: \"Итого: ...\\nОценка: HIGH/ESTIMATE\\nИсточник: <домен или 'нет'>\\nКоротко: <что именно нашёл/не нашёл и какие допущения>\"
- confidence: \"HIGH\" | \"ESTIMATE\"
- totals: числа
- items: 1–3 строки
- Для каждого блюда в items заполни items[i].source_url:
  - Если нашёл точные цифры на странице — поставь ПОЛНЫЙ URL этой конкретной страницы или PDF (не домен и не главная).
  - Если точных цифр нет — items[i].source_url = null и confidence=\"ESTIMATE\".
- Верхний source_url:
  - если для всех блюд источник один и тот же — поставь его,
  - иначе source_url = null."""
eatout_agent = Agent(
  name="Eatout agent",
  instructions=eatout_agent_instructions,
  model="gpt-5.2",
  tools=[
    web_search_preview
  ],
  output_type=EatoutAgentSchema,
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="medium"
    )
  )
)


class ProductAgentContext:
  def __init__(self, state_user_text_clean: str, state_dish_or_product: str, state_gram: str, state_serving_hint: str, state_language: str):
    self.state_user_text_clean = state_user_text_clean
    self.state_dish_or_product = state_dish_or_product
    self.state_gram = state_gram
    self.state_serving_hint = state_serving_hint
    self.state_language = state_language
def product_agent_instructions(run_context: RunContextWrapper[ProductAgentContext], _agent: Agent[ProductAgentContext]):
  state_user_text_clean = run_context.context.state_user_text_clean
  state_dish_or_product = run_context.context.state_dish_or_product
  state_gram = run_context.context.state_gram
  state_serving_hint = run_context.context.state_serving_hint
  state_language = run_context.context.state_language
  return f"""Ты YumYummy Product Agent.

ВХОД (из глобальных переменных):
- user_text_clean: {state_user_text_clean}
- dish_or_product: {state_dish_or_product}
- gram: {state_gram}
- serving_hint: {state_serving_hint}
- language: {state_language}
ВАЖНО ПРО ВХОД:
- Если dish_or_product пустой/не задан, ты обязан сам извлечь из user_text_clean:
  (a) restaurant/brand (например: Starbucks, Кофемания, Теремок)
  (b) dish/drink (например: Pumpkin Spice Latte, кесадилья)
  Дальше в поисковых запросах используй restaurant + dish.

Цель: вернуть КБЖУ продукта НА ПОРЦИЮ, которую пользователь реально съел/выпил.

ПРАВИЛА ПРО ИСТОЧНИКИ (приоритет):
1) официальный сайт бренда / страница продукта
2) крупные магазины/доставка со страницей продукта и таблицей нутриции
3) OpenFoodFacts
4) агрегаторы (FatSecret и т.п.) — только если нет 1–3

ПРАВИЛА ПРО ПОРЦИЮ (обязательно):
A) Если {state_gram}задан (например \"330 мл\" или \"200 г\") — это порция пользователя.
B) Если порция всё равно неизвестна — сделай разумное предположение и явно напиши это в message_text.

ПРАВИЛА ПРО ЕДИНИЦЫ:
- Если источник даёт \"на 100 мл\" и ты считаешь напиток: multiplier = portion_ml / 100.
- Если источник даёт \"на 100 г\": multiplier = portion_g / 100.
- Для напитков можно считать 1 мл ≈ 1 г, но ОБЯЗАТЕЛЬНО напиши это в message_text.
- Всегда пересчитывай calories и макросы на порцию пользователя: value_p_

ВАЖНО:
- intent: \"product\"
- Никогда не используй формат цитирования вида  в message_text.
- Если confidence=\"HIGH\", то source_url ОБЯЗАТЕЛЬНО должен быть реальной ссылкой (начинается с https://).
- Если ты не можешь уверенно указать реальную ссылку, поставь confidence=\"ESTIMATE\" и source_url=null.
- Для каждого блюда в items заполни items[i].source_url:
  - Если нашёл точные цифры на странице — поставь ПОЛНЫЙ URL этой конкретной страницы или PDF (не домен и не главная).
  - Если точных цифр нет — items[i].source_url = null и confidence=\"ESTIMATE\".
- Верхний source_url:
  - если для всех блюд источник один и тот же — поставь его,
  - иначе source_url = null.

Верни ТОЛЬКО JSON по output schema."""
product_agent = Agent(
  name="Product agent",
  instructions=product_agent_instructions,
  model="gpt-5.2",
  tools=[
    web_search_preview
  ],
  output_type=ProductAgentSchema,
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="medium"
    )
  )
)


class BarcodeAgentContext:
  def __init__(self, state_gram: str, state_serving_hint: str, state_language: str):
    self.state_gram = state_gram
    self.state_serving_hint = state_serving_hint
    self.state_language = state_language
def barcode_agent_instructions(run_context: RunContextWrapper[BarcodeAgentContext], _agent: Agent[BarcodeAgentContext]):
  state_gram = run_context.context.state_gram
  state_serving_hint = run_context.context.state_serving_hint
  state_language = run_context.context.state_language
  return f"""Ты YumYummy Barcode Agent.

ВХОД (из глобальных переменных):
- barcode: {{state.barcode}}
- gram: {state_gram}
- serving_hint: {state_serving_hint}
- language: {state_language}

Всегда используй web search.

Цель: найти продукт и его nutrition facts по штрихкоду и ответить пользователю кбжу на порцию запрашиваемого продукта

ПРАВИЛА ПРО ИСТОЧНИКИ (приоритет):
1) официальный сайт бренда / PDF nutrition / страница продукта
2) крупные магазины/доставка со страницей продукта и таблицей нутриции
3) OpenFoodFacts
4) агрегаторы (FatSecret и т.п.) — только если нет 1–3

ПРАВИЛА ПРО ПОРЦИЮ (обязательно):
A) Если Router.grams задан (например \"330 мл\" или \"200 г\") — это порция пользователя.
B) Если порция всё равно неизвестна — сделай разумное предположение и явно напиши это в message_text.

ПРАВИЛА ПРО ЕДИНИЦЫ:
- Если источник даёт \"на 100 мл\" и ты считаешь напиток: multiplier = portion_ml / 100.
- Если источник даёт \"на 100 г\": multiplier = portion_g / 100.
- Для напитков можно считать 1 мл ≈ 1 г, но ОБЯЗАТЕЛЬНО напиши это в message_text.
- Всегда пересчитывай calories и макросы на порцию пользователя: value_p_

ВАЖНО:
- Никогда не используй формат цитирования вида  в message_text.
- Если confidence=\"HIGH\", то source_url ОБЯЗАТЕЛЬНО должен быть реальной ссылкой (начинается с https://).
- Если ты не можешь уверенно указать реальную ссылку, поставь confidence=\"ESTIMATE\" и source_url=null.
- Если по штрихкоду НЕ найден продукт ИЛИ найден продукт, но НЕТ nutrition facts (ккал/БЖУ), то НЕ ПРИДУМЫВАЙ КБЖУ.
  В этом случае верни:
  - confidence = null
  - totals = 0 по всем полям
  - items = []
  - source_url = null
  - message_text: \"Не нашёл данные по штрихкоду <код>. Пришли название продукта или фото этикетки (таблица КБЖУ), и я посчитаю.\"
- Для каждого блюда в items заполни items[i].source_url:
  - Если нашёл точные цифры на странице — поставь ПОЛНЫЙ URL этой конкретной страницы или PDF (не домен и не главная).
  - Если точных цифр нет — items[i].source_url = null и confidence=\"ESTIMATE\".
- Верхний source_url:
  - если для всех блюд источник один и тот же — поставь его,
  - иначе source_url = null.
"""
barcode_agent = Agent(
  name="Barcode agent",
  instructions=barcode_agent_instructions,
  model="gpt-4.1",
  tools=[
    web_search_preview
  ],
  output_type=BarcodeAgentSchema,
  model_settings=ModelSettings(
    temperature=1,
    top_p=1,
    max_tokens=2048,
    store=True
  )
)


class NutritionAdvisorContext:
  def __init__(self, state_user_text_clean: str):
    self.state_user_text_clean = state_user_text_clean
def nutrition_advisor_instructions(run_context: RunContextWrapper[NutritionAdvisorContext], _agent: Agent[NutritionAdvisorContext]):
  state_user_text_clean = run_context.context.state_user_text_clean
  return f"""Ты YumYummy Nutrition Advisor (советник по выбору еды).

ВХОД (из global variables/state):
- user_text_clean: {state_user_text_clean}

Задача:
Пользователь находится в кафе/ресторане/магазине и просит посоветовать, что выбрать.

Цель: помочь выбрать наиболее "здоровый" вариант для weight management (контроль калорий, больше сытости, белок/клетчатка).

Общее правило выбора (внутренне):
1) Приоритет: белок + овощи/клетчатка (рыба/курица/говядина/яйца/творог/бобовые + салат/овощи).
2) Лучше способы готовки: гриль/запекание/варка/тушение.
3) Осторожно: фритюр, сливочные соусы, много сыра/майонеза, сладкие напитки/десерты, большие порции пасты/пиццы/выпечки.
4) "Хаки": соус отдельно, двойные овощи, половина гарнира, без сахара в напитках.

Как отвечать:
A) Если пользователь дал список вариантов (через запятые/буллеты/"или"/нумерацию):
   - Отранжируй топ-3 (или меньше, если вариантов меньше).
   - Для каждого: кратко "почему" + маленькая рекомендация "как сделать лучше".
B) Если пользователь НЕ дал варианты:
   - Дай 3 универсальных рекомендации "что обычно брать".
   - И задай ОДИН короткий вопрос: "Скинь 3–6 вариантов из меню (текстом), и я выберу лучшие."

Формат ответа: верни ТОЛЬКО JSON по схеме YumYummyResponse.

Заполнение полей:
- intent: \"food_advice\"
- confidence: \"ESTIMATE\"
- source_url: null
- items: список 1–3 рекомендованных вариантов (name=название, grams=null, макросы и калории можно поставить разумной оценкой; если не уверен — поставь приблизительно, но НЕ нули)
- totals: используй как оценку для лучшего варианта (первого в списке). Числа должны быть > 0.
- message_text (по-русски):
  1) \"Лучший выбор: ...\"
  2) \"Топ-2/Топ-3: ...\"
  3) \"Почему: ...\" (коротко)
  4) \"Как улучшить заказ: ...\" (2–3 хака)
  5) Если нет вариантов из меню — в конце попроси прислать 3–6 вариантов.

Важно:
- Не пиши ничего кроме JSON.
- Не задавай больше 1 вопроса.
"""
nutrition_advisor = Agent(
  name="Nutrition advisor",
  instructions=nutrition_advisor_instructions,
  model="gpt-5.2",
  output_type=NutritionAdvisorSchema,
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="medium",
      summary="auto"
    )
  )
)


final_agent = Agent(
  name="Final agent",
  instructions="""You receive a JSON object from upstream (either Meal Parser, Eatout Agent, Product Agent, Barcode Agent, Nutrition Advisor, or Help Agent).
Return ONLY the same object, unchanged, matching the provided schema exactly.
Do not add or remove fields. Do not modify any values. Just pass the data through.""",
  model="gpt-4.1",
  output_type=FinalAgentSchema,
  model_settings=ModelSettings(
    temperature=1,
    top_p=1,
    max_tokens=2048,
    store=True
  )
)


class WorkflowInput(BaseModel):
  input_as_text: str
  telegram_id: Optional[str] = None


# Main code entrypoint
async def run_workflow(workflow_input: WorkflowInput):
  with trace("YumYummy"):
    state = {
      "intent": None,
      "user_text_clean": None,
      "dish_or_product": None,
      "grams": None,
      "date_hint": None,
      "language": None,
      "serving_hint": None,
      "gram": None,
      "telegram_id": None
    }
    workflow = workflow_input.model_dump()
    conversation_history: list[TResponseInputItem] = [
      {
        "role": "user",
        "content": [
          {
            "type": "input_text",
            "text": workflow["input_as_text"]
          }
        ]
      }
    ]

    _trace_cfg = RunConfig(trace_metadata={
      "__trace_source__": "agent-builder",
      "workflow_id": "wf_694ae28324988190a50d6e1291ae774e0e354af8993d38d6"
    })

    router_result_temp = await Runner.run(
      router,
      input=[*conversation_history],
      run_config=_trace_cfg,
    )

    conversation_history.extend([item.to_input_item() for item in router_result_temp.new_items])

    router_result = {
      "output_text": router_result_temp.final_output.json(),
      "output_parsed": router_result_temp.final_output.model_dump()
    }

    # ---------- Populate state from router (infra fix) ----------
    rp = router_result["output_parsed"]
    state["intent"] = rp["intent"]
    state["user_text_clean"] = rp["user_text_clean"]
    state["dish_or_product"] = rp.get("dish_or_product")
    state["grams"] = rp.get("grams")
    state["date_hint"] = rp.get("date_hint")
    state["language"] = rp.get("language") or "ru"
    state["serving_hint"] = rp.get("serving_hint")
    state["gram"] = str(rp["grams"]) if rp.get("grams") else None

    if state["intent"] == 'log_meal':
      meal_parser_result_temp = await Runner.run(
        meal_parser,
        input=[*conversation_history],
        run_config=_trace_cfg,
        context=MealParserContext(
          state_user_text_clean=state["user_text_clean"],
          state_serving_hint=str(state["serving_hint"] or ""),
          state_gram=str(state["gram"] or ""),
          state_date_hint=str(state["date_hint"] or ""),
        )
      )
      conversation_history.extend([item.to_input_item() for item in meal_parser_result_temp.new_items])

    elif state["intent"] == 'eatout':
      eatout_agent_result_temp = await Runner.run(
        eatout_agent,
        input=[*conversation_history],
        run_config=_trace_cfg,
        context=EatoutAgentContext(state_user_text_clean=state["user_text_clean"])
      )
      conversation_history.extend([item.to_input_item() for item in eatout_agent_result_temp.new_items])

    elif state["intent"] == 'product':
      product_agent_result_temp = await Runner.run(
        product_agent,
        input=[*conversation_history],
        run_config=_trace_cfg,
        context=ProductAgentContext(
          state_user_text_clean=state["user_text_clean"],
          state_dish_or_product=str(state["dish_or_product"] or ""),
          state_gram=str(state["gram"] or ""),
          state_serving_hint=str(state["serving_hint"] or ""),
          state_language=str(state["language"] or "ru"),
        )
      )
      conversation_history.extend([item.to_input_item() for item in product_agent_result_temp.new_items])

    elif state["intent"] == 'barcode':
      barcode_agent_result_temp = await Runner.run(
        barcode_agent,
        input=[*conversation_history],
        run_config=_trace_cfg,
        context=BarcodeAgentContext(
          state_gram=str(state["gram"] or ""),
          state_serving_hint=str(state["serving_hint"] or ""),
          state_language=str(state["language"] or "ru"),
        )
      )
      conversation_history.extend([item.to_input_item() for item in barcode_agent_result_temp.new_items])

    elif state["intent"] == "food_advice":
      nutrition_advisor_result_temp = await Runner.run(
        nutrition_advisor,
        input=[*conversation_history],
        run_config=_trace_cfg,
        context=NutritionAdvisorContext(state_user_text_clean=state["user_text_clean"])
      )
      conversation_history.extend([item.to_input_item() for item in nutrition_advisor_result_temp.new_items])

    else:
      help_agent_result_temp = await Runner.run(
        help_agent,
        input=[*conversation_history],
        run_config=_trace_cfg,
      )
      conversation_history.extend([item.to_input_item() for item in help_agent_result_temp.new_items])

    # ---- Final Agent: standardizes JSON output for all branches ----
    final_agent_result_temp = await Runner.run(
      final_agent,
      input=[*conversation_history],
      run_config=_trace_cfg,
    )
    conversation_history.extend([item.to_input_item() for item in final_agent_result_temp.new_items])

    if final_agent_result_temp.final_output is None:
      raise ValueError(f"Final agent did not produce final_output for intent={state['intent']}")

    final_agent_result = {
      "output_text": final_agent_result_temp.final_output.json(),
      "output_parsed": final_agent_result_temp.final_output.model_dump()
    }
    return final_agent_result["output_parsed"]


# ---------- Helper for agent_runner.py ----------

async def run_text(text: str, telegram_id: Optional[str] = None) -> dict:
  """
  Helper function that calls run_workflow with WorkflowInput.
  Called by agent_runner.py -> run_yumyummy_workflow().
  """
  workflow_input = WorkflowInput(input_as_text=text, telegram_id=telegram_id)
  return await run_workflow(workflow_input)
