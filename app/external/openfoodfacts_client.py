"""
OpenFoodFacts API client для поиска продуктов по штрихкоду и названию.
"""
import logging
from typing import Optional, List
import httpx

logger = logging.getLogger(__name__)

OPENFOODFACTS_API_BASE = "https://world.openfoodfacts.org/api/v2"


async def fetch_product_by_barcode(barcode: str) -> Optional[dict]:
    """
    Получить продукт по штрихкоду через OpenFoodFacts API.
    
    Возвращает dict с данными продукта или None, если не найден или ошибка.
    Фильтрует результаты по наличию nutriments energy-kcal_100g или energy_100g.
    """
    if not barcode or not barcode.strip():
        return None
    
    url = f"{OPENFOODFACTS_API_BASE}/product/{barcode.strip()}"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            
            product = data.get("product")
            if not product:
                return None
            
            # Проверяем наличие калорий
            nutriments = product.get("nutriments", {})
            has_calories = (
                nutriments.get("energy-kcal_100g") is not None
                or nutriments.get("energy_100g") is not None
            )
            
            if not has_calories:
                logger.debug(f"Product {barcode} found but no calories data")
                return None
            
            return product
            
    except Exception as e:
        logger.warning(f"Error fetching product by barcode {barcode}: {e}")
        return None


async def search_products_by_name(
    name: str,
    locale: str = "ru-RU",
    brand: Optional[str] = None,
    limit: int = 10
) -> List[dict]:
    """
    Поиск продуктов по названию через OpenFoodFacts API.
    
    Возвращает список dict с данными продуктов, отсортированных по релевантности.
    Фильтрует результаты по наличию nutriments energy-kcal_100g или energy_100g.
    """
    if not name or not name.strip():
        return []
    
    # Формируем поисковый запрос
    query = name.strip()
    if brand:
        query = f"{query} {brand.strip()}"
    
    url = f"{OPENFOODFACTS_API_BASE}/cgi/search.pl"
    params = {
        "search_terms": query,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "page_size": limit,
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            products = data.get("products", [])
            if not products:
                return []
            
            # Фильтруем по наличию калорий
            filtered = []
            for product in products:
                nutriments = product.get("nutriments", {})
                has_calories = (
                    nutriments.get("energy-kcal_100g") is not None
                    or nutriments.get("energy_100g") is not None
                )
                
                if has_calories:
                    filtered.append(product)
            
            return filtered[:limit]
            
    except Exception as e:
        logger.warning(f"Error searching products by name '{name}': {e}")
        return []
