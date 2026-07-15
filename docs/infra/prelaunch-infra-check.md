# Pre-launch Infrastructure Check (Render + Neon)

Read-only audit run before App Store launch. Verified facts + the items only you
can action in the consoles.

## Render — verified OK

- **Production API:** `yumyummy-mvp-eu` (`srv-d7u65glckfvc73elunn0`), Frankfurt,
  web service. Matches the app's `EXPO_PUBLIC_API_BASE_URL`
  (`https://yumyummy-mvp-eu.onrender.com`).
- **Plan: `standard`** (not free) → no 15-min spin-down. Good for launch.
- Health check `/health`, predeploy `alembic upgrade head`, start
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Auto-deploy on `main`.
- **Bot worker:** `yumyummy-mvp-bot-eu` (`starter`), running.
- Old Oregon services (`yumyummy-mvp`, `-mcp`, `-rr80`) are **suspended** — fine,
  ignore. Consider deleting to avoid confusion later.
- Render MCP is reconnected (was failing during the first audit).

### You must verify in the Render dashboard (no API to read env values)
Open `yumyummy-mvp-eu` → Environment and confirm these are set on **prod**:
- [ ] `JWT_SECRET` (strong, unique to prod)
- [ ] `ADAPTY_API_KEY` / `ADAPTY_WEBHOOK_SECRET` (secret API key + webhook auth)
- [ ] `SENTRY_DSN` (backend)
- [ ] `BILLING_PAYWALL_ENABLED=true`
- [ ] `OPENAI_API_KEY`, `GEMINI_API_KEY`, `PERPLEXITY_API_KEY`
- [ ] `INTERNAL_API_TOKEN` (now required by the locked-down legacy `/ai/*` + CRUD routes)
- [ ] `AUTH_EMAIL_DEBUG_RETURN_CODE` — **must be off/false in prod** (else email
      login codes are returned in the API response = anyone can log in as anyone).
- [ ] New abuse-guard settings (optional overrides; safe defaults in code):
      `RATE_LIMIT_ENABLED=true`, `GLOBAL_DAILY_LLM_COST_CAP_USD` (default 200).
- [ ] `DATABASE_URL` uses the **pooled** Neon host — it must contain
      `-pooler` (e.g. `...-pooler.eu-central-1.aws.neon.tech`). The non-pooled
      host will exhaust connections under load.

## Neon — action needed

- **Single project `YumYummy-dev`** (`hidden-unit-26706255`), region
  `aws-eu-central-1`, Postgres 17. Primary branch is **`production`**
  (`br-wild-queen-aglbddb6`) — so this IS the prod DB, just misleadingly named.
- **History retention: 6 hours** (`history_retention_seconds: 21600`). PITR /
  restore window is very small for production.
- Primary branch is **not protected** (`protected: false`).
- Autoscaling 0.25–8 CU. An archived `migration-test-accounts-phase1` branch exists.

### You should action in the Neon console
- [ ] **Raise history retention** (7 days recommended) for a real restore window —
      needs a paid plan if not already. Settings → Storage / History retention.
- [ ] **Enable branch protection** on `production` (prevents accidental delete /
      forces safer resets).
- [ ] Optional: rename the project `YumYummy-dev` → `YumYummy` (or make a clean
      prod project) so "dev" isn't the thing serving real users. Low priority; the
      branch is correctly named `production`.
- [ ] Confirm `DATABASE_URL` on Render points at this project's **pooled** endpoint
      (see the Render checklist above).

## LLM provider billing (you)
- [ ] Set spend alerts/caps in OpenAI, Gemini (Google AI Studio / Vertex), and
      Perplexity dashboards, as a backstop above the app's
      `GLOBAL_DAILY_LLM_COST_CAP_USD` breaker.
