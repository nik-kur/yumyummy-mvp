"""Shared helpers for v2 pipelines."""
import asyncio
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx

from ..providers import fdc
from ..schemas import Item, ParsedItem, Totals

_REDIRECT_MARKERS = ("vertexaisearch", "grounding-api-redirect")
_UA = {"User-Agent": "Mozilla/5.0 (compatible; YumYummy/2.0)"}


def is_redirect_url(url: str) -> bool:
    return any(m in url for m in _REDIRECT_MARKERS)


def domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


async def _resolve_one(url: str, timeout: float = 3.0, max_hops: int = 5) -> str:
    """Walk redirects reading only headers; never download bodies."""
    current = url
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            for _ in range(max_hops):
                async with client.stream("GET", current, headers=_UA) as resp:
                    if resp.status_code in (301, 302, 303, 307, 308):
                        loc = resp.headers.get("location")
                        if not loc:
                            return current
                        current = urljoin(current, loc)
                        continue
                    return current
    except Exception:
        return ""
    return current


async def resolve_redirect_urls(urls: List[str], limit: int = 3) -> List[str]:
    """Resolve grounding redirect links to their real destination URLs."""
    targets = [u for u in urls if u][:limit]
    if not targets:
        return []
    resolved = await asyncio.gather(*(_resolve_one(u) for u in targets))
    out: List[str] = []
    for u in resolved:
        if u and not is_redirect_url(u) and u not in out:
            out.append(u)
    return out


# User-generated / aggregator domains: never a good primary source for a
# branded item. Ranked to the bottom; forums are effectively banned.
_FORUM_DOMAINS = (
    "reddit.com", "quora.com", "otzovik.com", "irecommend.ru", "pikabu.ru",
    "vk.com", "facebook.com", "instagram.com", "tiktok.com", "x.com",
    "twitter.com", "youtube.com", "dzen.ru", "livejournal.com",
)
_AGGREGATOR_DOMAINS = (
    "fatsecret", "myfitnesspal", "nutritionix", "calorieking", "calorizator",
    "health-diet.ru", "bonfit.ru", "openfoodfacts",
)


def _source_rank(url: str, official_domain: str = "") -> int:
    """Lower is better. Official brand domain wins; forums lose."""
    d = domain_of(url)
    if not d:
        return 90
    official = (official_domain or "").lower().replace("www.", "").strip()
    if official:
        if d == official or d.endswith("." + official):
            return 0
        core = official.split(".")[0]
        # Regional TLDs (joeandthejuice.is) and compressed CDN/mirror names
        # (content.joejuice.com for joeandthejuice.com) still count as official.
        compressed = core.replace("and", "").replace("the", "")
        host_flat = d.replace(".", "").replace("-", "")
        if len(core) >= 5 and core in host_flat:
            return 1
        if len(compressed) >= 6 and compressed != core and compressed in host_flat:
            return 1
    if any(f in d for f in _FORUM_DOMAINS):
        return 80
    if any(a in d for a in _AGGREGATOR_DOMAINS):
        return 40
    return 20


# Rank penalty for a URL the model typed itself but the search layer did not
# confirm. Keeps official model links above neutral provider pages (5+penalty
# < 20) while neutral model links stay below confirmed neutral pages.
_UNCONFIRMED_PENALTY = 5


def choose_source_url(
    model_url: str, provider_urls: List[str], official_domain: str = ""
) -> Optional[str]:
    """
    Pick a source link we can actually stand behind.

    Candidates: pages the provider's search layer really returned, plus the
    model-typed URL with a small "unconfirmed" penalty. Official brand domain
    > neutral pages > aggregators > forums; ties keep provider order.
    """
    model_url = (model_url or "").strip()
    candidates: List[tuple] = [
        (_source_rank(u, official_domain), i, u) for i, u in enumerate(provider_urls)
    ]
    if model_url and not is_redirect_url(model_url) and model_url not in provider_urls:
        candidates.append(
            (
                _source_rank(model_url, official_domain) + _UNCONFIRMED_PENALTY,
                len(candidates),
                model_url,
            )
        )
    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], t[1]))
    return candidates[0][2]


# Markers of "soft 404" pages: the server answers 200 but renders an error
# page (very common on restaurant/retail sites and RU aggregators).
_SOFT_404_MARKERS = (
    "страница не найдена",
    "страницу не найд",
    "не найдена",
    "page not found",
    "page you requested",
    "nothing was found",
    "not be found",
    "does not exist",
    "no longer available",
    "страница удалена",
    "товар не найден",
    "продукт не найден",
    "ошибка 404",
    "error 404",
    "erreur 404",
    "seite nicht gefunden",
    "sayfa bulunamad",
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
# SPA JS bundles legitimately contain strings like "page not found" as l10n
# resources — only scan markup that could actually render.
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL
)


def _looks_like_soft_404(final_url: str, original_url: str, body_head: str) -> bool:
    # 404 pages love to advertise themselves in <title>; body <h1>s are
    # covered by scanning the first chunk of HTML we already downloaded.
    title_m = _TITLE_RE.search(body_head)
    title = (title_m.group(1) if title_m else "").lower()
    if "404" in title:
        return True
    if any(m in title for m in _SOFT_404_MARKERS):
        return True
    visible = _SCRIPT_STYLE_RE.sub(" ", body_head).lower()
    if any(m in visible for m in _SOFT_404_MARKERS):
        return True
    # Deep link that got silently collapsed to the site root is a dead page.
    try:
        orig_path = urlparse(original_url).path.rstrip("/")
        final_path = urlparse(final_url).path.rstrip("/")
        if len(orig_path) > 8 and final_path == "":
            return True
    except Exception:
        pass
    return False


async def url_alive_quick(url: str, timeout: float = 3.0) -> bool:
    """
    Liveness probe that also catches soft 404s (HTTP 200 + "page not found"
    body). Downloads at most ~40 KB of the page.

    Only positive evidence of death counts: explicit 4xx/5xx or a soft-404
    page. Timeouts and TLS quirks mean "couldn't verify" — those pages are
    usually geo-/bot-blocked for our server yet fine in the user's browser,
    so we keep them. Cannot-connect/DNS-failure means dead (hallucinated
    domains land here).
    """
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers=_UA
        ) as client:
            async with client.stream("GET", url) as resp:
                # Bot walls (401/403/429) usually render fine in real browsers.
                if resp.status_code in (401, 403, 429):
                    return True
                if resp.status_code >= 400:
                    return False
                ctype = resp.headers.get("content-type", "")
                if "html" not in ctype:
                    return True  # PDFs, images, JSON — a 200 is enough.
                chunks: List[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes():
                    chunks.append(chunk)
                    total += len(chunk)
                    if total >= 40_960:
                        break
                body_head = b"".join(chunks).decode("utf-8", errors="ignore")
                return not _looks_like_soft_404(str(resp.url), url, body_head)
    except httpx.TimeoutException:
        return True  # unverifiable, not provably dead
    except httpx.ConnectError:
        return False  # DNS failure / connection refused — dead or fake domain
    except Exception:
        return True  # odd TLS/protocol issues: don't punish the page


async def probe_urls(urls: List[str], timeout: float = 3.0) -> Dict[str, bool]:
    """Probe unique URLs in parallel; returns url -> alive."""
    unique = list(dict.fromkeys(u for u in urls if u))
    if not unique:
        return {}
    results = await asyncio.gather(*(url_alive_quick(u, timeout) for u in unique))
    return dict(zip(unique, results))


def rank_candidates(
    model_url: str,
    provider_urls: List[str],
    official_domain: str = "",
    include_official_homepage: bool = False,
) -> List[str]:
    """All source candidates, best first (same ordering as choose_source_url)."""
    model_url = (model_url or "").strip()
    candidates: List[tuple] = [
        (_source_rank(u, official_domain), i, u) for i, u in enumerate(provider_urls)
    ]
    if model_url and not is_redirect_url(model_url) and model_url not in provider_urls:
        candidates.append(
            (
                _source_rank(model_url, official_domain) + _UNCONFIRMED_PENALTY,
                len(candidates),
                model_url,
            )
        )
    if include_official_homepage and official_domain:
        # Brand homepage: worse than an official deep page (rank 0/1) but
        # better than aggregators/neutral pages when those are all we have.
        d = official_domain.lower().strip().replace("www.", "")
        d = d.split("//")[-1].split("/")[0]
        if d and "." in d and not any(domain_of(c[2]) == d and _source_rank(c[2], official_domain) <= 2 for c in candidates):
            candidates.append((2, len(candidates), f"https://{d}/"))
    candidates.sort(key=lambda t: (t[0], t[1]))
    return [c[2] for c in candidates]


async def choose_live_source_url(
    model_url: str,
    provider_urls: List[str],
    official_domain: str = "",
    max_probes: int = 4,
) -> Optional[str]:
    """
    Rank candidates, probe the top few in parallel and return the best LIVE
    page. If every probed candidate is dead, return None — showing no link is
    better than showing a guaranteed 404 (confidence then drops to ESTIMATE
    via the existing "HIGH requires a link" rule).
    """
    ranked = rank_candidates(model_url, provider_urls, official_domain)
    if not ranked:
        return None
    head = ranked[:max_probes]
    alive = await probe_urls(head)
    for u in head:
        if alive.get(u):
            return u
    return None


def sum_totals(items: List[Item]) -> Totals:
    return Totals(
        calories_kcal=round(sum(i.calories_kcal for i in items), 1),
        protein_g=round(sum(i.protein_g for i in items), 1),
        fat_g=round(sum(i.fat_g for i in items), 1),
        carbs_g=round(sum(i.carbs_g for i in items), 1),
    )


def format_message(totals: Totals, confidence: str, note: str = "", source: str = "") -> str:
    lines = [
        "Total: {:.0f} kcal • P {:.1f}g • F {:.1f}g • C {:.1f}g".format(
            totals.calories_kcal, totals.protein_g, totals.fat_g, totals.carbs_g
        ),
        f"Confidence: {confidence}",
    ]
    if source:
        lines.append(f"Source: {source}")
    if note:
        lines.append(f"Note: {note}")
    return "\n".join(lines)


def macros_sane(kcal: float, protein: float, fat: float, carbs: float, tol: float = 0.30) -> bool:
    """kcal should roughly equal 4P + 9F + 4C (Atwater)."""
    if kcal <= 0:
        return False
    expected = 4 * protein + 9 * fat + 4 * carbs
    if expected <= 0:
        return False
    return abs(kcal - expected) / max(kcal, expected) <= tol


async def fdc_resolve_item(parsed: ParsedItem) -> Tuple[Item, bool]:
    """
    Convert one parsed item into a final Item, preferring USDA FDC data.

    Returns (item, used_fdc). Falls back to the model's own estimate when FDC
    has no confident match or errors out (network, rate limit).
    """
    grams = parsed.grams if parsed.grams and parsed.grams > 0 else 100.0
    if not parsed.fdc_query.strip():
        # Parser decided this dish has no clean USDA generic equivalent.
        return _estimate_item(parsed, grams), False
    try:
        candidates = await fdc.search_foods(parsed.fdc_query)
        best = fdc.pick_best(candidates, parsed.fdc_query)
    except Exception:
        best = None

    if best is not None:
        k = grams / 100.0
        item = Item(
            name=parsed.name,
            grams=grams,
            calories_kcal=round(best.kcal_100g * k, 1),
            protein_g=round(best.protein_100g * k, 1),
            fat_g=round(best.fat_100g * k, 1),
            carbs_g=round(best.carbs_100g * k, 1),
            source_url=best.url,
        )
        # Guard against absurd matches (e.g. spice matched for a main dish):
        # if the model's own estimate is wildly different AND the model's
        # estimate is itself Atwater-consistent, trust the model.
        est = parsed.est_calories_kcal
        if est > 0 and item.calories_kcal > 0:
            ratio = max(est, item.calories_kcal) / max(1.0, min(est, item.calories_kcal))
            if ratio > 2.5 and macros_sane(
                parsed.est_calories_kcal, parsed.est_protein_g, parsed.est_fat_g, parsed.est_carbs_g
            ):
                return _estimate_item(parsed, grams), False
        return item, True

    return _estimate_item(parsed, grams), False


def _estimate_item(parsed: ParsedItem, grams: float) -> Item:
    return Item(
        name=parsed.name,
        grams=grams,
        calories_kcal=round(parsed.est_calories_kcal, 1),
        protein_g=round(parsed.est_protein_g, 1),
        fat_g=round(parsed.est_fat_g, 1),
        carbs_g=round(parsed.est_carbs_g, 1),
        source_url=None,
    )


async def fdc_resolve_all(parsed_items: List[ParsedItem]) -> Tuple[List[Item], int]:
    """Resolve every parsed item against FDC in parallel."""
    results = await asyncio.gather(*(fdc_resolve_item(p) for p in parsed_items))
    items = [r[0] for r in results]
    fdc_hits = sum(1 for r in results if r[1])
    return items, fdc_hits


def single_source_url(items: List[Item]) -> Optional[str]:
    urls = {i.source_url for i in items if i.source_url}
    if len(urls) == 1:
        return next(iter(urls))
    return None
