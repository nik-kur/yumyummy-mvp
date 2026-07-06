"""
USDA FoodData Central client.

We query Foundation + SR Legacy (lab-analyzed, per-100g) and convert the
`foodNutrients` array into a compact macro dict. Free api.data.gov key,
1000 req/h.
"""
from dataclasses import dataclass
from typing import List, Optional

import httpx

from ..config import FDC_SEARCH_URL, env
from .base import ProviderError, Stopwatch

# FDC nutrient numbers (per 100 g)
_N_KCAL = "208"
_N_PROTEIN = "203"
_N_FAT = "204"
_N_CARBS = "205"


@dataclass
class FdcFood:
    fdc_id: int
    description: str
    data_type: str
    kcal_100g: float
    protein_100g: float
    fat_100g: float
    carbs_100g: float
    match_score: float = 0.0

    @property
    def url(self) -> str:
        return f"https://fdc.nal.usda.gov/food-details/{self.fdc_id}/nutrients"


def _nutrients_from_search_hit(food: dict) -> Optional[FdcFood]:
    values = {}
    for n in food.get("foodNutrients") or []:
        num = str(n.get("nutrientNumber") or "")
        if num in (_N_KCAL, _N_PROTEIN, _N_FAT, _N_CARBS):
            values[num] = float(n.get("value") or 0)
    if values.get(_N_KCAL) is None or values.get(_N_KCAL, 0) <= 0:
        return None
    return FdcFood(
        fdc_id=int(food["fdcId"]),
        description=food.get("description") or "",
        data_type=food.get("dataType") or "",
        kcal_100g=values.get(_N_KCAL, 0.0),
        protein_100g=values.get(_N_PROTEIN, 0.0),
        fat_100g=values.get(_N_FAT, 0.0),
        carbs_100g=values.get(_N_CARBS, 0.0),
        match_score=float(food.get("score") or 0),
    )


async def search_foods(
    query: str,
    *,
    page_size: int = 6,
    data_types: str = "Foundation,SR Legacy",
    timeout_s: float = 10.0,
) -> List[FdcFood]:
    key = env("FDC_API_KEY")
    if not key:
        raise ProviderError("fdc", "FDC_API_KEY is not set")
    params = {
        "api_key": key,
        "query": query,
        "pageSize": page_size,
        "dataType": data_types,
    }
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        with Stopwatch() as sw:
            resp = await client.get(FDC_SEARCH_URL, params=params)
    if resp.status_code == 429:
        raise ProviderError("fdc", "rate limited (429)", 429)
    if resp.status_code != 200:
        raise ProviderError("fdc", f"HTTP {resp.status_code}: {resp.text[:300]}", resp.status_code)

    foods = resp.json().get("foods") or []
    out: List[FdcFood] = []
    for f in foods:
        parsed = _nutrients_from_search_hit(f)
        if parsed:
            out.append(parsed)
    # attach timing to the first element consumer via return, callers time themselves
    _ = sw.ms
    return out


def _norm(token: str) -> str:
    token = token.strip(",()").lower()
    if len(token) > 3 and token.endswith("s"):
        token = token[:-1]
    return token


def pick_best(candidates: List[FdcFood], query: str) -> Optional[FdcFood]:
    """
    Cheap deterministic rerank on top of FDC relevance, tuned against real
    misses ("apple raw" -> "Rose-apples, raw"; "oats dry" -> QUAKER entries):
    - big boost when the description's head word IS the query's head noun
    - reward token overlap (plural-insensitive)
    - penalize branded entries (ALL-CAPS brand tokens) vs generic ones
    """
    if not candidates:
        return None
    q_tokens = [_norm(t) for t in query.replace(",", " ").split() if len(t) > 2]
    if not q_tokens:
        return max(candidates, key=lambda c: c.match_score)
    head = q_tokens[0]

    def score(c: FdcFood) -> float:
        words = c.description.replace("-", " ").replace(",", " ").split()
        d_tokens = {_norm(w) for w in words}
        first = _norm(words[0]) if words else ""
        s = 0.0
        if first == head:
            s += 3.0
        elif head in d_tokens:
            s += 1.0
        s += len(set(q_tokens) & d_tokens)
        if any(w.isupper() and len(w) > 2 for w in words):
            s -= 1.5
        return s + c.match_score / 1000.0

    return max(candidates, key=score)
