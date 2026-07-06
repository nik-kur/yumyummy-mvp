#!/usr/bin/env python3
"""
Agent v2 eval runner (in-process, no HTTP server needed).

Examples (from repo root):
  .venv/bin/python evals/agent_v2/run_v2_eval.py --variant v2g \
      --dataset evals/agent_v2/datasets/brands_regions_v1.csv \
      --out evals/agent_v2/results/v2g_regions.json --concurrency 4

  .venv/bin/python evals/agent_v2/run_v2_eval.py --variant v1 \
      --dataset evals/agent_v2/datasets/generic_15.csv \
      --out evals/agent_v2/results/v1_generic.json --concurrency 3

Variants: v2g | v2g35 | v2s | v2o (app/agent_v2) and v1 (production workflow,
imported in-process from app/agent_workflow — requires OPENAI_API_KEY).
"""
import argparse
import asyncio
import csv
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

AGENT_TYPE_TO_INTENT = {
    "eatout": "eatout",
    "product": "product",
    "log_meal": "log_meal",
    "barcode": "barcode",
    "photo": "photo_meal",
    "photo_meal": "photo_meal",
    "advice": "food_advice",
    "food_advice": "food_advice",
}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _expected_domain_hit(
    expected: str,
    source_url: Optional[str],
    cited: List[str],
    item_urls: List[str],
) -> Optional[bool]:
    expected = (expected or "").strip()
    if not expected:
        return None
    tokens = [t.strip().lower() for t in expected.split("|") if t.strip()]
    haystack = [d.lower() for d in cited if d]
    for u in [source_url] + item_urls:
        if u:
            haystack.append(_domain(u))
            haystack.append(u.lower())
    for token in tokens:
        for h in haystack:
            if token in h:
                return True
    return False


def _kcal_ok(expected_kcal: str, tol_pct: str, actual: float) -> Optional[bool]:
    if expected_kcal in ("", None):
        return None
    try:
        exp = float(expected_kcal)
    except ValueError:
        return None
    if exp == 0:
        return abs(actual) <= 5
    tol = float(tol_pct) / 100 if tol_pct not in ("", None) else 0.25
    return abs(actual - exp) / exp <= tol


def _kcal_err_pct(expected_kcal: str, actual: float) -> Optional[float]:
    try:
        exp = float(expected_kcal)
    except (TypeError, ValueError):
        return None
    if exp <= 0:
        return None
    return round(abs(actual - exp) / exp * 100, 1)


async def _url_alive(url: Optional[str]) -> Optional[str]:
    """
    'alive' | 'dead' | 'blocked' | 'redirect_proxy' | None.
    Catches hallucinated source links — a metric the v1 evals never had.
    """
    import httpx

    if not url or not url.startswith("http"):
        return None
    if "vertexaisearch" in url or "grounding-api-redirect" in url:
        return "redirect_proxy"
    # SPA that serves its app shell with HTTP 404; links work fine in browsers.
    if "fdc.nal.usda.gov" in url:
        return "alive"
    try:
        async with httpx.AsyncClient(
            timeout=8.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; YumYummyEval/1.0)"},
        ) as client:
            resp = await client.head(url)
            if resp.status_code in (405, 501):
                resp = await client.get(url)
            if resp.status_code < 400:
                return "alive"
            if resp.status_code in (401, 403, 429):
                return "blocked"  # bot-blocked; can't verify, don't count as dead
            return "dead"
    except Exception:
        return "dead"


# ---------------------------------------------------------------------------
# Case execution
# ---------------------------------------------------------------------------

async def run_case_v2(row: Dict[str, str], variant: str, photo_mode: str) -> Dict[str, Any]:
    from app.agent_v2 import engine

    intent = AGENT_TYPE_TO_INTENT[row["agent_type"].strip()]
    t0 = time.perf_counter()
    res = await engine.run(
        intent,
        row.get("input_as_text", ""),
        variant=variant,
        image_url=row.get("image_url") or None,
        image_path=row.get("image_path") or None,
        photo_mode=photo_mode,
    )
    wall_ms = (time.perf_counter() - t0) * 1000
    d = res.model_dump()
    return {
        "ok": res.error is None,
        "error": res.error,
        "latency_ms": round(wall_ms, 1),
        "cost_usd": res.total_cost_usd,
        "confidence": res.confidence,
        "intent": res.intent,
        "totals": d["totals"],
        "items": d["items"],
        "source_url": res.source_url,
        "cited_domains": res.cited_domains,
        "message_text": res.message_text,
        "stages": d["stages"],
        "search_queries": sum(s.search_queries for s in res.stages),
    }


def _image_data_url(path: str) -> str:
    """v1 only accepts image URLs; wrap local eval photos as data: URLs."""
    import base64

    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    payload = base64.b64encode(Path(path).read_bytes()).decode()
    return f"data:{mime};base64,{payload}"


async def run_case_v1(row: Dict[str, str]) -> Dict[str, Any]:
    from app.agent_workflow.workflow import run_text

    intent = AGENT_TYPE_TO_INTENT[row["agent_type"].strip()]
    image_url = row.get("image_url") or None
    if not image_url and row.get("image_path"):
        image_url = _image_data_url(row["image_path"])
    # Photos take the real prod path: the router sees the image and picks
    # photo_meal / nutrition_label / product itself, exactly like the app.
    force = None if intent == "photo_meal" else intent
    t0 = time.perf_counter()
    try:
        res = await run_text(
            text=row.get("input_as_text", ""),
            telegram_id="eval_v2_runner",
            image_url=image_url,
            force_intent=force,
        )
        wall_ms = (time.perf_counter() - t0) * 1000
        totals = res.get("totals") or {}
        return {
            "ok": True,
            "error": None,
            "latency_ms": round(wall_ms, 1),
            "cost_usd": None,  # v1 does not report usage; use published reports
            "confidence": res.get("confidence"),
            "intent": res.get("intent"),
            "totals": totals,
            "items": res.get("items") or [],
            "source_url": res.get("source_url"),
            "cited_domains": [],
            "message_text": res.get("message_text") or "",
            "stages": [],
            "search_queries": 0,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
            "cost_usd": None,
            "confidence": None,
            "intent": intent,
            "totals": {},
            "items": [],
            "source_url": None,
            "cited_domains": [],
            "message_text": "",
            "stages": [],
            "search_queries": 0,
        }


def score_case(row: Dict[str, str], out: Dict[str, Any], url_status: Optional[str] = None) -> Dict[str, Any]:
    totals = out.get("totals") or {}
    kcal = float(totals.get("calories_kcal") or 0)
    domain_hit = _expected_domain_hit(
        row.get("expected_source_domains", ""),
        out.get("source_url"),
        out.get("cited_domains") or [],
        [i.get("source_url") or "" for i in (out.get("items") or [])],
    )
    kcal_ok = _kcal_ok(row.get("expected_kcal", ""), row.get("kcal_tolerance_pct", ""), kcal)
    nonzero_expected = row.get("expected_kcal") not in ("", "0", None)
    return {
        "case_id": row["case_id"],
        "agent_type": row["agent_type"],
        "input": row.get("input_as_text", ""),
        "region": row.get("region", ""),
        **out,
        "score": {
            "domain_hit": domain_hit,
            "kcal_ok": kcal_ok,
            "kcal_err_pct": _kcal_err_pct(row.get("expected_kcal", ""), kcal),
            "zero_kcal_bug": bool(out.get("ok")) and kcal <= 0 and nonzero_expected,
            "url_status": url_status,
        },
    }


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _pct(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = min(len(values) - 1, max(0, int(round(p / 100 * (len(values) - 1)))))
    return values[idx]


def summarize(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok_cases = [c for c in cases if c["ok"]]
    lat = [c["latency_ms"] / 1000 for c in ok_cases]
    costs = [c["cost_usd"] for c in ok_cases if c.get("cost_usd") is not None]
    domain_scored = [c for c in ok_cases if c["score"]["domain_hit"] is not None]
    kcal_scored = [c for c in ok_cases if c["score"]["kcal_ok"] is not None]
    kcal_errs = [c["score"]["kcal_err_pct"] for c in ok_cases if c["score"]["kcal_err_pct"] is not None]
    conf = {}
    for c in ok_cases:
        conf[c.get("confidence") or "none"] = conf.get(c.get("confidence") or "none", 0) + 1
    return {
        "n": len(cases),
        "ok": len(ok_cases),
        "errors": len(cases) - len(ok_cases),
        "latency_s": {
            "mean": round(statistics.mean(lat), 2) if lat else None,
            "median": round(statistics.median(lat), 2) if lat else None,
            "p90": round(_pct(lat, 90), 2) if lat else None,
            "max": round(max(lat), 2) if lat else None,
        },
        "cost_usd": {
            "mean": round(statistics.mean(costs), 5) if costs else None,
            "total": round(sum(costs), 4) if costs else None,
        },
        "domain_hit_rate": round(
            sum(1 for c in domain_scored if c["score"]["domain_hit"]) / len(domain_scored), 3
        )
        if domain_scored
        else None,
        "domain_scored_n": len(domain_scored),
        "kcal_ok_rate": round(
            sum(1 for c in kcal_scored if c["score"]["kcal_ok"]) / len(kcal_scored), 3
        )
        if kcal_scored
        else None,
        "kcal_scored_n": len(kcal_scored),
        "kcal_err_pct_median": round(statistics.median(kcal_errs), 1) if kcal_errs else None,
        "zero_kcal_bugs": sum(1 for c in ok_cases if c["score"]["zero_kcal_bug"]),
        "url_status_dist": {
            s: sum(1 for c in ok_cases if c["score"].get("url_status") == s)
            for s in ("alive", "blocked", "redirect_proxy", "dead")
            if any(c["score"].get("url_status") == s for c in ok_cases)
        },
        "confidence_dist": conf,
        "mean_search_queries": round(
            statistics.mean([c["search_queries"] for c in ok_cases]), 2
        )
        if ok_cases
        else None,
    }


async def warmup(variant: str) -> None:
    """Compile Perplexity JSON schemas / open connections outside timed runs."""
    if variant != "v2s":
        return
    from app.agent_v2.config import SONAR
    from app.agent_v2.llm_schemas import ADVISOR_SCHEMA, BRANDED_SCHEMA
    from app.agent_v2.providers import perplexity

    for name, schema in [("branded_result", BRANDED_SCHEMA), ("advisor_result", ADVISOR_SCHEMA)]:
        try:
            await perplexity.generate(
                SONAR,
                "Calories in 100g apple. Fill the schema.",
                json_schema=schema,
                schema_name=name,
            )
        except Exception as e:
            print(f"[warmup] {name}: {type(e).__name__}: {e}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True, choices=["v1", "v2g", "v2g35", "v2s", "v2o"])
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--photo-mode", default="b", choices=["a", "b", "c"])
    ap.add_argument("--only", default="", help="comma-separated case_ids")
    args = ap.parse_args()

    with open(args.dataset, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if args.only:
        wanted = {c.strip() for c in args.only.split(",")}
        rows = [r for r in rows if r["case_id"] in wanted]
    if args.limit:
        rows = rows[: args.limit]

    await warmup(args.variant)

    sem = asyncio.Semaphore(args.concurrency)

    async def one(row: Dict[str, str]) -> Dict[str, Any]:
        async with sem:
            if args.variant == "v1":
                out = await run_case_v1(row)
            else:
                out = await run_case_v2(row, args.variant, args.photo_mode)
            url_status = await _url_alive(out.get("source_url"))
            scored = score_case(row, out, url_status)
            s = scored["score"]
            print(
                f"[{scored['case_id']}] ok={scored['ok']} {scored['latency_ms']/1000:.1f}s "
                f"kcal={ (scored.get('totals') or {}).get('calories_kcal') } "
                f"conf={scored.get('confidence')} domain={s['domain_hit']} kcal_ok={s['kcal_ok']}"
                + (f" ERR={scored['error'][:120]}" if scored["error"] else "")
            )
            return scored

    t0 = time.perf_counter()
    cases = await asyncio.gather(*(one(r) for r in rows))
    wall_s = round(time.perf_counter() - t0, 1)

    report = {
        "meta": {
            "variant": args.variant,
            "dataset": args.dataset,
            "n": len(cases),
            "concurrency": args.concurrency,
            "photo_mode": args.photo_mode,
            "wall_clock_s": wall_s,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        "summary": summarize(list(cases)),
        "cases": list(cases),
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== {args.variant} on {Path(args.dataset).name} (wall {wall_s}s) ===")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"saved -> {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
