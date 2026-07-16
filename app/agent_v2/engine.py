"""
Agent v2 engine — intent dispatch.

Two entry modes:
- explicit intent (eval runner, sandbox with a chosen tab, advisor/edit
  surfaces in the app that already know what they are);
- intent="auto" (production /app/agent/run parity): a deterministic barcode
  check, then photo -> photo pipeline, then ONE parse call that doubles as
  the router for free text (its `intent` field decides generic vs branded;
  the parsed items are reused so generic costs no extra call).
"""
import asyncio
import base64
import re
import time
import traceback
from pathlib import Path
from typing import List, Optional

import httpx

from . import prompts
from .config import VARIANTS, VariantSpec
from .llm_schemas import PARSE_SCHEMA
from .pipelines import advisor, barcode, branded, generic, photo
from .providers.base import extract_json
from .providers.dispatch import call_llm, stage_usage
from .schemas import ParseResult, V2Result

MEAL_INTENTS = {"log_meal", "eatout", "product", "photo_meal", "barcode"}

# Barcode detection — same heuristic the v1 router prompt encodes, but free
# and instant: an 8-14 digit run, with nothing else in the message except
# whitespace/punctuation and barcode-ish words ("штрих-код 4600699501398").
_BARCODE_DIGITS_RE = re.compile(r"(?<!\d)\d{8,14}(?!\d)")
_BARCODE_WORDS_RE = re.compile(r"штрих|баркод|barcode|код|скан|scan|ean|upc", re.IGNORECASE)


def _looks_like_barcode(text: str) -> bool:
    if not _BARCODE_DIGITS_RE.search(text or ""):
        return False
    rest = _BARCODE_WORDS_RE.sub("", text)
    rest = re.sub(r"[\d\s\-–—:,.!?()#№]", "", rest)
    return len(rest) <= 2


def _help_result(variant: str, intent: str, language: str) -> V2Result:
    res = V2Result(intent=intent, variant=variant)
    if (language or "ru").startswith("ru"):
        res.message_text = (
            "Я помогаю вести дневник питания: напишите, что вы съели "
            "(например «гречка 200 г и куриная грудка»), пришлите фото блюда "
            "или штрих-код продукта."
        )
    else:
        res.message_text = (
            "I help you log meals: tell me what you ate (e.g. “200 g rice and "
            "grilled chicken”), send a photo of your food, or a barcode."
        )
    return res


async def _load_image(image_path: Optional[str], image_url: Optional[str]) -> Optional[bytes]:
    if image_path:
        return Path(image_path).read_bytes()
    if image_url:
        if image_url.startswith("data:"):
            _, _, b64 = image_url.partition(",")
            return base64.b64decode(b64)
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            return resp.content
    return None


# Multi-photo cap: bounds vision cost/latency per request (25(1) sends <= 4).
MAX_IMAGES = 5


async def _load_all_images(
    image_path: Optional[str],
    image_url: Optional[str],
    image_urls: Optional[List[str]],
) -> List[bytes]:
    """All request images, de-duplicated, capped at MAX_IMAGES.

    `image_url` (the legacy single field) counts first so old clients keep the
    exact same behaviour; `image_urls` is the additive 25(1)+ field.
    """
    urls: List[str] = []
    for u in [image_url] + list(image_urls or []):
        if u and u not in urls:
            urls.append(u)
    urls = urls[:MAX_IMAGES]

    loaded: List[bytes] = []
    if image_path:
        loaded.append(Path(image_path).read_bytes())
    if urls:
        results = await asyncio.gather(
            *(_load_image(None, u) for u in urls), return_exceptions=True
        )
        for r in results:
            if isinstance(r, bytes):
                loaded.append(r)
        # Every URL failing to download is a real error, not "no photo".
        if not loaded:
            raise RuntimeError("failed to download any of the request images")
    return loaded[:MAX_IMAGES]


async def _run_auto(
    text: str,
    spec: VariantSpec,
    *,
    image_path: Optional[str],
    image_url: Optional[str],
    image_urls: Optional[List[str]],
    grams: str,
    serving_hint: str,
    language: str,
) -> V2Result:
    t0 = time.perf_counter()

    # 1) Barcode: deterministic, no LLM.
    if _looks_like_barcode(text):
        res = await barcode.run(text, spec, grams=grams, serving_hint=serving_hint, language=language)
        res.total_duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return res

    # 2) Photo(s): vision call per image; mode "c" escalates clearly-branded
    #    packaged items to a grounded web lookup (v1 router's photo/product
    #    split, in-pipeline).
    images = await _load_all_images(image_path, image_url, image_urls)
    if images:
        res = await photo.run_multi(
            images, spec, caption=text, grams=grams, serving_hint=serving_hint, mode="c"
        )
        res.total_duration_ms = round((time.perf_counter() - t0) * 1000, 1)
        return res

    # 3) Free text: ONE parse call doubles as the router.
    hints = ", ".join(x for x in [f"amount: {grams} g" if grams else "", serving_hint] if x)
    resp = await call_llm(
        spec.parse_provider,
        spec.parse_model,
        prompts.parse_user_msg(text, hints),
        system=prompts.PARSE_SYSTEM,
        json_schema=PARSE_SCHEMA,
        schema_name="parse_result",
    )
    parse_stage = stage_usage("parse_route", spec.parse_provider, spec.parse_model, resp)
    parsed = ParseResult.model_validate(extract_json(resp.text))
    routed = (parsed.intent or "log_meal").lower()

    if routed in ("help", "unknown"):
        res = _help_result(spec.variant, routed, parsed.language or language)
        res.add_stage(parse_stage)
    elif routed in ("eatout", "product") or any(p.is_branded for p in parsed.items):
        res = await branded.run(
            text,
            spec,
            intent=routed if routed in ("eatout", "product") else "product",
            grams=grams,
            serving_hint=serving_hint,
            language=parsed.language or language,
        )
        # Account for the routing call in the final usage/cost picture.
        res.stages.insert(0, parse_stage)
        res.total_cost_usd = round(res.total_cost_usd + parse_stage.cost_usd, 6)
    else:
        res = await generic.run(
            text, spec, grams=grams, serving_hint=serving_hint,
            parsed=parsed, parse_stage=parse_stage,
        )
    res.total_duration_ms = round((time.perf_counter() - t0) * 1000, 1)
    return res


async def run(
    intent: str,
    text: str = "",
    *,
    variant: str = "v2g",
    image_path: Optional[str] = None,
    image_url: Optional[str] = None,
    image_urls: Optional[List[str]] = None,
    grams: str = "",
    serving_hint: str = "",
    language: str = "ru",
    nutrition_context: str = "",
    history_context: str = "",
    conversation_context: str = "",
    photo_mode: str = "b",
) -> V2Result:
    spec: VariantSpec = VARIANTS[variant]
    try:
        if intent == "auto":
            return await _run_auto(
                text,
                spec,
                image_path=image_path,
                image_url=image_url,
                image_urls=image_urls,
                grams=grams,
                serving_hint=serving_hint,
                language=language,
            )

        if intent == "log_meal":
            return await generic.run(text, spec, grams=grams, serving_hint=serving_hint)

        if intent in ("eatout", "product"):
            image_bytes = await _load_image(image_path, image_url)
            return await branded.run(
                text,
                spec,
                intent=intent,
                grams=grams,
                serving_hint=serving_hint,
                language=language,
                image_bytes=image_bytes,
            )

        if intent == "photo_meal":
            images = await _load_all_images(image_path, image_url, image_urls)
            if not images:
                raise ValueError("photo_meal requires image_path or image_url(s)")
            return await photo.run_multi(
                images,
                spec,
                caption=text,
                grams=grams,
                serving_hint=serving_hint,
                mode=photo_mode,
            )

        if intent == "barcode":
            return await barcode.run(
                text, spec, grams=grams, serving_hint=serving_hint, language=language
            )

        if intent == "food_advice":
            image_bytes = await _load_image(image_path, image_url)
            return await advisor.run(
                text,
                spec,
                nutrition_context=nutrition_context,
                history_context=history_context,
                conversation_context=conversation_context,
                image_bytes=image_bytes,
            )

        raise ValueError(f"unsupported intent: {intent}")

    except Exception as exc:
        err = V2Result(intent=intent, variant=variant)
        err.message_text = "v2 engine error"
        tb = traceback.format_exc(limit=3)
        err.error = f"{type(exc).__name__}: {exc}\n{tb[-400:]}"
        return err
