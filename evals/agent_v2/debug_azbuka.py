"""Reproduce the Azbuka Vkusa 3-label photo case with candidate/probe tracing."""
import asyncio
import sys

sys.path.insert(0, ".")
from dotenv import load_dotenv

load_dotenv(".env")

import app.agent_v2.pipelines.branded as br

_orig_probe = br.probe_urls
_orig_rank = br.rank_candidates


async def probe_dbg(urls, timeout=3.0):
    res = await _orig_probe(urls, timeout)
    for u in urls:
        print(f"      probe alive={res.get(u)} {u}")
    return res


def rank_dbg(model_url, provider_urls, official="", **kw):
    out = _orig_rank(model_url, provider_urls, official, **kw)
    print(f"    rank(official={official!r}, model_url={model_url!r}, n_provider={len(provider_urls)})")
    for u in out[:6]:
        print(f"      cand {u}")
    return out


br.probe_urls = probe_dbg
br.rank_candidates = rank_dbg

from app.agent_v2 import engine  # noqa: E402


async def main():
    res = await engine.run(
        "auto", "", variant="v2g",
        image_path="evals/agent_v2/datasets/photos/azbuka_three.jpg",
    )
    print()
    print("intent:", res.intent, "| conf:", res.confidence, "| err:", res.error)
    print("kcal total:", round(res.totals.calories_kcal))
    for i in res.items:
        print(f"  - {i.name[:60]:<60} {i.grams}g {round(i.calories_kcal)} kcal src={i.source_url}")
    print("main source_url:", res.source_url)


asyncio.run(main())
