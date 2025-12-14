"""
Tavily API client для веб-поиска через HTTP API.
"""
import json
import logging
from typing import Dict, Any
import httpx

logger = logging.getLogger(__name__)

TAVILY_API_URL = "https://api.tavily.com/search"


async def tavily_search(
    query: str,
    api_key: str,
    max_results: int = 5
) -> Dict[str, Any]:
    """
    Выполняет поиск через Tavily API.
    
    Возвращает dict с результатами поиска или пустой dict {} при ошибке.
    Никогда не выбрасывает исключения наружу.
    """
    if not api_key or not query:
        logger.warning("tavily_search: missing api_key or query")
        return {}
    
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
        "include_raw_content": False,
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(TAVILY_API_URL, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.RequestError as e:
        logger.warning(f"Tavily request error for query '{query}': {e}")
        return {}
    except httpx.HTTPStatusError as e:
        logger.warning(f"Tavily HTTP error for query '{query}': {e.response.status_code} - {e.response.text}")
        return {}
    except json.JSONDecodeError as e:
        logger.warning(f"Tavily JSON decode error for query '{query}': {e}")
        return {}
    except Exception as e:
        logger.warning(f"Unexpected error in tavily_search for query '{query}': {e}")
        return {}

