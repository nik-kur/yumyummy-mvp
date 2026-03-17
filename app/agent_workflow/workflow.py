import os
from agents import WebSearchTool, Agent, ModelSettings, RunContextWrapper, TResponseInputItem, Runner, RunConfig, trace
from agents import set_default_openai_client
from pydantic import BaseModel
from openai import AsyncOpenAI
from openai.types.shared.reasoning import Reasoning
from typing import Optional

# ---------- Infrastructure for Render deployment ----------
os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "1")

_openai_timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "180"))
_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=_openai_timeout,
)
set_default_openai_client(_client)

# ---------- Exported agent code (from platform) ----------

# Tool definitions
web_search_preview = WebSearchTool(
  search_context_size="medium",
  user_location={
    "type": "approximate"
  }
)
web_search_preview1 = WebSearchTool(
  user_location={
    "type": "approximate",
    "country": None,
    "region": None,
    "city": None,
    "timezone": None
  },
  search_context_size="medium"
)
class RouterSchema(BaseModel):
  intent: str
  user_text_clean: str
  dish_or_product: str
  grams: str
  date_hint: str
  language: str
  serving_hint: str


class MealParserSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class MealParserSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float]
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str]


class MealParserSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: MealParserSchema__Totals
  items: list[MealParserSchema__ItemsItem]
  source_url: Optional[str]


class HelpAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class HelpAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float]
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class HelpAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: HelpAgentSchema__Totals
  items: list[HelpAgentSchema__ItemsItem]
  source_url: Optional[str]


class EatoutAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class EatoutAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float]
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str]


class EatoutAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: EatoutAgentSchema__Totals
  items: list[EatoutAgentSchema__ItemsItem]
  source_url: Optional[str]


class ProductAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class ProductAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float]
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str]


class ProductAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: ProductAgentSchema__Totals
  items: list[ProductAgentSchema__ItemsItem]
  source_url: Optional[str]


class BarcodeAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class BarcodeAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float]
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str]


class BarcodeAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: BarcodeAgentSchema__Totals
  items: list[BarcodeAgentSchema__ItemsItem]
  source_url: Optional[str]


class NutritionAdvisorSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class NutritionAdvisorSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float]
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class NutritionAdvisorSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: NutritionAdvisorSchema__Totals
  items: list[NutritionAdvisorSchema__ItemsItem]
  source_url: Optional[str]


class FinalAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class FinalAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float]
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str]


class FinalAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: FinalAgentSchema__Totals
  items: list[FinalAgentSchema__ItemsItem]
  source_url: Optional[str]


class PhotoMealAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class PhotoMealAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float]
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str]


class PhotoMealAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: PhotoMealAgentSchema__Totals
  items: list[PhotoMealAgentSchema__ItemsItem]
  source_url: Optional[str]


class NutritionLabelAgentSchema__Totals(BaseModel):
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float


class NutritionLabelAgentSchema__ItemsItem(BaseModel):
  name: str
  grams: Optional[float]
  calories_kcal: float
  protein_g: float
  fat_g: float
  carbs_g: float
  source_url: Optional[str]


class NutritionLabelAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: NutritionLabelAgentSchema__Totals
  items: list[NutritionLabelAgentSchema__ItemsItem]
  source_url: Optional[str]


router = Agent(
  name="Router",
  instructions="""You are YumYummy Router. Your job: classify the user message into an intent and extract routing fields.
Do NOT calculate nutrition here. Do NOT search the web here.

Return STRICT JSON matching the provided schema.

=== CRITICAL: IMAGE DETECTION (check FIRST) ===
BEFORE choosing any intent, check if the message contains an image/photo.
If an image IS present:
  - If the image shows prepared food/dishes on a plate/table WITHOUT a clear packaged product brand -> intent = \"photo_meal\". Do NOT choose log_meal.
  - If the image shows a packaged product with a clearly visible brand name/logo -> intent = \"product\".
  - If the image shows a nutrition facts table/label (таблица пищевой ценности) -> intent = \"nutrition_label\".
  - If the image doesn't show specific brands or nutrition labels, choose \"photo_meal\".
These image rules OVERRIDE all text-based rules below.
=== END IMAGE DETECTION ===

Intents (for TEXT-ONLY messages or after image rules have been applied):

- log_meal: user wants to log in food eaten but he does not state any specific brand of product or shop or restaurant making it irrelevant to try search for any specifics in the net.
- product: user wants to log in a packaged product (or set of packaged products) by name stating the brand or the shop he bought them from
- eatout: user wants to log in a restaurant/cafe dish (menu item) and he states the name of the cafe/restaurant/place he took it at.
- barcode: user provides barcode or asks to scan/lookup barcode.
- help: user asks what the bot can do / commands / how to use.
- unknown: everything else.

- photo_meal: user sent a PHOTO of food/dish and there is NO identifiable packaged product brand or store visible.
- nutrition_label: user sent a PHOTO of a nutrition facts table / label / этикетка with KBJU values printed on it.

Rules:
- Never give back intent food_advice. Food advice is handled externally.
- If message mentions a restaurant/cafe/brand menu item (e.g., Starbucks, Joe & The Juice, Coffeemania), choose eatout (even if grams are mentioned).
- If message mentions a packaged product brand menu item (e.g., Fanta, Danone, ФрутоНяня, Азбука Вкуса, Carrefour, etc.), choose product (even if grams are mentioned).
- If the message contains BOTH branded items (with known brand/store) AND generic/homemade items without a brand — choose intent 'product' (or 'eatout' if restaurant). The downstream agent will handle the mix.
- If message contains a long number that looks like barcode (8-14 digits), choose barcode.

- IMAGE RULES (apply only when an image is present in the message):   - If the image shows prepared food/dishes on a plate/table WITHOUT a clear packaged product brand -> choose photo_meal.
- If the image shows a packaged product with a clearly visible brand name/logo (e.g., Coca-Cola bottle, Danone yogurt package) -> choose product. Extract the brand name into dish_or_product.
- If the image shows a nutrition facts table/label (таблица пищевой ценности / этикетка с КБЖУ) -> choose nutrition_label.
- If the image is ambiguous (e.g., food + brand partially visible), prefer product if brand is readable, otherwise photo_meal.
 - If there is no image (text-only message), these IMAGE RULES do not apply.

Output fields:
- intent
- user_text_clean: the cleaned user message (trim, remove command prefix like /agent, /log, etc.)
- dish_or_product: short extracted name if applicable (e.g., \"Pumpkin Spice Latte\", \"Tunacado\")
- If intent is photo_meal or nutrition_label, set dish_or_product to what you see in the image (e.g., \"pasta with chicken\", \"nutrition label - yogurt\").
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
- totals must be numeric
- items must be a short list (1-6 items) and totals must be the sum.

The final response must include:
- intent: set to the Router intent (\"log_meal\")
- message_text: English friendly summary:
  \"Total: X kcal • P Yg • F Zg • C Wg\\nConfidence: CONF\\nNote: <assumptions>\"
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
- message_text: short help text in English on how to use YumYummy + 3 example queries.
Do not include any extra keys.""",
  model="gpt-5-mini",
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
  return f"""You are YumYummy Eatout Agent.

INPUT (from state):
- user_text_clean: {state_user_text_clean}


TASK:
Find calories and macros (kcal, protein, fat, carbs) for the specified dish/drink via WEB SEARCH.

IMPORTANT ABOUT INPUT:
- If dish_or_product is empty/unset, you must extract from user_text_clean:
  (a) restaurant/brand (e.g.: Starbucks, Coffeemania, Chipotle)
  (b) dish/drink (e.g.: Pumpkin Spice Latte, Caesar salad)
  Then use restaurant + dish in your search queries.

MANDATORY RULES:
1) Always use web search (minimum 5 search queries, maximum 10).
2) Set confidence=\"HIGH\" and source_url ONLY if the found page explicitly contains numbers for this specific dish/drink
   (at minimum calories_kcal, preferably also protein/fat/carbs).
3) If no exact numbers found — return confidence=\"ESTIMATE\" and source_url=null, but totals must be a reasonable estimate (NOT zeros).
4) Source priority (Official-first):
   A) official brand/restaurant website (menu/dish page/PDF nutrition)
   B) delivery pages (UberEats / DoorDash / Wolt / Glovo) with nutrition info
   C) databases/aggregators (FatSecret / MyFitnessPal) — only if A/B unavailable
5) For well-known brands, use site: queries:
   - for Coffeemania: site:coffeemania.ru
   - for Starbucks: site:starbucks.com + \"nutrition\"
   (if domain is unknown — first find the official domain with a query like \"official site <brand> menu calories\", then use site: with the found domain)
6) Make queries in both EN and the user's language (even if user_text_clean is not in English).
7) If the user's message contains multiple items and some have known brands while others don't: (1) For branded items — use web search to find exact nutrition and set source_url per item. (2) For generic/unbranded items — estimate nutrition yourself without web search, set source_url=null for those items and their confidence to 'ESTIMATE'. (3) In message_text, clearly indicate which items have verified data (with source) and which are AI estimates.

RESPONSE FORMAT (JSON only, matching the schema):
- intent: \"eatout\"
- message_text: \"Total: ...\\nConfidence: HIGH/ESTIMATE\\nSource: <domain or 'none'>\\nNote: <what was found/not found and assumptions made>\"
- confidence: \"HIGH\" | \"ESTIMATE\"
- totals: numbers
- items: 1-3 rows
- For each dish in items fill items[i].source_url:
  - If exact numbers found on a page — set the FULL URL of that specific page or PDF (not the domain or homepage).
  - If no exact numbers — items[i].source_url = null and confidence=\"ESTIMATE\".
- Top-level source_url:
  - if all dishes share the same source — set it,
  - otherwise source_url = null."""
eatout_agent = Agent(
  name="Eatout agent",
  instructions=eatout_agent_instructions,
  model="gpt-5-mini",
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
  return f"""You are YumYummy Product Agent.

INPUT (from global variables):
- user_text_clean: {state_user_text_clean}
- dish_or_product: {state_dish_or_product}
- gram: {state_gram}
- serving_hint: {state_serving_hint}
- language: {state_language}

IMPORTANT ABOUT INPUT:
- If dish_or_product is empty/unset, you must extract from user_text_clean:
  (a) brand (e.g.: Danone, Fanta, Chobani)
  (b) product (e.g.: Greek yogurt 5%, Diet Coke 330ml)
  Then use brand + product in your search queries.
- If the user's message contains multiple items and some have known brands while others don't: (1) For branded items — use web search to find exact nutrition and set source_url per item. (2) For generic/unbranded items — estimate nutrition yourself without web search, set source_url=null for those items and their confidence to 'ESTIMATE'. (3) In message_text, clearly indicate which items have verified data (with source) and which are AI estimates.
- PHOTO (if present):
-- If the message contains a photo — examine it carefully.
-- Identify the brand/product name from the packaging, logo, text on the package.
-- If the photo shows volume/weight (e.g., \"330 ml\", \"500 g\") — use it as the serving size.
-- Use the visually identified brand and product for web search queries.
-- If dish_or_product from Router is empty but the brand is visible in the photo — extract it from the photo.

Goal: return nutrition per SERVING that the user actually ate/drank.

SOURCE RULES (priority):
1) official brand website / product page
2) major stores/delivery with product page and nutrition table
3) OpenFoodFacts
4) aggregators (FatSecret etc.) — only if 1-3 unavailable

SERVING RULES (mandatory):
A) If {state_gram} is set (e.g. \"330 ml\" or \"200 g\") — that is the user's serving.
B) If serving is still unknown — make a reasonable assumption and explicitly state it in message_text.

UNIT RULES:
- If source gives \"per 100 ml\" and you're calculating a drink: multiplier = portion_ml / 100.
- If source gives \"per 100 g\": multiplier = portion_g / 100.
- For drinks, you can assume 1 ml ≈ 1 g, but you MUST state this in message_text.
- Always recalculate calories and macros to the user's serving size.

IMPORTANT:
- intent: \"product\"
- Never use citation format like  in message_text.
- If confidence=\"HIGH\", then source_url MUST be a real link (starts with https://).
- If you cannot confidently provide a real link, set confidence=\"ESTIMATE\" and source_url=null.
- For each item in items fill items[i].source_url:
  - If exact numbers found on a page — set the FULL URL of that specific page or PDF (not the domain or homepage).
  - If no exact numbers — items[i].source_url = null and confidence=\"ESTIMATE\".
- Top-level source_url:
  - if all items share the same source — set it,
  - otherwise source_url = null.

Return ONLY JSON matching the output schema."""
product_agent = Agent(
  name="Product agent",
  instructions=product_agent_instructions,
  model="gpt-5-mini",
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
  return f"""You are YumYummy Barcode Agent.

INPUT (from global variables):
- barcode: {{state.barcode}}
- gram: {state_gram}
- serving_hint: {state_serving_hint}
- language: {state_language}

Always use web search.

Goal: find the product and its nutrition facts by barcode and return calories/macros per serving to the user.

SOURCE RULES (priority):
1) official brand website / PDF nutrition / product page
2) major stores/delivery with product page and nutrition table
3) OpenFoodFacts
4) aggregators (FatSecret etc.) — only if 1-3 unavailable

SERVING RULES (mandatory):
A) If Router.grams is set (e.g. \"330 ml\" or \"200 g\") — that is the user's serving.
B) If serving is still unknown — make a reasonable assumption and explicitly state it in message_text.

UNIT RULES:
- If source gives \"per 100 ml\" and you're calculating a drink: multiplier = portion_ml / 100.
- If source gives \"per 100 g\": multiplier = portion_g / 100.
- For drinks, you can assume 1 ml ≈ 1 g, but you MUST state this in message_text.
- Always recalculate calories and macros to the user's serving size.

IMPORTANT:
- Never use citation format like  in message_text.
- If confidence=\"HIGH\", then source_url MUST be a real link (starts with https://).
- If you cannot confidently provide a real link, set confidence=\"ESTIMATE\" and source_url=null.
- If the product is NOT found by barcode OR found but has NO nutrition facts (calories/macros), do NOT make up nutrition data.
  In that case return:
  - confidence = null
  - totals = 0 for all fields
  - items = []
  - source_url = null
  - message_text: \"Could not find data for barcode <code>. Send the product name or a photo of the nutrition label, and I'll calculate it.\"
- For each item in items fill items[i].source_url:
  - If exact numbers found on a page — set the FULL URL of that specific page or PDF (not the domain or homepage).
  - If no exact numbers — items[i].source_url = null and confidence=\"ESTIMATE\".
- Top-level source_url:
  - if all items share the same source — set it,
  - otherwise source_url = null.
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
  def __init__(self, state_user_text_clean: str, nutrition_context: Optional[str] = None):
    self.state_user_text_clean = state_user_text_clean
    self.nutrition_context = nutrition_context
def nutrition_advisor_instructions(run_context: RunContextWrapper[NutritionAdvisorContext], _agent: Agent[NutritionAdvisorContext]):
  state_user_text_clean = run_context.context.state_user_text_clean
  nutrition_context = run_context.context.nutrition_context
  return f"""You are YumYummy Nutrition Advisor (food choice advisor).

INPUT (from global variables/state):
- user_text_clean: {state_user_text_clean}
- nutrition_context: {nutrition_context}
  (JSON with user's nutrition data for today: target_calories, target_protein_g, target_fat_g, target_carbs_g — daily goals; eaten_calories, eaten_protein_g, eaten_fat_g, eaten_carbs_g — already eaten; remaining_calories, remaining_protein_g, remaining_fat_g, remaining_carbs_g — remaining)

Task:
The user is at a cafe/restaurant/store and is asking for advice on what to choose.

Goal: help pick the "healthiest" option for weight management (calorie control, more satiety, protein/fiber).

General selection rules (internal):
1) Use nutrition_context data as the basis for recommendations:
   - Consider how much calories/macros the user has left for today
   - Prioritize options that fit better within the remaining budget
   - If the user has few calories left — recommend lighter options
   - If protein is lacking — prioritize high-protein dishes
2) Priority: protein + vegetables/fiber (fish/chicken/beef/eggs/cottage cheese/legumes + salad/vegetables).
3) Preferred cooking methods: grilled/baked/boiled/stewed.
4) Be cautious of: deep-fried, cream sauces, heavy cheese/mayo, sugary drinks/desserts, large portions of pasta/pizza/pastries.
5) "Hacks": sauce on the side, double vegetables, half the side dish, no sugar in drinks.

WEB SEARCH (mandatory if a restaurant/brand is mentioned):
1) Always use web search if the user mentions a specific restaurant, cafe, or brand (minimum 5 queries, maximum 10).
2) For well-known brands, use site: queries:
   - for Coffeemania: site:coffeemania.ru
   - for Starbucks: site:starbucks.com + \"nutrition\"
   (if domain is unknown — first find the official domain with a query like \"official site <brand> menu calories\", then use site: with the found domain)
3) Make queries in both EN and the user's language.
4) Source priority (Official-first):
   A) official brand/restaurant website (menu/dish page/PDF nutrition)
   B) delivery pages (UberEats / DoorDash / Wolt / Glovo) with nutrition info
   C) databases/aggregators (FatSecret / MyFitnessPal) — only if A/B unavailable
5) Set confidence and source_url ONLY if the found page explicitly contains numbers for this specific dish/drink (at minimum calories_kcal, preferably also macros). If no exact numbers — confidence=\"ESTIMATE\" and source_url=null, but totals must be a reasonable estimate (NOT zeros).
6) If the user does NOT mention a specific restaurant/brand — web search is not needed, use your knowledge.

How to respond:
A) If the user provided a list of options (comma-separated/bullets/"or"/numbered):
   - Rank top 3 (or fewer if fewer options).
   - For each: briefly explain "why" + a small tip on "how to make it better".
B) If the user did NOT provide options:
   - Give 3 universal recommendations "what to usually order".
   - Ask ONE short question: "Send me 3-6 menu options (as text), and I'll pick the best ones."
C) If the user sent a photo (could be a menu listing available dishes, or photos of actual dishes they're choosing from, etc.) — choose from the options visible in the photo.

Response format: return ONLY JSON matching the YumYummyResponse schema.

Field values:
- intent: \"food_advice\"
- confidence: \"ESTIMATE\"
- items: ALWAYS return exactly 3 options (if the user has fewer — supplement with your own recommendations). First item — priority (best choice), others — alternatives. For each item specify name, approximate calories_kcal, protein_g, fat_g, carbs_g. totals = sum of the best option (first item).
- totals: use as the estimate for the best option (first in the list).
- source_url:
  - If exact numbers found on a page — set the FULL URL of that specific page or PDF (not the domain or homepage).
  - If no exact numbers — source_url = null.
- message_text:
In message_text (in English): (1) 'Best choice: ...' with a brief explanation (2) 'Alternative 1: ...' (3) 'Alternative 2: ...' (4) 'Why these options:' — 2-4 sentences explaining the selection logic: how much nutrition the user has left, which macros are priority, why the best choice is better than the rest (example: \"You have 800 kcal left and need more protein (50g still needed). Greek salad with chicken is the best option: 420 kcal and 35g protein covers more than half your target, while leaving room for dinner.\") (5) 'How to improve your order: ...' — 2-3 hacks. Don't write 'Logged' — this is only a recommendation, the user will decide whether to log it.

Important:
- Never use citation format like  in message_text.
- Never use Markdown formatting (bold **, italic *, etc.) in message_text — plain text only.
- Do not write anything except JSON.
"""
nutrition_advisor = Agent(
  name="Nutrition advisor",
  instructions=nutrition_advisor_instructions,
  model="gpt-5.2",
  tools=[
    web_search_preview1
  ],
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


class PhotoMealAgentContext:
  def __init__(self, state_user_text_clean: str, state_serving_hint: str, state_gram: str):
    self.state_user_text_clean = state_user_text_clean
    self.state_serving_hint = state_serving_hint
    self.state_gram = state_gram
def photo_meal_agent_instructions(run_context: RunContextWrapper[PhotoMealAgentContext], _agent: Agent[PhotoMealAgentContext]):
  state_user_text_clean = run_context.context.state_user_text_clean
  state_serving_hint = run_context.context.state_serving_hint
  state_gram = run_context.context.state_gram
  return f"You are YumYummy Photo Meal Agent.  INPUT: - The user sent a PHOTO of food/dish. - user_text_clean (photo caption, if any): {state_user_text_clean}  - serving_hint: {state_serving_hint} - gram: {state_gram}  TASK: Analyze the photo and determine: 1) What dishes/products are visible in the photo (list each separately) 2) Estimate the serving size of each dish in grams based on visual cues (plate size, proportions, standard servings) 3) Calculate calories and macros for each dish and overall totals  RULES: - If the user specified grams in the caption {state_gram} — use them instead of visual estimation. - If the user specified serving_hint ({state_serving_hint}) — factor it into the serving estimate. - If the photo caption contains additional details about the food — take them into account. - confidence = \"ESTIMATE\" always (visual estimation cannot be precise). - source_url = null (no web source). - For each item: source_url = null. - grams in each item — your estimate of the serving size for that dish.  VISUAL ANALYSIS: - Pay attention to: plate type (standard plate ~25 cm), amount of food on plate, thickness/height of layers, comparison with known objects (fork, spoon, glass). - For drinks: estimate volume by glass/cup size. - If the photo shows multiple plates/dishes — list each as a separate item.  RESPONSE FORMAT (strict JSON matching output schema): - intent: \"photo_meal\" - message_text: \"I see in the photo: <description>.\\n\\nTotal: X kcal • P Yg • F Zg • C Wg\\nConfidence: ESTIMATE\\nNote: <serving assumptions>\" - confidence: \"ESTIMATE\" - totals: numbers (sum of all items) - items: list of dishes (1-6 items) - source_url: null"
photo_meal_agent = Agent(
  name="Photo Meal Agent",
  instructions=photo_meal_agent_instructions,
  model="gpt-5.2",
  output_type=PhotoMealAgentSchema,
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="high",
      summary="auto"
    )
  )
)


class NutritionLabelAgentContext:
  def __init__(self, state_user_text_clean: str, state_gram: str, state_serving_hint: str):
    self.state_user_text_clean = state_user_text_clean
    self.state_gram = state_gram
    self.state_serving_hint = state_serving_hint
def nutrition_label_agent_instructions(run_context: RunContextWrapper[NutritionLabelAgentContext], _agent: Agent[NutritionLabelAgentContext]):
  state_user_text_clean = run_context.context.state_user_text_clean
  state_gram = run_context.context.state_gram
  state_serving_hint = run_context.context.state_serving_hint
  return f"""You are YumYummy Nutrition Label Agent.

INPUT: - The user sent a PHOTO of a nutrition facts label / nutrition table from a product. - user_text_clean (photo caption, if any): {state_user_text_clean} - gram: {state_gram} - serving_hint: {state_serving_hint}  TASK: 1) Read all values from the nutrition facts table in the photo:    - Energy value (kcal)    - Protein (g)    - Fat (g)    - Carbohydrates (g) 2) Determine what serving size the values are for (per 100g, per serving, per package). 3) Identify the product name if visible in the photo. 4) Recalculate nutrition to the user's serving.  SERVING RECALCULATION RULES: - If values are \"per 100g\" and user specified grams ({state_gram}) — recalculate: value * (gram / 100). - If values are \"per 100g\" and grams not specified — try to determine package size from the photo. If not visible — return values per 100g and state in message_text that it's \"per 100g\". - If values are \"per serving\" — use as-is (unless user specified otherwise). - If user specified serving_hint ({state_serving_hint}) — factor it in.  RESPONSE FORMAT (strict JSON matching output schema): - intent: \"nutrition_label\" - message_text: \"<Product name (if visible)>\\n\\nPer serving (<weight>): X kcal • P Yg • F Zg • C Wg\\nConfidence: HIGH\\nSource: nutrition label photo\" - confidence: \"HIGH\" (data read from label) - totals: numbers (recalculated per serving) - items: 1 element with product data - items[0].source_url: null - source_url: null  IMPORTANT: - If the photo is blurry and values are hard to read — set confidence = \"ESTIMATE\" and try to read what you can. - If only some values are visible (e.g., only calories) — fill in what's available, estimate the rest, and note this in message_text. - Numbers should always be > 0 if something is visible on the label."""
nutrition_label_agent = Agent(
  name="Nutrition label agent",
  instructions=nutrition_label_agent_instructions,
  model="gpt-4.1",
  output_type=NutritionLabelAgentSchema,
  model_settings=ModelSettings(
    temperature=1,
    top_p=1,
    max_tokens=2048,
    store=True
  )
)


class WorkflowInput(BaseModel):
  input_as_text: str
  image_url: Optional[str] = None
  telegram_id: Optional[str] = None
  force_intent: Optional[str] = None
  nutrition_context: Optional[str] = None


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

    # Build conversation_history with optional image
    user_content = [
      {
        "type": "input_text",
        "text": workflow["input_as_text"]
      }
    ]
    if workflow.get("image_url"):
      user_content.append({
        "type": "input_image",
        "image_url": workflow["image_url"],
        "detail": "high"
      })

    conversation_history: list[TResponseInputItem] = [
      {
        "role": "user",
        "content": user_content
      }
    ]

    _trace_cfg = RunConfig(trace_metadata={
      "__trace_source__": "agent-builder",
      "workflow_id": "wf_694ae28324988190a50d6e1291ae774e0e354af8993d38d6"
    })

    force_intent = workflow.get("force_intent")
    nutrition_context = workflow.get("nutrition_context")

    _bypassable_intents = {"food_advice", "eatout", "product", "photo_meal", "barcode", "log_meal"}
    if force_intent and force_intent in _bypassable_intents:
      state["intent"] = force_intent
      state["user_text_clean"] = workflow["input_as_text"]
      state["dish_or_product"] = workflow["input_as_text"]
      state["language"] = "ru"
    else:
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

      # ---------- Populate state from router ----------
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
        context=NutritionAdvisorContext(
          state_user_text_clean=state["user_text_clean"],
          nutrition_context=nutrition_context,
        )
      )
      conversation_history.extend([item.to_input_item() for item in nutrition_advisor_result_temp.new_items])

    elif state["intent"] == "photo_meal":
      photo_meal_agent_result_temp = await Runner.run(
        photo_meal_agent,
        input=[*conversation_history],
        run_config=_trace_cfg,
        context=PhotoMealAgentContext(
          state_user_text_clean=state["user_text_clean"],
          state_serving_hint=str(state["serving_hint"] or ""),
          state_gram=str(state["gram"] or ""),
        )
      )
      conversation_history.extend([item.to_input_item() for item in photo_meal_agent_result_temp.new_items])

    elif state["intent"] == "nutrition_label":
      nutrition_label_agent_result_temp = await Runner.run(
        nutrition_label_agent,
        input=[*conversation_history],
        run_config=_trace_cfg,
        context=NutritionLabelAgentContext(
          state_user_text_clean=state["user_text_clean"],
          state_gram=str(state["gram"] or ""),
          state_serving_hint=str(state["serving_hint"] or ""),
        )
      )
      conversation_history.extend([item.to_input_item() for item in nutrition_label_agent_result_temp.new_items])

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

async def run_text(text: str, telegram_id: Optional[str] = None, image_url: Optional[str] = None,
                   force_intent: Optional[str] = None, nutrition_context: Optional[str] = None) -> dict:
  """
  Helper function that calls run_workflow with WorkflowInput.
  Called by agent_runner.py -> run_yumyummy_workflow().
  """
  workflow_input = WorkflowInput(
    input_as_text=text, telegram_id=telegram_id, image_url=image_url,
    force_intent=force_intent, nutrition_context=nutrition_context,
  )
  return await run_workflow(workflow_input)
