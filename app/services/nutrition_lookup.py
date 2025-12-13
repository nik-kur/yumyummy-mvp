"""
Единый нутриционный движок для поиска КБЖУ по штрихкоду или названию продукта.
"""
import logging
import re
from typing import Optional

from pydantic import BaseModel

from app.external.openfoodfacts_client import (
    fetch_product_by_barcode,
    search_products_by_name,
)

logger = logging.getLogger(__name__)


class NutritionQuery(BaseModel):
    """Запрос на поиск нутриции."""
    barcode: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    store: Optional[str] = None
    locale: str = "ru-RU"


class NutritionResult(BaseModel):
    """Результат поиска нутриции."""
    found: bool
    
    # описательный блок
    name: Optional[str] = None
    brand: Optional[str] = None
    source_provider: str = "OPENFOODFACTS"
    accuracy_level: str = "ESTIMATE"
    
    # нутриция на порцию
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    
    # информация о порции (в граммах)
    portion_grams: Optional[float] = None


def _to_float(value) -> Optional[float]:
    """
    Безопасное преобразование значения в float.
    Поддерживает int, float, строки с запятой или точкой.
    """
    if value is None:
        return None
    
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, str):
        # Заменяем запятую на точку
        cleaned = value.replace(",", ".").strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return None
    
    return None


def _extract_package_weight(product: dict) -> Optional[float]:
    """
    Извлекает вес упаковки из продукта OpenFoodFacts.
    Пробует product_quantity и quantity, парсит единицы (g, kg, ml).
    Возвращает вес в граммах или None.
    """
    # Пробуем product_quantity (число в граммах)
    product_quantity = product.get("product_quantity")
    if product_quantity:
        try:
            return float(product_quantity)
        except (ValueError, TypeError):
            pass
    
    # Пробуем quantity (строка типа "500 g" или "0.5 kg")
    quantity = product.get("quantity")
    if quantity and isinstance(quantity, str):
        # Ищем паттерн: число + пробел + единица
        match = re.search(r"(\d+\.?\d*)\s*(g|kg|ml|л)", quantity, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            
            if unit in ("g", "г"):
                return value
            elif unit in ("kg", "кг"):
                return value * 1000
            elif unit in ("ml", "мл", "л"):
                # Для жидкостей приравниваем мл к граммам
                if unit == "л":
                    return value * 1000
                return value
    
    return None


def _extract_nutrition_from_openfoodfacts(product: dict) -> dict:
    """
    Извлекает нутрицию из продукта OpenFoodFacts.
    Возвращает dict с полями:
    - calories_per_100g: Optional[float]
    - protein_per_100g: Optional[float]
    - fat_per_100g: Optional[float]
    - carbs_per_100g: Optional[float]
    """
    nutriments = product.get("nutriments", {})
    
    # Калории: пробуем energy-kcal_100g, затем energy_100g (в кДж, делим на 4.184)
    calories = None
    if "energy-kcal_100g" in nutriments:
        calories = _to_float(nutriments["energy-kcal_100g"])
    elif "energy_100g" in nutriments:
        kj = _to_float(nutriments["energy_100g"])
        if kj is not None:
            calories = kj / 4.184
    
    return {
        "calories_per_100g": calories,
        "protein_per_100g": _to_float(nutriments.get("proteins_100g")),
        "fat_per_100g": _to_float(nutriments.get("fat_100g")),
        "carbs_per_100g": _to_float(nutriments.get("carbohydrates_100g")),
    }


async def nutrition_lookup(query: NutritionQuery) -> NutritionResult:
    """
    Поиск нутриции по штрихкоду или названию продукта.
    
    Приоритет:
    - если barcode: fetch_product_by_barcode
    - если name: search_products_by_name, берём первый подходящий
    
    Если нет нутриции (calories_per_100g is None) => found=False.
    Никакие исключения наружу не выбрасываются; логируем и возвращаем found=False.
    """
    try:
        product = None
        
        # Поиск по штрихкоду
        if query.barcode:
            product = await fetch_product_by_barcode(query.barcode)
            if not product:
                logger.debug(f"Product not found by barcode: {query.barcode}")
                return NutritionResult(found=False)
        
        # Поиск по названию
        elif query.name:
            products = await search_products_by_name(
                query.name,
                locale=query.locale,
                brand=query.brand,
                limit=10
            )
            if products:
                product = products[0]  # Берём первый подходящий
            else:
                logger.debug(f"Products not found by name: {query.name}")
                return NutritionResult(found=False)
        
        else:
            return NutritionResult(found=False)
        
        if not product:
            return NutritionResult(found=False)
        
        # Извлекаем нутрицию
        nutrition_data = _extract_nutrition_from_openfoodfacts(product)
        
        if nutrition_data["calories_per_100g"] is None:
            logger.debug("Product found but no calories data")
            return NutritionResult(found=False)
        
        # Извлекаем вес упаковки
        portion_grams = _extract_package_weight(product)
        if portion_grams is None:
            portion_grams = 100.0  # По умолчанию на 100г
        
        # Пересчитываем нутрицию на порцию
        factor = portion_grams / 100.0
        calories_total = nutrition_data["calories_per_100g"] * factor
        protein_total = (
            nutrition_data["protein_per_100g"] * factor
            if nutrition_data["protein_per_100g"] is not None
            else None
        )
        fat_total = (
            nutrition_data["fat_per_100g"] * factor
            if nutrition_data["fat_per_100g"] is not None
            else None
        )
        carbs_total = (
            nutrition_data["carbs_per_100g"] * factor
            if nutrition_data["carbs_per_100g"] is not None
            else None
        )
        
        # Извлекаем название и бренд
        product_name = (
            product.get("product_name")
            or product.get("product_name_en")
            or query.name
            or "Продукт"
        )
        brands = product.get("brands", "")
        product_brand = brands.split(",")[0].strip() if brands else query.brand
        
        return NutritionResult(
            found=True,
            name=product_name,
            brand=product_brand,
            source_provider="OPENFOODFACTS",
            accuracy_level="ESTIMATE",
            calories=calories_total,
            protein_g=protein_total,
            fat_g=fat_total,
            carbs_g=carbs_total,
            portion_grams=portion_grams,
        )
        
    except Exception as e:
        logger.error(f"Error in nutrition_lookup: {e}", exc_info=True)
        return NutritionResult(found=False)
