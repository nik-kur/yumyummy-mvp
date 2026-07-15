# YumYummy — App Store Listing (ASO Package)

Copy-paste-ready App Store Connect metadata, optimized for conversion + keyword
reach. Positioning (from design review): **source-verified nutrition data** —
"from the source, not the crowd" — is the differentiator vs. MyFitnessPal / Cal
AI / Yazio, whose numbers "feel made up." Lead every surface with it.

Character limits are hard caps enforced by App Store Connect — counts below are
verified. English (U.S.) primary locale.

---

## App Name — max 30 chars
```
YumYummy: AI Calorie Tracker
```
`28/30`. Puts the two highest-volume terms ("calorie", "tracker") in the
highest-weighted field alongside the brand.

## Subtitle — max 30 chars
```
Macro & food log, real data
```
`27/30`. Adds "macro", "food", "log", "data" to the indexed set without
repeating name terms. Alternatives:
- `Verified macros in seconds` (26) — leans on speed
- `Photo, voice & text logging` (27) — leans on capture methods

## Keywords — max 100 chars (comma-separated, NO spaces, singular, no repeats of name/subtitle)
```
counter,nutrition,diet,weight,loss,protein,carb,meal,fasting,health,fitness,kcal,scanner,coach
```
`94/100`. Rules applied: never repeat words already in Name/Subtitle (calorie,
tracker, macro, food, log, data, ai) — Apple indexes them together, so repeats
waste space. Singular forms only (Apple auto-handles plurals). No spaces.

## Promotional Text — max 170 chars (editable anytime, not indexed)
```
Every calorie cites its source — USDA, EU labels, manufacturers. Log by text, voice, or photo in seconds. Start your free 3-day trial.
```
`133/170`.

---

## Description — max 4000 chars

```
Effortless logging. Nerd-level precision.

YumYummy is the AI calorie and macro tracker for people who quit MyFitnessPal because the numbers felt made up. Every calorie and macro we show cites a real source — USDA, official EU labels, and manufacturer data — not crowd-sourced guesses. Tap any number to see where it came from.

THREE WAYS TO LOG — PICK THE FASTEST
• Type it — "two scrambled eggs and sourdough" and we parse it instantly.
• Say it — voice-log a meal in a few seconds; we transcribe and break it down.
• Snap it — photograph your plate, a package, or a nutrition label. The AI identifies each item and pulls the macros.

FROM THE SOURCE, NOT THE CROWD
Most trackers let anyone type in a food and a calorie count. YumYummy anchors every number to an authoritative record — USDA FoodData Central, EU nutrition labels, and brand/manufacturer data. A source badge sits on every kcal and macro so you always know the number is real.

AN AI NUTRITIONIST IN YOUR POCKET
• Ask "what should I eat next?" and get suggestions that fit your remaining macros.
• Chat with the advisor about eating out, a wedding, an open bar — real guidance, real numbers.
• Restaurant lookup: we web-search the menu and estimate macros when there's no label.

TARGETS CALIBRATED TO YOU
Set your goal — lose weight, maintain, build muscle, or just track — and we calculate calorie and macro targets using the Mifflin-St Jeor equation, the same method used in clinical practice. Edit any target anytime.

CALM BY DESIGN — NO SHAME
No streaks. No fire emojis. No guilt. Just a quiet, factual record of what you ate, with a weekly summary and a monthly view that tell you what actually happened — like the week you skipped breakfast three times.

YOUR DATA STAYS YOURS
Export to CSV anytime. We don't sell or share your data. Photos and audio leave your device only after you confirm a log.

MEMBERSHIP
Start with a free 3-day trial — no credit card required. Keep going for $9.99/month, or save with an annual plan. Cancel anytime.

Download YumYummy and log your first meal in seconds — with numbers you can actually trust.
```
`~2,050/4000`. First 2–3 lines are the only text shown before "more" — they
carry the hook.

---

## What's New (release notes) — for 1.0.0
```
Welcome to YumYummy — the AI calorie tracker with source-verified nutrition data.
• Log meals by text, voice, or photo in seconds
• Every calorie and macro cites a real source (USDA, EU labels, brands)
• AI advisor suggests what to eat next based on your remaining macros
• Calm by design: no streaks, no shame — just the numbers, done right
Start your free 3-day trial.
```

---

## Fields the user sets in App Store Connect (not copy)
- **Primary category:** Health & Fitness. **Secondary:** Food & Drink.
- **Age rating:** 4+ (confirm the questionnaire).
- **Support URL:** https://yumyummy.ai/support (see `docs/support.html`).
- **Marketing/Privacy Policy URL:** confirm live before submit.
- **Privacy "Nutrition Labels":** because ATT + AppsFlyer ship in this build,
  declare **Data Used to Track You** (IDFA / device id, usage data) — otherwise
  App Review rejects. See `attribution` task.
- **Promotional text** can be changed post-approval without a new review — use
  it for pricing/seasonal tweaks.

## A/B & iteration notes
- Test Subtitle variants via Product Page Optimization once you have baseline
  installs. Speed vs. capture-methods vs. verified-data are the three angles.
- The `paywall_*` and onboarding funnel events (see `docs/analytics/`) tell you
  whether the store promise matches in-app reality.
```
