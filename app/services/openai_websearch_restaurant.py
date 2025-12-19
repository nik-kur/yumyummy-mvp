"""
Experimental helper module for restaurant nutrition using OpenAI Responses API with web_search tool.
This is Path A for A/B testing - parallel to the existing Tavily-based approach.
"""
import json
import logging
import re
from typing import Any, Dict, Optional

from anyio import to_thread
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
_client = OpenAI(api_key=settings.openai_api_key)


async def estimate_restaurant_meal_with_openai_websearch(
    text: str,
    locale: str = "ru-RU"
) -> Optional[Dict[str, Any]]:
    """
    Оценивает КБЖУ блюда из ресторана через OpenAI Responses API с web_search tool.
    
    Args:
        text: свободный текст с описанием блюда из ресторана
        locale: локаль (по умолчанию "ru-RU")
    
    Returns:
        dict с полями:
        - description: str
        - calories: float
        - protein_g: float
        - fat_g: float
        - carbs_g: float
        - accuracy_level: "HIGH"|"ESTIMATE"
        - notes: str
        - source_url: Optional[str]
        или None, если не удалось найти
    """
    if not text or not text.strip():
        logger.warning("estimate_restaurant_meal_with_openai_websearch: empty text")
        return None
    
    text = text.strip()
    
    # System prompt with prioritization rules
    system_prompt = (
        "You are a nutrition researcher. Your task is to find accurate nutritional information "
        "for restaurant dishes using web search.\n\n"
        "SOURCE PRIORITIZATION (in order):\n"
        "1. Official restaurant website pages and official menu pages (e.g., restaurant.com/menu, restaurant.ru/menu)\n"
        "2. Reputable delivery/menu platforms: UberEats, Deliveroo, Wolt, Glovo, Yandex.Eda, etc.\n"
        "3. AVOID user-generated calorie databases: FatSecret, MyFitnessPal, EatThisMuch, health-diet, Calorizator, "
        "and similar fitness/calorie tracking sites.\n\n"
        "INSTRUCTIONS:\n"
        "1. Use the web_search tool to find information about the restaurant and dish.\n"
        "2. First, search for the restaurant official domain or official menu page for this dish.\n"
        "3. Extract calories, protein (g), fat (g), and carbs (g) from the source.\n"
        "4. Return STRICT JSON only, no additional text.\n\n"
        "JSON format:\n"
        "{\n"
        '  "description": "full dish name with restaurant",\n'
        '  "calories": number,\n'
        '  "protein_g": number,\n'
        '  "fat_g": number,\n'
        '  "carbs_g": number,\n'
        '  "accuracy_level": "HIGH" or "ESTIMATE",\n'
        '  "notes": "brief explanation",\n'
        '  "source_url": "URL of the source page or null"\n'
        "}\n\n"
        "RULES:\n"
        "- Return HIGH only when you can cite an official/delivery/menu source URL with evidence of nutrition data.\n"
        "- Return ESTIMATE if you cannot find an official/delivery/menu page with nutrition.\n"
        "- If you only find user-generated databases, do NOT cite them as source_url (set source_url to null).\n"
        "- If no reliable source is found, set source_url to null and accuracy_level to ESTIMATE.\n"
        "- Always use web_search tool to find information."
    )
    
    user_prompt = (
        f"Query: {text}\n\n"
        "TWO-STAGE SEARCH:\n"
        "1. First, find the restaurant official domain or official menu page for this dish.\n"
        "2. Second, extract nutrition from that page.\n\n"
        "If you only find user-generated databases, do not cite them as source_url.\n\n"
        "Find the nutritional information (calories, protein, fat, carbs) for this restaurant dish. "
        "Return STRICT JSON with the format specified above."
    )
    
    try:
        # Call Responses API with web_search tool
        def _call_responses_api():
            if not hasattr(_client, 'responses') or not hasattr(_client.responses, 'create'):
                raise AttributeError("Responses API not available")
            
            return _client.responses.create(
                model="gpt-4o",
                tools=[{"type": "web_search"}],
                # НЕ форсируем tool_choice - оставляем auto
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )
        
        try:
            response = await to_thread.run_sync(_call_responses_api)
            
            # Логирование структуры ответа
            output_items = []
            has_web_search_call = False
            source_url = None
            output_content = None
            
            # Проверяем response.output
            if hasattr(response, 'output') and response.output:
                # Логируем типы output items
                if isinstance(response.output, list):
                    output_types = [getattr(item, 'type', type(item).__name__) for item in response.output]
                    logger.info(f"[OPENAI] Response output types: {output_types}")
                    output_items = response.output
                else:
                    logger.info(f"[OPENAI] Response output is not a list: {type(response.output)}")
                    output_items = [response.output] if response.output else []
                
                # Проверяем наличие web_search_call
                for item in output_items:
                    item_type = getattr(item, 'type', None)
                    if item_type == "web_search_call":
                        has_web_search_call = True
                        logger.info(f"[OPENAI] Found web_search_call in output")
                        break
                
                logger.info(f"[OPENAI] Has web_search_call: {has_web_search_call}")
                
                # Извлекаем content из message items и ищем annotations
                for item in output_items:
                    item_type = getattr(item, 'type', None)
                    
                    # Если это message item, извлекаем content
                    if item_type == "message" or hasattr(item, 'content'):
                        content = getattr(item, 'content', None)
                        if content:
                            if isinstance(content, list):
                                # Content может быть списком блоков
                                for block in content:
                                    if hasattr(block, 'text'):
                                        if not output_content:
                                            output_content = block.text
                                    elif isinstance(block, str):
                                        if not output_content:
                                            output_content = block
                                    elif isinstance(block, dict) and 'text' in block:
                                        if not output_content:
                                            output_content = block['text']
                            elif isinstance(content, str):
                                output_content = content
                        
                        # Ищем annotations в message item
                        if hasattr(item, 'annotations'):
                            annotations = item.annotations
                            logger.info(f"[OPENAI] Found annotations: {type(annotations)}")
                            
                            if annotations:
                                if isinstance(annotations, list):
                                    for ann in annotations:
                                        ann_type = getattr(ann, 'type', None)
                                        logger.info(f"[OPENAI] Annotation type: {ann_type}")
                                        
                                        if ann_type == "url_citation" or hasattr(ann, 'url_citation'):
                                            url_citation = getattr(ann, 'url_citation', None)
                                            if url_citation:
                                                if hasattr(url_citation, 'url'):
                                                    source_url = url_citation.url
                                                elif isinstance(url_citation, dict) and 'url' in url_citation:
                                                    source_url = url_citation['url']
                                                elif isinstance(url_citation, str):
                                                    source_url = url_citation
                                                
                                                if source_url:
                                                    logger.info(f"[OPENAI] Extracted source_url from url_citation: {source_url}")
                                                    break
                                elif hasattr(annotations, 'url_citation'):
                                    url_citation = annotations.url_citation
                                    if hasattr(url_citation, 'url'):
                                        source_url = url_citation.url
                                    elif isinstance(url_citation, dict) and 'url' in url_citation:
                                        source_url = url_citation['url']
                                    
                                    if source_url:
                                        logger.info(f"[OPENAI] Extracted source_url from annotations.url_citation: {source_url}")
                    
                    # Альтернативный путь: проверяем напрямую наличие url в item
                    if not source_url and hasattr(item, 'url'):
                        source_url = item.url
                        logger.info(f"[OPENAI] Extracted source_url from item.url: {source_url}")
            
            # Если не нашли content, пробуем альтернативные пути
            if not output_content:
                if hasattr(response, 'content'):
                    output_content = response.content
                elif hasattr(response, 'text'):
                    output_content = response.text
            
            # Логируем найденные URL
            if source_url:
                logger.info(f"[OPENAI] Final source_url: {source_url}")
            else:
                logger.info(f"[OPENAI] No source_url found in response")
            
            if not output_content:
                logger.warning("[OPENAI] No content extracted from response")
                return None
            
            # Парсим JSON из ответа
            json_match = re.search(r'\{.*\}', output_content, re.DOTALL)
            if not json_match:
                logger.warning(f"[OPENAI] Response does not contain JSON: {output_content[:200]}")
                # Fallback: возвращаем estimate
                return {
                    "description": text,
                    "calories": 0,
                    "protein_g": 0.0,
                    "fat_g": 0.0,
                    "carbs_g": 0.0,
                    "accuracy_level": "ESTIMATE",
                    "notes": "JSON parsing failed: response format invalid",
                    "source_url": source_url,
                }
            
            try:
                data = json.loads(json_match.group(0))
            except json.JSONDecodeError as e:
                logger.warning(f"[OPENAI] Failed to parse JSON: {e}, raw: {output_content[:200]}")
                # Fallback: возвращаем estimate
                return {
                    "description": text,
                    "calories": 0,
                    "protein_g": 0.0,
                    "fat_g": 0.0,
                    "carbs_g": 0.0,
                    "accuracy_level": "ESTIMATE",
                    "notes": f"JSON parsing failed: {str(e)}",
                    "source_url": source_url,
                }
            
            # Извлекаем данные
            calories = float(data.get("calories", 0) or 0)
            protein_g = float(data.get("protein_g", 0) or 0)
            fat_g = float(data.get("fat_g", 0) or 0)
            carbs_g = float(data.get("carbs_g", 0) or 0)
            accuracy_level = data.get("accuracy_level", "ESTIMATE")
            notes = data.get("notes", "")
            description = data.get("description", text)
            
            # Извлекаем source_url из данных (если модель вернула его в JSON)
            extracted_source_url_from_json = data.get("source_url")
            if extracted_source_url_from_json and extracted_source_url_from_json != "null" and extracted_source_url_from_json:
                # Если source_url уже был извлечен из citations, не перезаписываем
                if not source_url:
                    source_url = extracted_source_url_from_json
            
            # Валидация source_url: проверяем, что это не user-generated база
            user_generated_domains = [
                "fatsecret", "myfitnesspal", "eatthismuch", "health-diet", 
                "calorizator", "fitness", "recept", "calories", "diet",
                "myplate", "sparkpeople", "loseit", "cronometer"
            ]
            
            if source_url:
                source_url_lower = source_url.lower()
                is_user_generated = any(domain in source_url_lower for domain in user_generated_domains)
                
                if is_user_generated:
                    logger.warning(f"[OPENAI] User-generated source detected: {source_url}, discarding")
                    if notes:
                        notes = f"Non-official source discarded. {notes}"
                    else:
                        notes = "Non-official source discarded."
                    source_url = None
                    accuracy_level = "ESTIMATE"
            
            # Проверяем, использовался ли web_search
            if not has_web_search_call:
                if notes:
                    notes = f"model did not use web_search; estimate. {notes}"
                else:
                    notes = "model did not use web_search; estimate"
                accuracy_level = "ESTIMATE"
            
            # Валидация accuracy_level
            if accuracy_level not in ["HIGH", "ESTIMATE"]:
                accuracy_level = "ESTIMATE"
            
            # Если accuracy_level ESTIMATE и source_url есть - проверяем, не является ли он неофициальным
            # Если официальный источник не найден, source_url должен быть null
            if accuracy_level == "ESTIMATE" and source_url:
                # Если source_url не был отфильтрован как user-generated, но accuracy=ESTIMATE,
                # это означает, что официальный источник не найден - убираем source_url
                logger.info(f"[OPENAI] accuracy=ESTIMATE with source_url, removing source_url (official source not found)")
                source_url = None
                if notes and "Non-official source discarded" not in notes:
                    if notes:
                        notes = f"Official source not found. {notes}"
                    else:
                        notes = "Official source not found."
            
            # Если calories = 0, считаем это failed extraction
            if calories <= 0:
                logger.info("[OPENAI] Calories=0, treating as failed extraction")
                return {
                    "description": description or text,
                    "calories": 0,
                    "protein_g": 0.0,
                    "fat_g": 0.0,
                    "carbs_g": 0.0,
                    "accuracy_level": "ESTIMATE",
                    "notes": notes or "calories=0, extraction failed",
                    "source_url": source_url,
                }
            
            # Округляем значения
            calories = round(calories)
            protein_g = round(protein_g, 1)
            fat_g = round(fat_g, 1)
            carbs_g = round(carbs_g, 1)
            
            return {
                "description": description,
                "calories": calories,
                "protein_g": protein_g,
                "fat_g": fat_g,
                "carbs_g": carbs_g,
                "accuracy_level": accuracy_level,
                "notes": notes,
                "source_url": source_url,
            }
            
        except AttributeError as e:
            logger.error(f"[OPENAI] Responses API not available: {e}")
            # Fallback на обычный parse_meal_text будет в main.py
            return None
        except Exception as e:
            logger.error(f"[OPENAI] Error calling Responses API: {e}", exc_info=True)
            return None
        
    except Exception as e:
        logger.error(f"Error in estimate_restaurant_meal_with_openai_websearch: {e}", exc_info=True)
        return None

