# Release Runbook — Build → Submit → Phased Rollout

The single 1.0.x binary that carries attribution + sourcemaps + events. Backend
fixes deploy independently on `main` (no review). These steps need your Apple
credentials / 2FA, so you run them; commands are copy-paste ready.

## 0. Pre-flight (once)
- [ ] `cd mobile && npm install` (new native deps already in `package.json`:
      `expo-tracking-transparency`, `react-native-appsflyer`).
- [ ] Add build secrets as **EAS env**:
  - [ ] `SENTRY_AUTH_TOKEN` (scope `project:releases`) — for source map upload.
  - [ ] `EXPO_PUBLIC_APPSFLYER_DEV_KEY`, `EXPO_PUBLIC_APPSFLYER_APP_ID` (add to the
        `production`/`preview` env in `eas.json`, or as EAS env vars). If omitted,
        attribution is a safe no-op and the build still works.
  ```bash
  eas env:create --environment production --name SENTRY_AUTH_TOKEN --value <token> --visibility sensitive
  ```
- [ ] Adapty dashboard (server-to-server, no SDK change): enable
      **Adapty → AppsFlyer**, **Adapty → Meta Ads**, **Adapty → TikTok Events**;
      confirm the prod webhook URL/secret matches Render.
- [ ] Backend: confirm the infra checklist in `docs/infra/prelaunch-infra-check.md`
      (esp. `AUTH_EMAIL_DEBUG_RETURN_CODE` OFF, `INTERNAL_API_TOKEN` set, pooled DB).

## 1. Version
- Marketing version stays **1.0.0** (never publicly released yet). `eas.json`
  `production.autoIncrement: true` bumps the **build number** automatically, so a
  new binary is accepted even at the same marketing version.
- If you prefer a clean marketing bump, set `expo.version` in `app.json` to
  `1.0.1` — optional.

## 2. Sanity (local)
```bash
cd mobile
npx tsc --noEmit      # currently clean
npm run lint          # 0 errors (pre-existing warnings only)
```

## 3. Build
```bash
cd mobile
eas build --platform ios --profile production
```
- New native modules (AppsFlyer, ATT) mean this is a **full native build** — the
  config plugins in `app.json` regenerate the native project automatically.
- Watch the build log for the **Sentry source map upload** step (needs
  `SENTRY_AUTH_TOKEN`). "Uploaded ... source maps" = good; a warning about a
  missing token means crashes will stay minified — fix the secret and rebuild.

## 4. Submit to App Store Connect
```bash
eas submit --platform ios --profile production --latest
```
Submit creds (`ascApiKey*`, `appleTeamId`) are already in `eas.json`.

## 5. TestFlight smoke test (real device)
- [ ] Fresh install → ATT prompt appears (expected on first launch).
- [ ] Onboarding → **sign in with Apple** → lands on Today.
- [ ] Log a meal by **text**, **photo**, and **voice** → each shows "Logged." with
      a source badge → PostHog shows `meal_logged`.
- [ ] Advisor opens and replies → `advisor_opened`.
- [ ] Paywall: **sandbox purchase** → `access_status: active`; then **cancel** and
      **restore purchases** (Profile) both behave. Check Adapty + PostHog
      `subscription_*` / `paywall_purchase_success`.
- [ ] Sentry: trigger a test error, confirm the stack trace is **symbolicated**
      (readable), tagged with release `yumyummy@1.0.0`.

## 6. Store listing (App Store Connect)
- [ ] Metadata from `docs/aso/app-store-listing.md` (name, subtitle, keywords,
      description, promo text, What's New).
- [ ] Screenshots + App Preview per `docs/aso/screenshots-storyboard.md`.
- [ ] Categories, Support URL (`docs/support.html`), Privacy Policy URL.
- [ ] **Privacy "Nutrition Labels":** declare **Data Used to Track You** (IDFA,
      usage data) — required because ATT + AppsFlyer ship. Skipping this = reject.

## 7. Submit for review → Phased release
- [ ] Submit for review in App Store Connect.
- [ ] On approval, enable **Phased Release** (7-day gradual rollout) — insurance
      against a launch-day crash hitting everyone.

## 8. First 24–48h watch (before turning on paid ads)
- Sentry crash-free sessions ≥ 99.5%; no top-issue spike.
- Render logs: 5xx rate, `[RATELIMIT]` 429s, cost-cap hits.
- PostHog launch dashboard (`docs/analytics/launch-dashboard.md`): funnel +
  `meal_logged` activation.
- LLM spend vs the daily cap.
- **Only after stability:** turn on Meta/TikTok campaigns. Attribution
  (AppsFlyer + SKAdNetwork + Adapty S2S) is already in the binary, so conversions
  will attribute from day one of spend.
```
