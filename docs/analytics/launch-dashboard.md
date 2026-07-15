# YumYummy iOS — Launch Dashboard Spec (PostHog)

What to watch in the first 30 days. Build these as PostHog insights on one
dashboard ("YumYummy iOS — Launch"). Events are defined in
`ios-event-taxonomy.md`. Project: YumYummy (EU, id 175093).

> Note: event definitions appear in PostHog only after the first events are
> ingested from a TestFlight/App Store build. Create these insights once the
> first sessions land (or the day of launch), so the event names autocomplete.

## Tiles

### 1. Acquisition & activation funnel (Funnel insight)
Steps, ordered, 7-day conversion window:
1. `onboarding_screen_viewed` where `screen = S1_welcome`
2. `signin_success`
3. `meal_logged`  ← activation
4. `paywall_shown`
5. `paywall_purchase_success`

Breakdown by `signin_success.method` to see channel quality.

### 2. Paid conversion (Trends)
- Series A: `paywall_purchase_success` (count)
- Series B: Adapty-mirrored `subscription_purchased` (count) — cross-check
- Series C: `trial_started` (from Adapty mirror)
Display: line, daily. Formula tile: `subscription_purchased / trial_started` = trial→paid.

### 3. Revenue (Trends)
- `subscription_purchased` + `subscription_renewed`, **sum of `revenue`**, daily.
- Breakdown by `plan`.

### 4. Activation quality (Trends)
- `meal_logged` count, daily, breakdown by `source` (text/photo/voice).
- Secondary: breakdown by `origin` (brand/generic) — proves the source-checked value prop.

### 5. D1 / D7 retention (Retention insight)
- Cohortizing event: `signin_success`
- Returning event: `meal_logged`
- Period: Day, 14 days. This is the real "does it stick" chart.

### 6. Onboarding drop-off (Funnel)
Ordered `onboarding_screen_completed` for each screen S1→N3_plan_reveal. Find the leakiest step.

### 7. Paywall behaviour (Trends)
- `paywall_shown`, `paywall_plan_selected`, `paywall_purchase_success`,
  `paywall_purchase_cancelled`, `paywall_purchase_failed`, `paywall_closed`.
- Watch `paywall_purchase_failed` rate as an SDK-health canary.

### 8. Restore health (Trends)
- `paywall_restore_*` and `profile_restore_*`. A spike in `_failed`/`_empty`
  after launch often means an Adapty/entitlement misconfig.

## First-48h launch watch (manual, not a tile)
- Sentry: crash-free sessions ≥ 99.5%.
- Render logs: 5xx rate, `[RATELIMIT]` 429s, `[GUARDRAIL]` cost-cap hits.
- LLM spend vs `global_daily_llm_cost_cap_usd`.
- Only enable paid Meta/TikTok campaigns after 24–48h of stability.
