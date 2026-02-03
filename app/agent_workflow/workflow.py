import os
from agents import WebSearchTool, Agent, ModelSettings, TResponseInputItem, Runner, RunConfig, trace
from agents import set_default_openai_client
from pydantic import BaseModel
from openai import AsyncOpenAI
from openai.types.shared.reasoning import Reasoning
from typing import Optional, List

# 1) Disable tracing to avoid SSL handshake timeouts in local dev
os.environ.setdefault("OPENAI_AGENTS_DISABLE_TRACING", "1")

# 2) Use a longer OpenAI timeout because WebSearch can be slow
_openai_timeout = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "180"))
_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=_openai_timeout,
)
set_default_openai_client(_client)

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
  dish_or_product: Optional[str]
  grams: Optional[float]
  date_hint: Optional[str]
  language: str
  serving_hint: Optional[str]


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


class MealParserSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: MealParserSchema__Totals
  items: List[MealParserSchema__ItemsItem]
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
  items: List[HelpAgentSchema__ItemsItem]
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


class FinalAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: FinalAgentSchema__Totals
  items: List[FinalAgentSchema__ItemsItem]
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


class EatoutAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: EatoutAgentSchema__Totals
  items: List[EatoutAgentSchema__ItemsItem]
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


class ProductAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: ProductAgentSchema__Totals
  items: List[ProductAgentSchema__ItemsItem]
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


class BarcodeAgentSchema(BaseModel):
  intent: str
  message_text: str
  confidence: Optional[str]
  totals: BarcodeAgentSchema__Totals
  items: List[BarcodeAgentSchema__ItemsItem]
  source_url: Optional[str]


router = Agent(
  name="Router",
  instructions="""You are YumYummy Router. Your job: classify the user message into an intent and extract routing fields.
Do NOT calculate nutrition here. Do NOT search the web here.

Return STRICT JSON matching the provided schema.

Intents:
- log_meal: user describes food eaten (any free text) and wants calories/macros logged or estimated.
- day_summary: user asks for today/day summary.
- week_summary: user asks for weekly summary.
- product: user asks nutrition for a packaged product by name.
- barcode: user provides barcode or asks to scan/lookup barcode.
- eatout: user asks about a restaurant/cafe dish (menu item) or “from Starbucks/Joe & The Juice/etc”.
- help: user asks what the bot can do / commands / how to use.
- unknown: everything else.

Rules:
- If message mentions a restaurant/cafe/brand menu item (e.g., Starbucks, Joe & The Juice, Coffeemania), choose eatout (even if grams are mentioned).
- If message contains a long number that looks like barcode (8-14 digits), choose barcode.
- If message contains words “сегодня / today / за день” -> day_summary.
- If message contains “неделя / week” -> week_summary.
- If user asks “кбжу” for a product brand name without restaurant context -> product.

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
  model="gpt-5.2-pro",
  output_type=RouterSchema,
  model_settings=ModelSettings(
    store=True
  )
)


meal_parser = Agent(
  name="Meal Parser",
  instructions="""You are YumYummy Meal Parser.

You will receive:
- the user's cleaned text from the Router node
- the Router intent (should be \"log_meal\" in this branch)

Task:
1) Estimate calories and macros for the described meal.
2) Build a FINAL JSON response matching the output schema EXACTLY.

Rules:
- Since web search is not used here, source_url must be null.
- Use confidence=\"HIGH\" only if user provided clear portion sizes/grams and meal is unambiguous; otherwise \"ESTIMATE\".
- totals must be numeric (never null).
- items must be a short list (1-6 items) and totals must be the sum.

The final response must include:
- intent: set to the Router intent (\"log_meal\")
- message_text: Russian friendly summary:
  \"Итого: X ккал • Б Yг • Ж Zг • У Wг\nОценка: CONF\nКоротко: <assumptions>\"
- confidence, totals, items, source_url.
""",
  model="gpt-4.1",
  output_type=MealParserSchema,
  model_settings=ModelSettings(
    temperature=0.3,
    top_p=1,
    max_tokens=2048,
    store=True
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
  model="gpt-4.1",
  output_type=HelpAgentSchema,
  model_settings=ModelSettings(
    temperature=1,
    top_p=1,
    max_tokens=2048,
    store=True
  )
)


final_agent = Agent(
  name="Final agent",
  instructions="""You receive a JSON object from upstream (either Meal Parser or Help Agent).
Return ONLY the same object, unchanged, matching the provided schema exactly.
Do not add or remove fields.
""",
  model="gpt-4.1",
  output_type=FinalAgentSchema,
  model_settings=ModelSettings(
    temperature=1,
    top_p=1,
    max_tokens=2048,
    store=True
  )
)


eatout_agent = Agent(
  name="Eatout agent",
  instructions="""Ты YumYummy Eatout Agent.

Вход: текст пользователя (Router.user_text_clean) и название блюда/напитка (Router.dish_or_product).

Задача: найти КБЖУ (ккал и БЖУ) именно для указанного блюда/напитка через WEB SEARCH.

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
1) Всегда используй web search.
2) confidence=\"HIGH\" и source_url (ссылка) ставь ТОЛЬКО если на найденной странице явно есть цифры для этого блюда/напитка:
   - минимум calories_kcal, лучше также БЖУ.
3) Если точных цифр нет — верни confidence=\"ESTIMATE\" и source_url=null, но totals должны быть разумной оценкой (НЕ нули).
4) Official-first:
   - сначала пытайся найти официальный сайт бренда/ресторана и страницу меню или блюда,
   - затем delivery сервисы (например Wolt/Glovo/UberEats),
   - затем агрегаторы/обзоры (например, fatsecret).
4) Сделай 3–5 поисковых запросов (разные формулировки RU/EN), чтобы попытаться найти приоритетный источник (официальный сайт или службы доставки -  как описано в пункте 3)) 
5) Не выдумывай точные цифры. Если не нашёл — честный ESTIMATE.

ФОРМАТ ОТВЕТА:
Верни только JSON по схеме:
- intent: \"eatout\"
- message_text: коротко по-русски (Итого: ...; Оценка: HIGH/ESTIMATE; если есть ссылка — скажи \"Источник: <домен>\")
- confidence
- totals
- items (1–3 строки, например \"Pumpkin Spice Latte, grande\")
- source_url (строка или null)
""",
  model="gpt-5.2-pro",
  tools=[
    web_search_preview
  ],
  output_type=EatoutAgentSchema,
  model_settings=ModelSettings(
    store=True
  )
)


product_agent = Agent(
  name="Product agent",
  instructions="""Ты YumYummy Product Agent.

Вход: Router.user_text_clean, Router.dish_or_product, Router.grams (может быть null), Router.serving_hint (может быть null).
Всегда используй web search.

Цель: вернуть КБЖУ продукта НА ПОРЦИЮ, которую пользователь реально съел/выпил.

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
- Если ты не можешь уверенно указать реальную ссылку, поставь confidence=\"ESTIMATE\" и source_url=null.""",
  model="gpt-5.2-pro",
  tools=[
    web_search_preview
  ],
  output_type=ProductAgentSchema,
  model_settings=ModelSettings(
    store=True
  )
)


barcode_agent = Agent(
  name="Barcode agent",
  instructions="""Ты YumYummy Barcode Agent.

Вход: штрихкод (8–14 цифр).
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
""",
  model="gpt-5-nano",
  tools=[
    web_search_preview
  ],
  output_type=BarcodeAgentSchema,
  model_settings=ModelSettings(
    store=True,
    reasoning=Reasoning(
      effort="medium"
    )
  )
)


class WorkflowInput(BaseModel):
  input_as_text: str
  telegram_id: Optional[str] = None


# Main code entrypoint
async def run_workflow(workflow_input: WorkflowInput):
  with trace("YumYummy"):
    state = {

    }
    workflow = workflow_input.model_dump()
    telegram_id = workflow.get("telegram_id")
    
    # Helper function to build trace_metadata with telegram_id
    def get_trace_metadata() -> dict:
        metadata = {
            "__trace_source__": "agent-builder",
            "workflow_id": "wf_694ae28324988190a50d6e1291ae774e0e354af8993d38d6"
        }
        if telegram_id:
            metadata["telegram_id"] = telegram_id
        return metadata
    
    conversation_history: List[TResponseInputItem] = [
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
    router_result_temp = await Runner.run(
      router,
      input=[
        *conversation_history
      ],
      run_config=RunConfig(trace_metadata=get_trace_metadata())
    )

    conversation_history.extend([item.to_input_item() for item in router_result_temp.new_items])

    if router_result_temp.final_output is None:
      raise ValueError("Router agent did not produce final_output")
    
    router_result = {
      "output_text": router_result_temp.final_output.json(),
      "output_parsed": router_result_temp.final_output.model_dump()
    }
    if router_result["output_parsed"]["intent"] == 'log_meal':
      meal_parser_result_temp = await Runner.run(
        meal_parser,
        input=[
          *conversation_history
        ],
      run_config=RunConfig(trace_metadata=get_trace_metadata())
      )

      conversation_history.extend([item.to_input_item() for item in meal_parser_result_temp.new_items])

      meal_parser_result = {
        "output_text": meal_parser_result_temp.final_output.json(),
        "output_parsed": meal_parser_result_temp.final_output.model_dump()
      }
      final_agent_result_temp = await Runner.run(
        final_agent,
        input=[
          *conversation_history
        ],
      run_config=RunConfig(trace_metadata=get_trace_metadata())
      )

      conversation_history.extend([item.to_input_item() for item in final_agent_result_temp.new_items])

      if final_agent_result_temp.final_output is None:
        raise ValueError("Final agent did not produce final_output in log_meal branch")
      
      final_agent_result = {
        "output_text": final_agent_result_temp.final_output.json(),
        "output_parsed": final_agent_result_temp.final_output.model_dump()
      }
      return final_agent_result["output_parsed"]
    elif router_result["output_parsed"]["intent"] == 'eatout':
      eatout_agent_result_temp = await Runner.run(
        eatout_agent,
        input=[
          *conversation_history
        ],
      run_config=RunConfig(trace_metadata=get_trace_metadata())
      )

      conversation_history.extend([item.to_input_item() for item in eatout_agent_result_temp.new_items])

      eatout_agent_result = {
        "output_text": eatout_agent_result_temp.final_output.json(),
        "output_parsed": eatout_agent_result_temp.final_output.model_dump()
      }
      final_agent_result_temp = await Runner.run(
        final_agent,
        input=[
          *conversation_history
        ],
      run_config=RunConfig(trace_metadata=get_trace_metadata())
      )

      conversation_history.extend([item.to_input_item() for item in final_agent_result_temp.new_items])

      if final_agent_result_temp.final_output is None:
        raise ValueError("Final agent did not produce final_output in eatout branch")
      
      final_agent_result = {
        "output_text": final_agent_result_temp.final_output.json(),
        "output_parsed": final_agent_result_temp.final_output.model_dump()
      }
      return final_agent_result["output_parsed"]
    elif router_result["output_parsed"]["intent"] == 'product':
      product_agent_result_temp = await Runner.run(
        product_agent,
        input=[
          *conversation_history
        ],
      run_config=RunConfig(trace_metadata=get_trace_metadata())
      )

      conversation_history.extend([item.to_input_item() for item in product_agent_result_temp.new_items])

      product_agent_result = {
        "output_text": product_agent_result_temp.final_output.json(),
        "output_parsed": product_agent_result_temp.final_output.model_dump()
      }
      final_agent_result_temp = await Runner.run(
        final_agent,
        input=[
          *conversation_history
        ],
      run_config=RunConfig(trace_metadata=get_trace_metadata())
      )

      conversation_history.extend([item.to_input_item() for item in final_agent_result_temp.new_items])

      if final_agent_result_temp.final_output is None:
        raise ValueError("Final agent did not produce final_output in product branch")
      
      final_agent_result = {
        "output_text": final_agent_result_temp.final_output.json(),
        "output_parsed": final_agent_result_temp.final_output.model_dump()
      }
      return final_agent_result["output_parsed"]
    elif router_result["output_parsed"]["intent"] == 'barcode':
      barcode_agent_result_temp = await Runner.run(
        barcode_agent,
        input=[
          *conversation_history
        ],
      run_config=RunConfig(trace_metadata=get_trace_metadata())
      )

      conversation_history.extend([item.to_input_item() for item in barcode_agent_result_temp.new_items])

      barcode_agent_result = {
        "output_text": barcode_agent_result_temp.final_output.json(),
        "output_parsed": barcode_agent_result_temp.final_output.model_dump()
      }
      final_agent_result_temp = await Runner.run(
        final_agent,
        input=[
          *conversation_history
        ],
      run_config=RunConfig(trace_metadata=get_trace_metadata())
      )

      conversation_history.extend([item.to_input_item() for item in final_agent_result_temp.new_items])

      if final_agent_result_temp.final_output is None:
        raise ValueError("Final agent did not produce final_output in barcode branch")
      
      final_agent_result = {
        "output_text": final_agent_result_temp.final_output.json(),
        "output_parsed": final_agent_result_temp.final_output.model_dump()
      }
      return final_agent_result["output_parsed"]
    else:
      help_agent_result_temp = await Runner.run(
        help_agent,
        input=[
          *conversation_history
        ],
      run_config=RunConfig(trace_metadata=get_trace_metadata())
      )

      conversation_history.extend([item.to_input_item() for item in help_agent_result_temp.new_items])

      help_agent_result = {
        "output_text": help_agent_result_temp.final_output.json(),
        "output_parsed": help_agent_result_temp.final_output.model_dump()
      }
      final_agent_result_temp = await Runner.run(
        final_agent,
        input=[
          *conversation_history
        ],
      run_config=RunConfig(trace_metadata=get_trace_metadata())
      )

      conversation_history.extend([item.to_input_item() for item in final_agent_result_temp.new_items])

      if final_agent_result_temp.final_output is None:
        raise ValueError("Final agent did not produce final_output in help branch")
      
      final_agent_result = {
        "output_text": final_agent_result_temp.final_output.json(),
        "output_parsed": final_agent_result_temp.final_output.model_dump()
      }
      return final_agent_result["output_parsed"]


# Module-level helper function
async def run_text(text: str, telegram_id: Optional[str] = None) -> dict:
  """
  Helper function that calls run_workflow with WorkflowInput.
  
  Args:
    text: User input text
    telegram_id: Optional Telegram user ID (for agent tools context)
    
  Returns:
    Dict with the workflow result
  """
  workflow_input = WorkflowInput(input_as_text=text, telegram_id=telegram_id)
  return await run_workflow(workflow_input)
