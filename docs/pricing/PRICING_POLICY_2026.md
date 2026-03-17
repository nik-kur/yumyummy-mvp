# YumYummy Bot Pricing Policy (USD, B2C)

## 1) Unit Economics Assumptions (Token-based COGS)

This project has no free plan. Access is only via paid subscription, with a card-required free trial that auto-converts unless canceled.

Baseline assumptions (can be tuned weekly after data appears):

- `avgTokensPerMessage`: 1200
- `heavyPercent`: 15%
- `heavyMultiplier`: 3.0 (heavy requests are ~3x costlier than standard)
- `blendedCostPer1MTokens`: $2.50
- `targetGrossMargin`:
  - Basic: 75%
  - Plus: 80%
  - Max: 72%

Core formulas:

- `effectiveTokensPerMessage = avgTokensPerMessage * (1 + heavyPercent * (heavyMultiplier - 1))`
- `costPerMessageUsd = effectiveTokensPerMessage / 1_000_000 * blendedCostPer1MTokens`
- `includedBudgetUsd = monthlyPriceUsd * (1 - targetGrossMargin)`
- `includedMessagesMonth = floor(includedBudgetUsd / costPerMessageUsd)`

With the baseline above:

- `effectiveTokensPerMessage = 1560`
- `costPerMessageUsd = $0.0039`

These assumptions drive all package limits and cap policy.

## 2) 3 Production-Ready Pricing Matrices

All options below follow `Basic / Plus / Max` (good/better/best), annual discount, and no free tier.

### Option A: Conversion-first

- Best when top priority is trial-to-paid conversion and early activation.
- Higher COGS risk; requires stricter heavy-request cap control.

| Plan | Monthly | Annual | Included messages/day | Intensive requests/day |
|---|---:|---:|---:|---:|
| Basic | $7.99 | $79.99 | 25 | 1 |
| Plus (default) | $17.99 | $179.99 | 55 | 4 |
| Max | $34.99 | $349.99 | 120 | 8 |

Trial policy for Option A:

- 7-day free trial
- Card required at start
- Auto-charge after trial unless canceled

### Option B: Balanced (recommended default)

- Best trade-off between conversion, ARPU, and cost control.
- Aligned with common AI pricing anchors around ~$20 mid-tier.

| Plan | Monthly | Annual | Included messages/day | Intensive requests/day |
|---|---:|---:|---:|---:|
| Basic | $9.99 | $99.99 | 22 | 1 |
| Plus (default) | $19.99 | $199.99 | 35 | 5 |
| Max | $39.99 | $399.99 | 95 | 12 |

Trial policy for Option B:

- 5-day free trial
- Card required at start
- Auto-charge after trial unless canceled

### Option C: Margin-first

- Best when CAC payback and COGS protection dominate.
- Lower conversion expected, higher ARPU expected.

| Plan | Monthly | Annual | Included messages/day | Intensive requests/day |
|---|---:|---:|---:|---:|
| Basic | $12.99 | $129.99 | 16 | 1 |
| Plus (default) | $24.99 | $249.99 | 28 | 3 |
| Max | $49.99 | $499.99 | 70 | 8 |

Trial policy for Option C:

- 3-day free trial
- Card required at start
- Auto-charge after trial unless canceled

## 3) Selected Go-live Policy

Start with **Option B (Balanced)**.

Why this is the best first launch for current constraints:

- Keeps a strong Plus anchor at `$19.99`.
- Leaves room for ARPU growth through annual selection and Max upgrades.
- Better token spend predictability than conversion-first.
- Simpler than adding top-ups at this stage (you selected subscription-only caps).

## 4) Trial Rules (No Free Plan)

Mandatory trial mechanics:

1. User must choose a plan before trial starts.
2. User must add payment method before trial starts.
3. User explicitly accepts auto-renew terms before trial starts.
4. Trial grants temporary access with stricter caps than paid plans.

Balanced trial limits (5-day trial):

- Basic trial: 12 messages/day, 1 intensive request/day
- Plus trial: 20 messages/day, 2 intensive requests/day
- Max trial: 35 messages/day, 4 intensive requests/day

Post-cap behavior:

- Standard messages over cap: hard stop for current day + upgrade CTA
- Intensive over cap: hard stop for intensive mode; standard mode remains if standard cap not reached

Reminder schedule:

- T-24h: "Trial ends tomorrow, then $X/month"
- T-3h: "Your trial ends in 3 hours"

Cancellation UX:

- One-tap cancel in settings
- Access remains until trial end timestamp
- No silent price changes during active trial

## 5) Paywall and Positioning Copy (short)

Plan card structure:

- Headline outcome (not technical limit details)
- 3 bullets max
- Price and billing cadence
- `Plus` marked as "Most popular"

Example value bullets:

- Basic: "Track food effortlessly every day"
- Plus: "Best balance for consistent progress"
- Max: "High-volume usage with priority access"

Checkout transparency text:

- "Today: $0.00"
- "Then: $19.99/month after 5-day trial"
- "Cancel anytime before renewal"

## 6) Experiment Program (2-3 Iterations)

### Iteration 1 (Price of Plus)

- Arms: `$14.99` vs `$19.99` vs `$24.99`
- Fixed: Basic and Max stay unchanged (relative positioning constant)
- Goal: maximize contribution margin per new subscriber

### Iteration 2 (Trial length)

- Arms: `3 days` vs `5 days` vs `7 days`
- Fixed: prices from winning arm in Iteration 1
- Goal: highest trial-to-paid with acceptable refund/churn profile

### Iteration 3 (Cap framing)

- Arms: `daily caps` vs `weekly caps` with equivalent monthly budget
- Goal: reduce cap frustration and improve D30 retention

Decision metrics (ranked):

1. `trial_to_paid_rate`
2. `gross_margin_after_30d`
3. `D30_retention_paid`
4. `net_revenue_per_trial_start`
5. `share_users_hitting_caps`

Guardrails:

- Pause an arm if gross margin falls below 65% for 3 consecutive days.
- Pause an arm if refund/dispute rate is materially above baseline.

## 7) Analytics Events Required for Billing Rollout

Track at minimum:

- `paywall_viewed` (plan cards shown)
- `plan_selected`
- `trial_started`
- `trial_reminder_sent`
- `trial_canceled`
- `trial_converted_to_paid`
- `renewal_success`
- `renewal_failed`
- `cap_reached_standard`
- `cap_reached_intensive`
- `upgrade_clicked`
- `plan_upgraded`
- `plan_downgraded`
- `churned`

Recommended event properties:

- `plan_id`
- `price_usd`
- `billing_period` (`monthly` or `annual`)
- `trial_days`
- `message_cap_daily`
- `intensive_cap_daily`
- `days_since_trial_start`

## 8) Weekly Operating Rhythm

Every week, review and decide:

1. Keep current price/test arm.
2. Raise/lower Plus by one step.
3. Tighten/relax intensive caps.
4. Move more traffic to annual checkout default if churn rises.

Single decision owner should publish a short weekly memo:

- What changed
- Why it changed
- Expected impact on conversion, ARPU, and COGS

## 9) Internal AI Cost Guardrails (Risk Hedge)

This section defines non-marketing, internal limits to protect margin and prevent outlier abuse.

- Guardrail scope: AI variable cost only (`model tokens + web search tool calls`).
- Billing-cycle limits:
  - Active paid user: `$10.00` per billing cycle
  - Trial user: `$2.00` per trial cycle
- Enforcement behavior:
  - If limit is reached, requests are blocked for the rest of the cycle.
  - User sees a support escalation message ("contact support").
  - No silent model downgrade should be applied without user-visible notice.
- Communication policy:
  - Public-facing pages should describe this as "fair use limits".
  - Do not promise "unlimited" usage in paywall, ads, or landing pages.
  - Exact internal USD thresholds are operational and may change.
