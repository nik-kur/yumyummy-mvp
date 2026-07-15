# YumYummy iOS — Analytics Event Taxonomy

Source of truth for the events the iOS app sends to **PostHog** (via
`mobile/src/analytics/posthog.ts`). The older `Demos/yumyummy-tracking-taxonomy.html`
covers the Telegram bot / web funnel; this file covers the App Store app.

## Identity model

- App boots **anonymous** — PostHog assigns an anonymous `distinct_id`.
- On sign-in, `auth.tsx → loadProfile(method)` calls `identify(account_id)`. The
  RN SDK links (aliases) the anonymous onboarding `distinct_id` to `account_id`,
  so pre-login funnel events stitch to the user. No manual `alias()` needed.
- The same `account_id` is bound to **Adapty** (`identifyAdapty`), **AppsFlyer**
  (`setAttributionCustomerId`) and **Sentry** (`setUser`) — one id across tools.
- `signOut()` calls `reset()` so the next user starts on a fresh anonymous id.

## Core / activation events

| Event | Where | Key properties | Why it matters |
|---|---|---|---|
| `signin_success` | `state/auth.tsx` | `method` (`apple`/`google`/`email`/`demo`/`telegram`) | Account creation / login. Fires once per real sign-in, not on session restore. |
| `meal_logged` | `state/pendingMeals.tsx` | `source` (`text`/`photo`/`voice`), `origin` (`brand`/`generic`), `calories`, `items_count`, `day_meal_index` | **Primary activation metric.** Fires once per confirmed log (incl. timeout-reconciled photo logs). D0/D1 `meal_logged` = activation & retention. |
| `advisor_opened` | `app/advisor.tsx` | — | AI advisor engagement. |
| `ai_consent_granted` | `state/aiConsent.ts` | — | One-time 5.1.1/5.1.2 consent for third-party AI. |

## Monetization events (paywall)

| Event | Properties |
|---|---|
| `paywall_shown` | `variant`, … |
| `paywall_plan_selected` | `product` |
| `paywall_purchase_success` | `product`, `price`, `currency`, `mode` |
| `paywall_purchase_cancelled` | `product` |
| `paywall_purchase_pending` | `product` |
| `paywall_purchase_failed` | `product`, `error` |
| `paywall_retry_pressed` | — |
| `paywall_restore_started` / `_success` / `_empty` / `_failed` | — |
| `paywall_closed` | `dismissable` |
| `profile_restore_started` / `_success` / `_empty` / `_failed` | `error` (on fail) |
| `post_purchase_signin_success` | — |
| `postbuy_push_screen_viewed` / `postbuy_push_skipped` | — |

> Revenue truth comes server-side: Adapty webhooks are mirrored to PostHog in
> `app/api/adapty_webhook.py` as `subscription_*` events with `revenue`,
> `currency`, `plan`, `provider: adapty`. Client `paywall_purchase_success` is a
> funnel signal, not the billing ledger.

## Onboarding funnel

Every intro screen emits a pair — use these for step-by-step drop-off:

- `onboarding_screen_viewed` `{ screen }`
- `onboarding_screen_completed` `{ screen, … }`

Screens (in order): `S1_welcome`, `S2_goal`, `S3_why`, `S4_gender`, `S5_age`,
`S6_body`, `S7_activity`, `S8_pain_points`, `S9_problem`, `N1_target_pace`,
`N2_loader`, `N3_plan_reveal`, `S10_fix`, `S11_try_it`. Extra: `tryit_interacted { meal }`.

## Engagement / journey

| Event | Properties |
|---|---|
| `quest_info_opened` | `quest`, `day` |
| `quest_completed` | `quest`, `day`, `journey_day` |
| `journey_popup_shown` | `quest` |
| `journey_path_opened` | — |
| `week_tab_viewed` | — |
| `week1_report_viewed` | — |

## Launch funnel (build this in PostHog)

`install → onboarding_screen_viewed (S1) → onboarding_screen_completed (N3_plan_reveal) → signin_success → paywall_shown → paywall_purchase_success`

Cross-check with Adapty-mirrored `subscription_purchased` for paid conversion,
and with `meal_logged` (D0/D1) for activation. See the launch dashboard spec in
`docs/analytics/launch-dashboard.md`.
