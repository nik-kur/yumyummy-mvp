"""
Agent runner service using OpenAI Responses API with tools.
Implements an agentic mode that can understand user intent, search for nutrition info,
and log meals using function tools.
"""
import json
import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, Optional

from anyio import to_thread
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User
from app.models.user_day import UserDay
from app.models.meal_entry import MealEntry
from app.schemas.meal import DaySummary, MealRead

logger = logging.getLogger(__name__)

# Initialize OpenAI client
_client = OpenAI(api_key=settings.openai_api_key)


def _log_meal_tool(
    db: Session,
    user_id: int,
    date_str: str,
    title: str,
    grams: Optional[float],
    calories: float,
    protein_g: float,
    fat_g: float,
    carbs_g: float,
    accuracy_level: str,
    source_url: Optional[str],
    notes: Optional[str],
) -> Dict[str, Any]:
    """
    Function tool implementation for logging a meal.
    Called by the agent when it decides to log a meal.
    """
    try:
        # Validate user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {
                "success": False,
                "error": f"User {user_id} not found"
            }
        
        # Parse date
        meal_date = date.fromisoformat(date_str) if isinstance(date_str, str) else date_str
        
        # Find or create UserDay
        user_day = (
            db.query(UserDay)
            .filter(UserDay.user_id == user.id, UserDay.date == meal_date)
            .first()
        )
        
        if not user_day:
            user_day = UserDay(
                user_id=user.id,
                date=meal_date,
                total_calories=0,
                total_protein_g=0,
                total_fat_g=0,
                total_carbs_g=0,
            )
            db.add(user_day)
            db.flush()
        
        # Normalize accuracy_level
        accuracy = accuracy_level.upper() if accuracy_level else "ESTIMATE"
        if accuracy == "HIGH":
            accuracy = "ESTIMATE"
        elif accuracy not in ("EXACT", "ESTIMATE", "APPROX"):
            accuracy = "ESTIMATE"
        
        # Create meal entry
        meal = MealEntry(
            user_id=user.id,
            user_day_id=user_day.id,
            description_user=title,
            calories=calories,
            protein_g=protein_g,
            fat_g=fat_g,
            carbs_g=carbs_g,
            uc_type="AGENT",  # Mark as agent-logged
            accuracy_level=accuracy,
        )
        
        # Update day aggregates
        user_day.total_calories += calories
        user_day.total_protein_g += protein_g
        user_day.total_fat_g += fat_g
        user_day.total_carbs_g += carbs_g
        
        db.add(meal)
        db.commit()
        db.refresh(meal)
        
        logger.info(f"[AGENT] Logged meal: user_id={user_id}, meal_id={meal.id}, calories={calories}")
        
        return {
            "success": True,
            "meal_id": meal.id,
            "message": f"Successfully logged meal: {title}"
        }
    except Exception as e:
        logger.error(f"[AGENT] Error logging meal: {e}", exc_info=True)
        db.rollback()
        return {
            "success": False,
            "error": str(e)
        }


def _get_day_tool(db: Session, user_id: int, date_str: str) -> Dict[str, Any]:
    """
    Function tool implementation for getting day summary.
    """
    try:
        meal_date = date.fromisoformat(date_str) if isinstance(date_str, str) else date_str
        
        user_day = (
            db.query(UserDay)
            .filter(UserDay.user_id == user_id, UserDay.date == meal_date)
            .first()
        )
        
        if not user_day:
            return {
                "success": True,
                "data": None,
                "message": f"No data for {date_str}"
            }
        
        meals = (
            db.query(MealEntry)
            .filter(MealEntry.user_day_id == user_day.id)
            .order_by(MealEntry.eaten_at.asc())
            .all()
        )
        
        day_summary = DaySummary(
            user_id=user_id,
            date=meal_date,
            total_calories=user_day.total_calories,
            total_protein_g=user_day.total_protein_g,
            total_fat_g=user_day.total_fat_g,
            total_carbs_g=user_day.total_carbs_g,
            meals=[MealRead.model_validate(meal) for meal in meals],
        )
        
        return {
            "success": True,
            "data": day_summary.model_dump(),
            "message": f"Day summary for {date_str}"
        }
    except Exception as e:
        logger.error(f"[AGENT] Error getting day summary: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


def _get_week_tool(db: Session, user_id: int, date_start_str: str) -> Dict[str, Any]:
    """
    Function tool implementation for getting week summary.
    Calculates aggregate stats for 7 days starting from date_start.
    """
    try:
        start_date = date.fromisoformat(date_start_str) if isinstance(date_start_str, str) else date_start_str
        
        total_calories = 0.0
        total_protein_g = 0.0
        total_fat_g = 0.0
        total_carbs_g = 0.0
        
        days_data = []
        
        for offset in range(7):
            day = start_date + timedelta(days=offset)
            user_day = (
                db.query(UserDay)
                .filter(UserDay.user_id == user_id, UserDay.date == day)
                .first()
            )
            
            if user_day:
                total_calories += user_day.total_calories
                total_protein_g += user_day.total_protein_g
                total_fat_g += user_day.total_fat_g
                total_carbs_g += user_day.total_carbs_g
                
                days_data.append({
                    "date": day.isoformat(),
                    "total_calories": user_day.total_calories,
                    "total_protein_g": user_day.total_protein_g,
                    "total_fat_g": user_day.total_fat_g,
                    "total_carbs_g": user_day.total_carbs_g,
                })
        
        return {
            "success": True,
            "data": {
                "date_start": start_date.isoformat(),
                "date_end": (start_date + timedelta(days=6)).isoformat(),
                "total_calories": total_calories,
                "total_protein_g": total_protein_g,
                "total_fat_g": total_fat_g,
                "total_carbs_g": total_carbs_g,
                "days": days_data,
            },
            "message": f"Week summary from {start_date.isoformat()}"
        }
    except Exception as e:
        logger.error(f"[AGENT] Error getting week summary: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


async def run_agent(
    db: Session,
    user_id: int,
    text: str,
    date_str: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the agent with OpenAI Responses API.
    
    Args:
        db: Database session
        user_id: User ID
        text: User input text
        date_str: Optional date string (YYYY-MM-DD), defaults to today
    
    Returns:
        Dict with structured output matching the schema:
        {
            "intent": "log_meal" | "show_today" | "show_week" | "needs_clarification" | "error",
            "reply_text": string,
            "meal": {...} | null,
            "day_summary": {...} | null,
            "week_summary": {...} | null
        }
    """
    if not text or not text.strip():
        return {
            "intent": "error",
            "reply_text": "Пожалуйста, введите запрос.",
            "meal": None,
            "day_summary": None,
            "week_summary": None,
        }
    
    # Default to today if no date provided
    if not date_str:
        date_str = date.today().isoformat()
    
    # Validate user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {
            "intent": "error",
            "reply_text": f"Пользователь {user_id} не найден.",
            "meal": None,
            "day_summary": None,
            "week_summary": None,
        }
    
    # Define function tools (Responses API format: flattened structure)
    function_tools = [
        {
            "type": "function",
            "name": "log_meal",
            "description": "Log a meal entry for the user. Use this when the user wants to record what they ate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "User ID"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                    "title": {"type": "string", "description": "Meal description/title"},
                    "grams": {"type": ["number", "null"], "description": "Portion size in grams (optional)"},
                    "calories": {"type": "number", "description": "Calories"},
                    "protein_g": {"type": "number", "description": "Protein in grams"},
                    "fat_g": {"type": "number", "description": "Fat in grams"},
                    "carbs_g": {"type": "number", "description": "Carbs in grams"},
                    "accuracy_level": {"type": "string", "description": "HIGH if from official source, ESTIMATE otherwise", "enum": ["HIGH", "ESTIMATE"]},
                    "source_url": {"type": ["string", "null"], "description": "URL of the source page if available"},
                    "notes": {"type": ["string", "null"], "description": "Additional notes"},
                },
                "required": ["user_id", "date_str", "title", "calories", "protein_g", "fat_g", "carbs_g", "accuracy_level"],
            },
        },
        {
            "type": "function",
            "name": "get_day",
            "description": "Get day summary (total calories and macros, list of meals) for a specific date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "User ID"},
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                },
                "required": ["user_id", "date"],
            },
        },
        {
            "type": "function",
            "name": "get_week",
            "description": "Get week summary (aggregate stats for 7 days starting from date_start).",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "integer", "description": "User ID"},
                    "date_start": {"type": "string", "description": "Start date in YYYY-MM-DD format"},
                },
                "required": ["user_id", "date_start"],
            },
        },
    ]
    
    # System prompt
    system_prompt = (
        "You are a helpful nutrition assistant for the YumYummy app. "
        "Your task is to understand user intent and help them log meals or view summaries.\n\n"
        "CAPABILITIES:\n"
        "1. Understand user intent:\n"
        "   - log_meal: User wants to record what they ate (e.g., 'I ate a burger', 'сырники из кофемании')\n"
        "   - show_today: User wants to see today's summary (e.g., 'show today', 'что я съел сегодня')\n"
        "   - show_week: User wants to see week summary (e.g., 'week summary', 'сводка за неделю')\n"
        "   - needs_clarification: User's intent is unclear\n"
        "   - error: Something went wrong\n\n"
        "2. For restaurant/menu items and packaged products:\n"
        "   - Use web_search tool to find nutrition information\n"
        "   - Source priority (from highest to lowest):\n"
        "     1. Official restaurant websites (e.g., coffeemania.ru, joeandthejuice.is) - HIGHEST priority\n"
        "     2. Official menu pages with nutrition facts\n"
        "     3. Reputable delivery platforms (UberEats, Yandex.Eda, Wolt, Glovo)\n"
        "     4. User-generated nutrition databases (FatSecret, MyFitnessPal, health-diet.ru, calorizator) - acceptable but lower priority\n"
        "     5. LLM estimation based on similar foods - LOWEST priority (only if no sources found)\n"
        "   - ALWAYS search for portion size/weight (grams) on pages - it's usually listed alongside nutrition\n"
        "   - Return HIGH accuracy_level if you found reliable evidence from official/delivery source with source_url\n"
        "   - Return ESTIMATE with source_url if using user-generated databases (they're acceptable but less reliable)\n"
        "   - Return ESTIMATE with no source_url only if no sources found and using LLM estimation\n\n"
        "3. When ready to log a meal:\n"
        "   - Call log_meal tool with all required fields\n"
        "   - Use the date provided in context (default: today)\n"
        "   - IMPORTANT: If you found nutrition data, you MUST also return it in the 'meal' field of the final JSON\n\n"
        "4. Always produce a FINAL JSON result matching this schema. Return ONLY valid JSON, no additional text:\n"
        "{\n"
        '  "intent": "log_meal" | "show_today" | "show_week" | "needs_clarification" | "error",\n'
        '  "reply_text": string (user-friendly response in Russian),\n'
        '  "meal": {\n'
        '    "title": string (full dish name, e.g., "Сырники Кофемания"),\n'
        '    "grams": number|null (portion size in grams if found, otherwise null),\n'
        '    "calories": number (total calories for the portion),\n'
        '    "protein_g": number (protein in grams),\n'
        '    "fat_g": number (fat in grams),\n'
        '    "carbs_g": number (carbs in grams),\n'
        '    "accuracy_level": "HIGH"|"ESTIMATE" (HIGH only for official sources),\n'
        '    "source_url": string|null (URL of official source page, null if not official),\n'
        '    "notes": string|null (brief explanation)\n'
        '  } | null (MUST be object with all fields if intent is "log_meal"),\n'
        '  "day_summary": object|null,\n'
        '  "week_summary": object|null\n'
        "}\n\n"
        "CRITICAL RULES:\n"
        "- You MUST return valid JSON only. Start your response with { and end with }.\n"
        "- If intent is 'log_meal', the 'meal' field MUST be an object (not null) with all required fields\n"
        "- If you found nutrition data from web_search, you MUST include it in the 'meal' field\n"
        "- If you found portion size (grams) on the official page, include it in meal.grams\n"
        "- If portion size is not found, set meal.grams to null but still provide calories/macros for the standard portion\n\n"
        "IMPORTANT:\n"
        "- Always respond in Russian for reply_text\n"
        "- If user asks to delete/edit meals, return intent='needs_clarification' with reply_text explaining it's not implemented yet\n"
        "- If web_search finds nutrition info from official source, use it and set accuracy_level='HIGH'\n"
        "- If only unofficial sources found, return ESTIMATE with source_url=null\n"
        "- Never call log_meal without user explicitly wanting to log something\n"
        "- For 'сырники кофемания' or similar restaurant queries:\n"
        "  1. Search for 'coffeemania.ru сырники nutrition' or 'site:coffeemania.ru сырники'\n"
        "  2. Extract portion size (grams) and nutrition from official page\n"
        "  3. Return JSON with intent='log_meal' and complete 'meal' object with all fields\n"
    )
    
    user_prompt = (
        f"User ID: {user_id}\n"
        f"Date: {date_str}\n"
        f"User input: {text}\n\n"
        "Understand the user's intent and help them accordingly. "
        "If they want to log a meal, search for nutrition info if needed, then call log_meal. "
        "If they want to see summaries, call get_day or get_week. "
        "Always return the final JSON result."
    )
    
    # Tool handler mapping
    tool_handlers = {
        "log_meal": lambda **kwargs: _log_meal_tool(db, **kwargs),
        "get_day": lambda **kwargs: _get_day_tool(db, **kwargs),
        "get_week": lambda **kwargs: _get_week_tool(db, **kwargs),
    }
    
    try:
        def _call_responses_api():
            if not hasattr(_client, 'responses') or not hasattr(_client.responses, 'create'):
                raise AttributeError("Responses API not available")
            
            # Try with function tools first
            try:
                logger.info(f"[AGENT] Attempting Responses API call with {len(function_tools)} function tools")
                return _client.responses.create(
                    model="gpt-4o",
                    tools=[{"type": "web_search"}] + function_tools,
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    include=["web_search_call.action.sources"],
                )
            except Exception as e:
                logger.warning(f"[AGENT] Responses API call with function tools failed: {e}, trying without function tools")
                # Fallback: try without function tools, just web_search
                return _client.responses.create(
                    model="gpt-4o",
                    tools=[{"type": "web_search"}],
                    input=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    include=["web_search_call.action.sources"],
                )
        
        response = await to_thread.run_sync(_call_responses_api)
        logger.info(f"[AGENT] Responses API call completed, response type: {type(response)}")
        
        # Log web_search usage
        has_web_search = False
        web_sources = []
        if hasattr(response, 'output') and response.output:
            output_items = response.output if isinstance(response.output, list) else [response.output]
            for item in output_items:
                item_type = getattr(item, 'type', None)
                if item_type == "web_search_call":
                    has_web_search = True
                    # Try to extract sources if available
                    if hasattr(item, 'action') and hasattr(item.action, 'sources'):
                        web_sources = item.action.sources
                    logger.info(f"[AGENT] web_search_call detected, sources_count={len(web_sources) if web_sources else 0}")
                    break
        
        logger.info(f"[AGENT] Has web_search_call: {has_web_search}")
        
        # Process tool calls and function results
        output_items = []
        if hasattr(response, 'output') and response.output:
            output_items = response.output if isinstance(response.output, list) else [response.output]
        
        # Handle function tool calls if present
        # Note: Responses API may handle function calls differently
        # We'll check for function_call items and execute them
        function_results = []
        for item in output_items:
            item_type = getattr(item, 'type', None)
            if item_type == "function_call":
                function_name = getattr(item, 'name', None)
                function_args = getattr(item, 'arguments', {})
                
                if isinstance(function_args, str):
                    try:
                        function_args = json.loads(function_args)
                    except json.JSONDecodeError:
                        logger.warning(f"[AGENT] Failed to parse function arguments: {function_args}")
                        continue
                
                if function_name in tool_handlers:
                    logger.info(f"[AGENT] Calling tool: {function_name} with args: {function_args}")
                    # Fix parameter name mismatch: schema uses 'date' but function expects 'date_str'
                    if function_name == "log_meal" and "date" in function_args:
                        function_args["date_str"] = function_args.pop("date")
                    result = tool_handlers[function_name](**function_args)
                    logger.info(f"[AGENT] Tool result: {result}")
                    function_results.append({
                        "name": function_name,
                        "result": result
                    })
                else:
                    logger.warning(f"[AGENT] Unknown tool: {function_name}")
        
        # Extract final JSON from response
        final_json = None
        output_content = None
        
        # Log all output items for debugging
        logger.info(f"[AGENT] Processing {len(output_items)} output items")
        for idx, item in enumerate(output_items):
            item_type = getattr(item, 'type', None)
            logger.info(f"[AGENT] Output item {idx}: type={item_type}, has_content={hasattr(item, 'content')}")
            
            if item_type == "message" or hasattr(item, 'content'):
                content = getattr(item, 'content', None)
                if content:
                    if isinstance(content, list):
                        for block_idx, block in enumerate(content):
                            if hasattr(block, 'text'):
                                block_text = block.text
                                logger.info(f"[AGENT] Block {block_idx} text length: {len(block_text) if block_text else 0}")
                                if not output_content:
                                    output_content = block_text
                            elif isinstance(block, str):
                                logger.info(f"[AGENT] Block {block_idx} is string, length: {len(block)}")
                                if not output_content:
                                    output_content = block
                    elif isinstance(content, str):
                        logger.info(f"[AGENT] Content is string, length: {len(content)}")
                        output_content = content
        
        if not output_content:
            if hasattr(response, 'content'):
                output_content = response.content
                logger.info(f"[AGENT] Using response.content, length: {len(str(output_content))}")
            elif hasattr(response, 'text'):
                output_content = response.text
                logger.info(f"[AGENT] Using response.text, length: {len(str(output_content))}")
        
        logger.info(f"[AGENT] Final output_content length: {len(str(output_content)) if output_content else 0}")
        if output_content:
            logger.info(f"[AGENT] First 500 chars of output_content: {str(output_content)[:500]}")
        
        if output_content:
            # Try to extract JSON from output
            json_match = re.search(r'\{.*\}', str(output_content), re.DOTALL)
            if json_match:
                try:
                    final_json = json.loads(json_match.group(0))
                    logger.info(f"[AGENT] Successfully parsed JSON, intent: {final_json.get('intent')}")
                except json.JSONDecodeError as e:
                    logger.warning(f"[AGENT] Failed to parse JSON: {e}, raw: {str(output_content)[:500]}")
            else:
                logger.warning(f"[AGENT] No JSON pattern found in output_content")
        else:
            logger.warning(f"[AGENT] No output_content extracted from response")
        
        # If no JSON found, try to infer intent from tool calls
        if not final_json:
            logger.warning(f"[AGENT] No JSON found, checking for function calls")
            # Check if log_meal was called
            meal_logged = False
            day_requested = False
            week_requested = False
            
            for item in output_items:
                item_type = getattr(item, 'type', None)
                function_name = getattr(item, 'name', None)
                logger.info(f"[AGENT] Checking item: type={item_type}, name={function_name}")
                
                if item_type == "function_call":
                    if function_name == "log_meal":
                        meal_logged = True
                        logger.info(f"[AGENT] log_meal function call detected")
                    elif function_name == "get_day":
                        day_requested = True
                        logger.info(f"[AGENT] get_day function call detected")
                    elif function_name == "get_week":
                        week_requested = True
                        logger.info(f"[AGENT] get_week function call detected")
            
            if meal_logged:
                final_json = {
                    "intent": "log_meal",
                    "reply_text": "Приём пищи успешно записан!",
                    "meal": None,
                    "day_summary": None,
                    "week_summary": None,
                }
            elif day_requested:
                final_json = {
                    "intent": "show_today",
                    "reply_text": "Сводка за день получена.",
                    "meal": None,
                    "day_summary": None,
                    "week_summary": None,
                }
            elif week_requested:
                final_json = {
                    "intent": "show_week",
                    "reply_text": "Сводка за неделю получена.",
                    "meal": None,
                    "day_summary": None,
                    "week_summary": None,
                }
            else:
                # If we have output_content but no JSON, try to extract intent from text
                if output_content:
                    output_lower = str(output_content).lower()
                    if any(word in output_lower for word in ["сырник", "кофеман", "блюдо", "еда", "съел", "съела"]):
                        logger.info(f"[AGENT] Detected meal-related keywords, but no JSON. Returning needs_clarification with more context.")
                        final_json = {
                            "intent": "needs_clarification",
                            "reply_text": f"Получен ответ от модели, но не удалось извлечь структурированные данные. Попробуйте переформулировать запрос.\n\nОтвет модели (первые 300 символов): {str(output_content)[:300]}",
                            "meal": None,
                            "day_summary": None,
                            "week_summary": None,
                        }
                    else:
                        final_json = {
                            "intent": "needs_clarification",
                            "reply_text": "Не удалось понять ваш запрос. Попробуйте переформулировать.",
                            "meal": None,
                            "day_summary": None,
                            "week_summary": None,
                        }
                else:
                    final_json = {
                        "intent": "needs_clarification",
                        "reply_text": "Не удалось получить ответ от модели. Попробуйте позже.",
                        "meal": None,
                        "day_summary": None,
                        "week_summary": None,
                    }
        
        # Ensure all required fields are present
        if "intent" not in final_json:
            final_json["intent"] = "error"
        if "reply_text" not in final_json:
            final_json["reply_text"] = "Произошла ошибка при обработке запроса."
        if "meal" not in final_json:
            final_json["meal"] = None
        if "day_summary" not in final_json:
            final_json["day_summary"] = None
        if "week_summary" not in final_json:
            final_json["week_summary"] = None
        
        # Validate meal structure if intent is log_meal
        if final_json.get("intent") == "log_meal" and final_json.get("meal") is None:
            logger.warning(f"[AGENT] Intent is log_meal but meal is None, trying to extract from reply_text")
            # Try to infer meal data from reply_text or function calls
            # This is a fallback - ideally the model should return proper JSON
            final_json["meal"] = {
                "title": text,  # Use original user input as fallback
                "grams": None,
                "calories": 0,
                "protein_g": 0,
                "fat_g": 0,
                "carbs_g": 0,
                "accuracy_level": "ESTIMATE",
                "source_url": None,
                "notes": "Не удалось извлечь данные о блюде из ответа модели",
            }
        
        # Validate meal object structure
        if final_json.get("meal") and isinstance(final_json["meal"], dict):
            # Ensure all required fields are present
            required_meal_fields = ["title", "grams", "calories", "protein_g", "fat_g", "carbs_g", "accuracy_level", "source_url", "notes"]
            for field in required_meal_fields:
                if field not in final_json["meal"]:
                    if field in ["grams", "source_url", "notes"]:
                        final_json["meal"][field] = None
                    elif field == "accuracy_level":
                        final_json["meal"][field] = "ESTIMATE"
                    else:
                        final_json["meal"][field] = 0
        
        logger.info(f"[AGENT] Final JSON intent: {final_json.get('intent')}, meal present: {final_json.get('meal') is not None}")
        if final_json.get("meal"):
            logger.info(f"[AGENT] Meal data: title={final_json['meal'].get('title')}, calories={final_json['meal'].get('calories')}, grams={final_json['meal'].get('grams')}")
        
        return final_json
        
    except AttributeError as e:
        logger.error(f"[AGENT] Responses API not available: {e}")
        return {
            "intent": "error",
            "reply_text": "Сервис временно недоступен. Попробуйте позже.",
            "meal": None,
            "day_summary": None,
            "week_summary": None,
        }
    except Exception as e:
        logger.error(f"[AGENT] Unexpected error: {e}", exc_info=True)
        return {
            "intent": "error",
            "reply_text": f"Произошла ошибка: {str(e)}",
            "meal": None,
            "day_summary": None,
            "week_summary": None,
        }

