"""
Auto-routing smoke: run engine.run(intent="auto") over a mixed set and check
which pipeline each message lands in (production /app/agent/run parity).

Usage:
    python -u evals/agent_v2/run_auto_routing.py [variant]
"""
import asyncio
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from app.agent_v2 import engine  # noqa: E402

# (text, image_path, expected_intent)
CASES = [
    # barcode — deterministic, no LLM
    ("4600699501398", None, "barcode"),
    ("штрих-код 5449000000996", None, "barcode"),
    ("barcode 8000500310427", None, "barcode"),
    # generic (log_meal)
    ("гречка 200 г и куриная грудка 150 г", None, "log_meal"),
    ("овсянка на воде из 60 г хлопьев и банан", None, "log_meal"),
    ("2 вареных яйца и тост с маслом", None, "log_meal"),
    ("салат из огурцов и помидоров с оливковым маслом", None, "log_meal"),
    ("borsch bowl and a slice of rye bread", None, "log_meal"),
    # eatout
    ("капучино и тунакадо из Joe & The Juice", None, "eatout"),
    ("биг мак и средняя картошка из макдональдса", None, "eatout"),
    ("гранде латте из старбакса", None, "eatout"),
    ("шаурма из Wolt-а от Döner Pasha", None, "eatout"),
    # product
    ("сникерс 50 г", None, "product"),
    ("актимель клубничный, одна бутылочка", None, "product"),
    ("творог Простоквашино 5% 200 г", None, "product"),
    ("Barilla penne 80 g dry with Mutti tomato sauce", None, "product"),
    # help / unknown
    ("что ты умеешь?", None, "help"),
    ("привет! как дела?", None, "unknown"),
    # photo (image forces photo pipeline)
    ("", "evals/agent_v2/datasets/photos/real/photo_03.jpg", "photo_meal"),
]

BRANDED_AS_OK = {"eatout", "product"}  # eatout/product mixups are acceptable


async def run_case(text, image_path, expected, variant):
    t0 = time.perf_counter()
    res = await engine.run(
        "auto",
        text,
        variant=variant,
        image_path=str(ROOT / image_path) if image_path else None,
    )
    dt = round((time.perf_counter() - t0) * 1000)
    got = res.intent
    ok = got == expected or (expected in BRANDED_AS_OK and got in BRANDED_AS_OK)
    return {
        "text": text or f"[photo] {image_path}",
        "expected": expected,
        "got": got,
        "ok": ok,
        "ms": dt,
        "kcal": round(res.totals.calories_kcal),
        "conf": res.confidence,
        "err": res.error,
    }


async def main():
    variant = sys.argv[1] if len(sys.argv) > 1 else "v2g"
    sem = asyncio.Semaphore(4)

    async def guarded(c):
        async with sem:
            return await run_case(*c, variant)

    rows = await asyncio.gather(*[guarded(c) for c in CASES])
    ok_n = sum(r["ok"] for r in rows)
    for r in rows:
        mark = "OK " if r["ok"] else "MISS"
        print(f"[{mark}] {r['expected']:>10} -> {r['got']:<10} {r['ms']:>6}ms  kcal={r['kcal']:>5}  {r['text'][:60]}")
        if r["err"]:
            print(f"       err: {r['err'][:200]}")
    print(f"\nintent match: {ok_n}/{len(rows)}")
    out = ROOT / "evals/agent_v2/results/auto_routing.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"variant": variant, "rows": rows}, ensure_ascii=False, indent=2))
    print(f"saved -> {out}")


if __name__ == "__main__":
    asyncio.run(main())
