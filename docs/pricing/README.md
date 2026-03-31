# Pricing Docs Index

- `PRICING_POLICY_2026.md` - full pricing policy, unit economics assumptions, 3 pricing matrices, launch recommendation.
- `TRIAL_FLOW_AND_COPY.md` - card-required trial mechanics, RU copy, reminders, cancellation flow.
- `AB_TEST_SCORECARD.md` - sequential A/B experiments, success metrics, guardrails, decision framework.
- `FAIR_USE_POLICY_WEBSITE_COPY.md` - ready-to-publish fair-use wording for ToS/FAQ on yumyummy.ai.

Recommended implementation order:

1. Finalize launch matrix (`Option B` by default).
2. Build billing + trial flow according to `TRIAL_FLOW_AND_COPY.md`.
3. Instrument events.
4. Start Experiment 1 from `AB_TEST_SCORECARD.md`.
