#!/usr/bin/env python3
"""
Smoke-check every provider with live keys (run from repo root):

    .venv/bin/python evals/agent_v2/smoke_providers.py

Checks, in order:
  1. FDC search (free, instant)
  2. Gemini plain generation (no search)
  3. Gemini + google_search grounding + JSON schema (verifies paid tier)
  4. Perplexity Sonar + JSON schema (first call compiles the schema: slow once)
  5. OpenAI Responses + web_search (control variant)
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.agent_v2.config import GEMINI_FLASH, OPENAI_MINI, SONAR  # noqa: E402
from app.agent_v2.llm_schemas import BRANDED_SCHEMA  # noqa: E402
from app.agent_v2.providers import fdc, gemini, openai_client, perplexity  # noqa: E402
from app.agent_v2.providers.base import extract_json  # noqa: E402


async def check_fdc():
    foods = await fdc.search_foods("buckwheat cooked")
    best = fdc.pick_best(foods, "buckwheat cooked")
    assert best is not None, "no FDC match"
    return f"{len(foods)} hits; best: {best.description!r} {best.kcal_100g} kcal/100g ({best.url})"


async def check_gemini_plain():
    r = await gemini.generate(GEMINI_FLASH, "Reply with exactly: OK", thinking_level="low")
    return f"text={r.text.strip()[:40]!r} in={r.input_tokens} out={r.output_tokens} {r.duration_ms:.0f}ms"


async def check_gemini_grounded():
    r = await gemini.generate(
        GEMINI_FLASH,
        "Find official calories for McDonald's Big Mac (US). Fill the JSON schema.",
        system="Use web search. Max 2 queries. Return only JSON.",
        json_schema=BRANDED_SCHEMA,
        use_search=True,
        thinking_level="low",
    )
    data = extract_json(r.text)
    return (
        f"kcal={data['items'][0]['calories_kcal']} conf={data.get('confidence')} "
        f"searches={r.search_queries} domains={r.source_domains[:3]} "
        f"url={ (data.get('source_url') or '')[:60] } {r.duration_ms:.0f}ms"
    )


async def check_sonar():
    r = await perplexity.generate(
        SONAR,
        "Official calories and macros for Snickers bar 50g. Fill the JSON schema.",
        system="Return only JSON matching the schema.",
        json_schema=BRANDED_SCHEMA,
        schema_name="branded_result",
    )
    data = extract_json(r.text)
    return (
        f"kcal={data['items'][0]['calories_kcal']} conf={data.get('confidence')} "
        f"urls={[u[:40] for u in r.source_urls[:2]]} {r.duration_ms:.0f}ms"
    )


async def check_openai():
    r = await openai_client.generate(
        OPENAI_MINI,
        "Official calories for Coca-Cola Zero 330ml. Fill the JSON schema.",
        system="Use web search, max 2 queries. Return only JSON.",
        json_schema=BRANDED_SCHEMA,
        schema_name="branded_result",
        use_search=True,
    )
    data = extract_json(r.text)
    return (
        f"kcal={data['items'][0]['calories_kcal']} searches={r.search_queries} "
        f"urls={[u[:40] for u in r.source_urls[:2]]} {r.duration_ms:.0f}ms"
    )


CHECKS = [
    ("FDC", check_fdc),
    ("Gemini plain", check_gemini_plain),
    ("Gemini grounded+schema", check_gemini_grounded),
    ("Sonar schema", check_sonar),
    ("OpenAI web_search", check_openai),
]


async def main():
    results = {}
    for name, fn in CHECKS:
        try:
            results[name] = ("OK", await fn())
        except Exception as e:
            results[name] = ("FAIL", f"{type(e).__name__}: {e}")
        status, detail = results[name]
        print(f"[{status}] {name}: {detail}")
    fails = [n for n, (s, _) in results.items() if s == "FAIL"]
    print(json.dumps({"failed": fails}, ensure_ascii=False))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    asyncio.run(main())
