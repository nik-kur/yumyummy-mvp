#!/usr/bin/env python3
"""
Build the consolidated v1-vs-v2 comparison from eval result files.

Usage:
    .venv/bin/python evals/agent_v2/build_comparison.py

Outputs evals/agent_v2/results/comparison.json and prints a markdown table.
The legacy v1 run on the 30-case brand set (evals/gpt5mini/
v1_medium_original_30.json, HTTP-based) is converted into the same shape so
the "current production" column exists without paying for a fresh $5 rerun.
"""
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[2]
RESULTS = REPO / "evals/agent_v2/results"
sys.path.insert(0, str(REPO))


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _legacy_domain_hit(expected: str, source_url: Optional[str]) -> Optional[bool]:
    expected = (expected or "").strip()
    if not expected:
        return None
    if not source_url:
        return False
    hay = source_url.lower()
    return any(tok.strip().lower() in hay for tok in expected.split("|") if tok.strip())


def load_legacy_v1_brands30() -> Dict[str, Any]:
    src = json.load(open(REPO / "evals/gpt5mini/v1_medium_original_30.json"))
    cases = []
    for r in src["results"]:
        resp = r.get("response") or {}
        totals = resp.get("totals") or {}
        cases.append(
            {
                "case_id": r["case_id"],
                "ok": bool(r.get("success")),
                "latency_ms": r.get("duration_ms") or 0,
                "cost_usd": None,
                "confidence": resp.get("confidence"),
                "totals": totals,
                "source_url": resp.get("source_url"),
                "score": {
                    "domain_hit": _legacy_domain_hit(
                        r.get("expected_source_domains", ""), resp.get("source_url")
                    ),
                    "kcal_ok": None,
                    "kcal_err_pct": None,
                    "url_status": None,
                },
                "search_queries": 0,
            }
        )
    return {
        "meta": {"variant": "v1", "dataset": "legacy v1_medium_original_30.json"},
        "cases": cases,
    }


def summarize(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok = [c for c in cases if c.get("ok")]
    lat = [c["latency_ms"] / 1000 for c in ok if c.get("latency_ms")]
    costs = [c["cost_usd"] for c in ok if c.get("cost_usd") is not None]
    dom = [c for c in ok if c["score"].get("domain_hit") is not None]
    kc = [c for c in ok if c["score"].get("kcal_ok") is not None]
    kerr = [c["score"]["kcal_err_pct"] for c in ok if c["score"].get("kcal_err_pct") is not None]
    url_alive = [c for c in ok if c["score"].get("url_status") in ("alive", "blocked", "redirect_proxy", "dead")]
    high = sum(1 for c in ok if (c.get("confidence") or "").upper() == "HIGH")
    out = {
        "n": len(cases),
        "errors": len(cases) - len(ok),
        "lat_mean": round(statistics.mean(lat), 1) if lat else None,
        "lat_median": round(statistics.median(lat), 1) if lat else None,
        "lat_p90": round(sorted(lat)[max(0, int(round(0.9 * (len(lat) - 1))))], 1) if lat else None,
        "cost_mean": round(statistics.mean(costs), 4) if costs else None,
        "domain_hit": round(sum(1 for c in dom if c["score"]["domain_hit"]) / len(dom), 3) if dom else None,
        "domain_n": len(dom),
        "kcal_ok": round(sum(1 for c in kc if c["score"]["kcal_ok"]) / len(kc), 3) if kc else None,
        "kcal_n": len(kc),
        "kcal_err_median": round(statistics.median(kerr), 1) if kerr else None,
        "high_share": round(high / len(ok), 3) if ok else None,
        "url_dead": sum(1 for c in url_alive if c["score"]["url_status"] == "dead"),
        "url_checked": len(url_alive),
    }
    return out


FILES = {
    ("brands30", "v1"): "LEGACY",
    ("brands30", "v2g"): "v2g_brands30.json",
    ("brands30", "v2g35"): "v2g35_brands30.json",
    ("brands30", "v2s"): "v2s_brands30.json",
    ("brands30", "v2o"): "v2o_brands30.json",
    ("regions14", "v1"): "v1_regions14.json",
    ("regions14", "v2g"): "v2g_regions14.json",
    ("regions14", "v2g35"): "v2g35_regions14.json",
    ("regions14", "v2s"): "v2s_regions14.json",
    ("regions14", "v2o"): "v2o_regions14.json",
    ("generic15", "v1"): "v1_generic15.json",
    ("generic15", "v2g"): "v2g_generic15.json",
    ("generic15", "v2o"): "v2o_generic15.json",
    ("barcodes5", "v1"): "v1_barcodes5.json",
    ("barcodes5", "v2g"): "v2g_barcodes5.json",
}


def main() -> None:
    table: Dict[str, Dict[str, Any]] = {}
    for (dataset, variant), fname in FILES.items():
        if fname == "LEGACY":
            data = load_legacy_v1_brands30()
        else:
            path = RESULTS / fname
            if not path.exists():
                continue
            data = json.load(open(path))
        table.setdefault(dataset, {})[variant] = summarize(data["cases"])

    out_path = RESULTS / "comparison.json"
    out_path.write_text(json.dumps(table, indent=2, ensure_ascii=False), encoding="utf-8")

    for dataset, variants in table.items():
        print(f"\n## {dataset}")
        hdr = f"{'variant':7} | {'lat med':>7} | {'p90':>6} | {'$/req':>7} | {'domain':>6} | {'kcal_ok':>7} | {'err%md':>6} | {'HIGH%':>5} | {'dead':>4} | {'err':>3}"
        print(hdr)
        print("-" * len(hdr))
        for v in ("v1", "v2g", "v2g35", "v2s", "v2o"):
            s = variants.get(v)
            if not s:
                continue
            print(
                f"{v:7} | {s['lat_median'] or '—':>7} | {s['lat_p90'] or '—':>6} | "
                f"{s['cost_mean'] if s['cost_mean'] is not None else '—':>7} | "
                f"{s['domain_hit'] if s['domain_hit'] is not None else '—':>6} | "
                f"{s['kcal_ok'] if s['kcal_ok'] is not None else '—':>7} | "
                f"{s['kcal_err_median'] if s['kcal_err_median'] is not None else '—':>6} | "
                f"{s['high_share'] if s['high_share'] is not None else '—':>5} | "
                f"{s['url_dead']}/{s['url_checked']:>2} | {s['errors']:>3}"
            )
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
