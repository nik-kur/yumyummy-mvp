# Adapty flows (SDK v4 Flow & Paywall Builder)

Source of truth for the two flows the app fetches (see `mobile/src/billing/flowBridge.ts` for the app contract):

- `onb_main` — onboarding quiz S1–S10 (flow a8b7ec17-d855-48ab-9b31-efdc56f19663, placement `onb_main`)
- `pw_main` — placement for the builder paywall. Flows: `pw_main` (variant A trial-all, 482e6945-…), `pw_single_monthly` (be988b5b-…) and `pw_single_weekly` (588d6ac7-…), replicas of the live code paywalls; the A/B test on this placement is created in the dashboard when the builder paywall is switched on.
- `pw_after_cancel` — one-screen offer (weekly 2.99 with 3-day trial) the app shows once after the customer dismisses the App Store sheet (flow 95dab450-…, placement 0ca14826-…).

Switches (no release needed): a flow whose remote config is `{"use_native": true}` is ignored by the app —
onboarding falls back to the native quiz, the paywall to the code-rendered `main` placement, the after-cancel
offer is simply not shown. Remove the key (or set it to false) in the builder's Remote Config tab and publish to switch on.
Current state: all three OFF (native onboarding, legacy paywall + its A/B test, no offer).

Files:
- `build_flows.py` + `products.json` — generator (needs `flowkit.py` from github.com/adaptyteam/adapty-skills, skills/flow-generator/references).
- `*.published.json` — the envelope Adapty returned after the last `flows config update` (config + fonts mapping), 2026-09-30.
- `CHECKLIST.md` — online steps (CLI commands) and the list of deviations from the native screens.
- `NOTES.md` — element mapping decisions. `intro-spec.md` — verbatim spec of the native screens the flows replicate.
- `media/*.json` — Adapty media upload records (mascots), keep: they hold the preview blobs the config binds.

Rules: any edit made in the builder must be fetched with `adapty flows config get` before regenerating from the script,
or the script overwrites it. Reload the builder after a CLI write. Fonts are app-wide in Adapty and must also be
bundled in the app (`mobile/assets/fonts`, expo-font plugin) under the same PostScript names.
