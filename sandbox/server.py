#!/usr/bin/env python3
"""
YumYummy Agent v2 — локальная песочница.

Запуск (из корня рабочей копии exp/agent-v2):
    .venv/bin/python sandbox/server.py
Затем открыть http://127.0.0.1:8787 в браузере.

Ничего не деплоится и не трогает прод: сервер живёт только на этом Mac,
ходит напрямую в Gemini/Perplexity/OpenAI/USDA по ключам из .env.
"""
import asyncio
import base64
import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(REPO_ROOT / ".env")

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

app = FastAPI(title="YumYummy Agent v2 sandbox")

VARIANT_LABELS = {
    "v2g": "V2 · Gemini 3 Flash (рекомендованный)",
    "v2s": "V2 · Perplexity Sonar (фолбэк)",
    "v2o": "V2 · OpenAI gpt-5-mini (контроль)",
}

INTENT_LABELS = [
    ("auto", "Авто — как в приложении (сам понимает)"),
    ("log_meal", "Обычная еда (текст, без бренда)"),
    ("eatout", "Ресторан / кафе"),
    ("product", "Брендовый продукт"),
    ("barcode", "Штрих-код (цифры)"),
    ("food_advice", "Совет: что поесть"),
    ("photo_meal", "Фото еды"),
]

INTENT_RU = {
    "log_meal": "обычная еда",
    "eatout": "ресторан/кафе",
    "product": "брендовый продукт",
    "barcode": "штрих-код",
    "food_advice": "совет",
    "photo_meal": "фото еды",
    "help": "справка",
    "unknown": "не про еду",
}


class RunRequest(BaseModel):
    intent: str
    text: str = ""
    variant: str = "v2g"
    image_b64: str = ""  # data-url или чистый base64 (jpeg/png)
    compare_v1: bool = False


def _decode_image(image_b64: str) -> Optional[bytes]:
    if not image_b64:
        return None
    payload = image_b64.split(",", 1)[-1]
    return base64.b64decode(payload)


async def _run_v2(req: RunRequest) -> dict:
    from app.agent_v2 import engine

    image = _decode_image(req.image_b64)
    tmp_path = None
    if image is not None:
        tmp_path = REPO_ROOT / "sandbox" / ".last_upload.jpg"
        tmp_path.write_bytes(image)

    t0 = time.perf_counter()
    res = await engine.run(
        req.intent,
        req.text,
        variant=req.variant,
        image_path=str(tmp_path) if tmp_path else None,
    )
    latency_s = round(time.perf_counter() - t0, 2)
    d = res.model_dump()
    return {
        "engine": VARIANT_LABELS.get(req.variant, req.variant),
        "ok": res.error is None,
        "error": res.error,
        "routed": INTENT_RU.get(res.intent, res.intent) if req.intent == "auto" else None,
        "latency_s": latency_s,
        "cost_usd": res.total_cost_usd,
        "confidence": res.confidence,
        "totals": d["totals"],
        "items": d["items"],
        "source_url": res.source_url,
        "message_text": res.message_text,
    }


async def _run_v1(req: RunRequest) -> dict:
    from app.agent_workflow.workflow import run_text

    image_url = None
    if req.image_b64:
        payload = req.image_b64.split(",", 1)[-1]
        image_url = f"data:image/jpeg;base64,{payload}"

    force = None if req.intent in ("photo_meal", "auto") else req.intent
    t0 = time.perf_counter()
    try:
        res = await run_text(
            text=req.text,
            telegram_id="sandbox",
            image_url=image_url,
            force_intent=force,
        )
        return {
            "engine": "V1 · текущий прод",
            "ok": True,
            "error": None,
            "latency_s": round(time.perf_counter() - t0, 2),
            "cost_usd": None,
            "confidence": res.get("confidence"),
            "totals": res.get("totals") or {},
            "items": res.get("items") or [],
            "source_url": res.get("source_url"),
            "message_text": res.get("message_text") or "",
        }
    except Exception as e:  # noqa: BLE001 — показываем ошибку в UI
        return {
            "engine": "V1 · текущий прод",
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "latency_s": round(time.perf_counter() - t0, 2),
            "cost_usd": None,
            "confidence": None,
            "totals": {},
            "items": [],
            "source_url": None,
            "message_text": "",
        }


@app.post("/api/run")
async def api_run(req: RunRequest) -> JSONResponse:
    tasks = [_run_v2(req)]
    if req.compare_v1:
        tasks.append(_run_v1(req))
    results = await asyncio.gather(*tasks)
    return JSONResponse({"results": list(results)})


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML_PAGE


HTML_PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>YumYummy · песочница Agent v2</title>
<style>
  :root {
    --bg: #f7f5f0; --card: #ffffff; --ink: #26221c; --muted: #8a8377;
    --accent: #e2643b; --accent-soft: #fdeee7; --ok: #2e7d4f; --warn: #b3541e;
    --border: #e8e3da; --radius: 16px;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 15px/1.5 -apple-system, "SF Pro Text", Segoe UI, Roboto, sans-serif;
  }
  .wrap { max-width: 880px; margin: 0 auto; padding: 28px 20px 80px; }
  h1 { font-size: 22px; margin: 0 0 4px; }
  .sub { color: var(--muted); margin-bottom: 24px; font-size: 13.5px; }
  .panel {
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 18px; margin-bottom: 18px;
  }
  label { font-size: 12.5px; color: var(--muted); display: block; margin-bottom: 4px; }
  select, textarea {
    width: 100%; border: 1px solid var(--border); border-radius: 10px;
    padding: 10px 12px; font: inherit; background: #fcfbf8; color: var(--ink);
  }
  textarea { resize: vertical; min-height: 64px; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; }
  .row > div { flex: 1; min-width: 220px; }
  .controls { display: flex; align-items: center; gap: 14px; margin-top: 14px; flex-wrap: wrap; }
  button.go {
    background: var(--accent); color: #fff; border: 0; border-radius: 12px;
    padding: 12px 26px; font: 600 15px/1 inherit; cursor: pointer;
  }
  button.go:disabled { opacity: .5; cursor: default; }
  .hint { font-size: 12.5px; color: var(--muted); }
  .chk { display: flex; align-items: center; gap: 7px; font-size: 13.5px; user-select: none; }
  input[type=file] { font-size: 13px; }
  .thumb { max-height: 90px; border-radius: 10px; border: 1px solid var(--border); display: none; }
  .results { display: grid; gap: 14px; grid-template-columns: 1fr; }
  .results.two { grid-template-columns: 1fr 1fr; }
  @media (max-width: 720px) { .results.two { grid-template-columns: 1fr; } }
  .res {
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--radius); padding: 16px;
  }
  .res h3 { margin: 0 0 10px; font-size: 14px; display: flex; justify-content: space-between; align-items: center; gap: 8px; }
  .badges { display: flex; gap: 6px; flex-wrap: wrap; }
  .badge {
    font-size: 11.5px; font-weight: 600; border-radius: 99px; padding: 3px 9px;
    background: var(--accent-soft); color: var(--warn); white-space: nowrap;
  }
  .badge.lat { background: #e9f4ee; color: var(--ok); }
  .badge.conf-HIGH { background: #e9f4ee; color: var(--ok); }
  .badge.conf-ESTIMATE { background: #fdf3e0; color: #9a6b12; }
  .totals { font-size: 20px; font-weight: 700; margin: 4px 0 2px; }
  .macros { color: var(--muted); font-size: 13px; margin-bottom: 10px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 6px 0; }
  td, th { text-align: left; padding: 5px 6px; border-top: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 500; border-top: 0; }
  td.num, th.num { text-align: right; }
  a.src { color: var(--accent); word-break: break-all; font-size: 12.5px; }
  .msg { white-space: pre-wrap; font-size: 13px; color: #4c463d; background: #faf8f4; border-radius: 10px; padding: 10px 12px; margin-top: 10px; }
  .err { color: #b3261e; font-size: 13px; white-space: pre-wrap; }
  .spin { display: none; color: var(--muted); font-size: 13.5px; }
  .cost { color: var(--muted); font-size: 12px; margin-top: 8px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>YumYummy · песочница нового движка</h1>
  <div class="sub">Работает только на этом Mac. Прод и приложение не затрагиваются.</div>

  <div class="panel">
    <div class="row">
      <div>
        <label>Что проверяем</label>
        <select id="intent">
          <option value="auto" selected>Авто — как в приложении (сам понимает)</option>
          <option value="log_meal">Обычная еда (текст, без бренда)</option>
          <option value="eatout">Ресторан / кафе</option>
          <option value="product">Брендовый продукт</option>
          <option value="barcode">Штрих-код (цифры)</option>
          <option value="food_advice">Совет: что поесть</option>
          <option value="photo_meal">Фото еды</option>
        </select>
      </div>
      <div>
        <label>Движок</label>
        <select id="variant">
          <option value="v2g">V2 · Gemini 3 Flash (рекомендованный)</option>
          <option value="v2s">V2 · Perplexity Sonar (фолбэк)</option>
          <option value="v2o">V2 · OpenAI gpt-5-mini (контроль)</option>
        </select>
      </div>
    </div>
    <div style="margin-top:12px">
      <label>Запрос (текст, каптион к фото или штрих-код)</label>
      <textarea id="text" placeholder="Например: 2 яйца и тост с маслом · Биг Мак кбжу · 4650322700346"></textarea>
    </div>
    <div class="controls">
      <input type="file" id="photo" accept="image/*">
      <img id="thumb" class="thumb" alt="">
      <label class="chk"><input type="checkbox" id="cmp"> сравнить с продом (v1, медленно)</label>
    </div>
    <div class="controls">
      <button class="go" id="go">Спросить</button>
      <span class="spin" id="spin">Считаю…</span>
    </div>
  </div>

  <div class="results" id="results"></div>
</div>

<script>
const $ = (id) => document.getElementById(id);
let imageB64 = "";

$("photo").addEventListener("change", () => {
  const f = $("photo").files[0];
  if (!f) { imageB64 = ""; $("thumb").style.display = "none"; return; }
  const r = new FileReader();
  r.onload = () => {
    imageB64 = r.result;
    $("thumb").src = r.result;
    $("thumb").style.display = "block";
    if ($("intent").value !== "auto") $("intent").value = "photo_meal";
  };
  r.readAsDataURL(f);
});

$("text").addEventListener("input", () => {
  const t = $("text").value.trim();
  if ($("intent").value !== "auto" && /^\\d{8,14}$/.test(t)) $("intent").value = "barcode";
});

function fmt(n) { return (n === null || n === undefined) ? "—" : Math.round(n * 10) / 10; }

function card(r) {
  const t = r.totals || {};
  const items = (r.items || []).map(i => `
    <tr><td>${i.name || "—"}</td>
        <td class="num">${fmt(i.grams)} г</td>
        <td class="num">${fmt(i.calories_kcal)} ккал</td>
        <td class="num">${i.source_url ? `<a class="src" href="${i.source_url}" target="_blank">источник</a>` : ""}</td></tr>`).join("");
  return `<div class="res">
    <h3><span>${r.engine}</span>
      <span class="badges">
        ${r.routed ? `<span class="badge lat">понял: ${r.routed}</span>` : ""}
        <span class="badge lat">${r.latency_s} c</span>
        ${r.confidence ? `<span class="badge conf-${r.confidence}">${r.confidence}</span>` : ""}
      </span></h3>
    ${r.ok ? `
      <div class="totals">${fmt(t.calories_kcal)} ккал</div>
      <div class="macros">Б ${fmt(t.protein_g)} · Ж ${fmt(t.fat_g)} · У ${fmt(t.carbs_g)}</div>
      ${items ? `<table><tr><th>Позиция</th><th class="num">Порция</th><th class="num">Ккал</th><th></th></tr>${items}</table>` : ""}
      ${r.source_url ? `<a class="src" href="${r.source_url}" target="_blank">${r.source_url}</a>` : ""}
      ${r.message_text ? `<div class="msg">${r.message_text}</div>` : ""}
      ${r.cost_usd != null ? `<div class="cost">стоимость запроса ≈ $${r.cost_usd}</div>` : ""}
    ` : `<div class="err">${r.error || "ошибка"}</div>`}
  </div>`;
}

$("go").addEventListener("click", async () => {
  $("go").disabled = true; $("spin").style.display = "inline";
  $("results").innerHTML = "";
  try {
    const body = {
      intent: $("intent").value,
      text: $("text").value.trim(),
      variant: $("variant").value,
      image_b64: imageB64,
      compare_v1: $("cmp").checked,
    };
    const resp = await fetch("/api/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    const rs = data.results || [];
    $("results").className = "results" + (rs.length > 1 ? " two" : "");
    $("results").innerHTML = rs.map(card).join("");
  } catch (e) {
    $("results").innerHTML = `<div class="res"><div class="err">${e}</div></div>`;
  } finally {
    $("go").disabled = false; $("spin").style.display = "none";
  }
});
</script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn

    print("Песочница: http://127.0.0.1:8787  (Ctrl+C — остановить)")
    uvicorn.run(app, host="127.0.0.1", port=8787, log_level="warning")
