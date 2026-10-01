# YumYummy → Adapty flows: element mapping (written before authoring)

Source of truth: `../intro-spec.md`. Schema facts: `adapty-skills/skills/flow-generator/references/flow-schema.md`
(trap numbers below refer to it). Built by `build_flows.py` with `flowkit.py`; schemaVersion 12.

## Global decisions

| Native (RN) | Adapty JSON | Why / evidence |
|---|---|---|
| Screen shell: SafeArea all edges, bg `#F7F1E6`, 20px gutter | screen `props.safeArea: true`, `fill` = theme token `bg`, root `padding` 0/20/20/0 (+ bottom 16) | trap 20: screen bg must be a token |
| Colour tokens (§0.7) | `theme.colors` ids `bg, surface, surface_alt, ink, ink_muted, ink_faint, hairline, hairline_strong, terracotta, terracotta_text, terracotta_soft, success, error, info_blue, info_blue_soft, olive_soft, warning_soft, protein, fat, carbs, done_green, surplus_strip, white`; `dark` = same hex as `light` (app has no dark mode, so nothing flips) | trap 19 (#RRGGBB only), trap 21 (colour ids never reused as preset ids) |
| Fonts Fraunces / Inter / JetBrains Mono | typography presets named per intended face (`fr_h1` = "Fraunces 600 · H1 28/32", `in_body` = "Inter 400 · Body 16/26", `jb_overline` = "JetBrains Mono 500 · Overline 11"), **no `family`** → builder default system font | trap 8: a custom font needs a builder upload that mints the id; hand-writing `_meta.fonts` fabricates an asset. `_meta.fonts: []`. Upload + map is on CHECKLIST |
| lineHeight / letterSpacing | preset `settings.lineHeight` / `letterSpacing` (numbers) | flowkit `_typo`, real export carries them |
| Overline `textTransform: uppercase` | copy written in UPPERCASE | simplest, identical output |
| Button (brand) | `stack` 54h, radius 12, fill `terracotta`, centred `in_button` white text, tap interaction | "no button element" (Vocabulary) |
| CTA pinned bottom (`marginTop:auto`) | short screens: root `distribution: space-between`, `scrollable: false`, CTA last child; long screens (S1, S9, S10): `scrollable: true` + one `footer` with opaque `bg` fill | patterns.md footer rule 0 + spread for short screens |
| IntroHeader (back 32 circle + 4px progress track) | row stack: back `stack` 32x32 (surface fill, hairline border, radius 16, phosphor `CaretLeft` 18 ink) with `navigateBack`; progress = real `progress-bar` component referenced as `{"id": "pb_intro", "type": "global"}` | patterns.md "A progress bar" — never a static bar |
| Progress fractions step/12 (S2=1 … S10=9) | component `pb_intro`: `progress-bar` `multiple-segments`, template `segmented`, `oneSegmentPerScreen: false` (manual mode), **12 segments** gap 0 (`s01`…`s12`), each with a `progress-bar-loader` (track `terracotta_soft`, fill `terracotta`); screen `props.progressBar = {enabled: true, segment: "s0N"}` | schema `progressBar` doc: manual mode maps a screen to a segment customId; 12 segments reproduce `round(step/12*100)%` exactly (N1–N3 are app-side, segments 10–12 never become current) |
| Option cards (§0.8) | `selectable` members of a `single_choice` / `multi_choice` group; base border `hairline` 1.5, fill `surface`; `propsByState.selected` = border `terracotta` (same width) + fill `terracotta_soft` | patterns.md plan-card rules: style via state, never resize |
| Radio (22 circle) → `CircleCheck` when selected | 22x22 ring stack, border `hairline_strong` 1.5 → selected border `terracotta`; child phosphor `Check` 14 terracotta, `opacity 0` → selected `100` | catalog `checkbox-with-text` uses icon opacity 0→100 |
| Checkbox (22, radius 8) | ring radius 8; selected fill+border `terracotta`; child `Check` bold 14 white, opacity 0→100 | same |
| Auto-advance after tap (280 ms) | option `selectable` carries tap interaction `navigate` → next screen (no delay) | quiz fixture: selectables carry tap interactions |
| Analytics screen ids | screen `id` = `S1_welcome` … `S10_fix`, `PW_A_trial_all`; `caption` = same | trap 7b: `instanceId` = screen id; group `element_id` = `selectableGroups[].id`; `item_ids` = option `customId`; input `element_id` = `customId` |
| lucide icons | phosphor via `icons.py`: ChevronLeft→`CaretLeft`, TrendingDown→`TrendDown`, Utensils→`ForkKnife`, Dumbbell→`Barbell`, Eye→`Eye`, CircleCheck→`Check` in ring, Check→`Check`, ExternalLink→`ArrowSquareOut`, Camera→`Camera`, Mic→`Microphone`, Keyboard→`Keyboard`, LockOpen→`LockOpen`, Bell→`Bell`, Star→`Star` | trap 23 |
| Emoji | text | brief |
| Mascot / avatars | styled empty `image` (`flowkit.PLACEHOLDER`) at spec size, `objectFit: fit` | trap 5, media upload needs auth |

## Flow 1 `onb_main` (S1 → S10)

| Screen | Key elements → JSON | Contract ids |
|---|---|---|
| S1_welcome | no header; mascot image 64x64; H1 centred; sub `in_title` muted; **WelcomeDemo → `carousel`** of 3 slides (Photo / Voice / Text phase: mode pills row, stage 128 `stage_bg`, result card with 3px terracotta left edge approximated by a left border strip) with `scrollAnimation {delay 3300}` and no dots; footer: CTA `Get Started`, 3 trust chips, "Already have an account? Sign in" | Get Started: `custom request_att` → `navigate S2_goal`; Sign in: `custom sign_in` |
| S2_goal | eyebrow, H1; `single_choice` group `goal`: 4 cards (icon tile 44 + label + radio) | group `goal`; customIds `lose, maintain, gain, just_track`; tap → navigate `S3_why` |
| S3_why | eyebrow; per-goal stat / statcap / headline / body / citation via `switch` rich text on `goal.selectedOptionId` (default = lose); citation tap → `conditional` openUrl per goal; Continue | — |
| S4_gender | eyebrow, H1, body; two square cards (emoji 40 + label) in a `single_choice` group | group `gender`; `male`, `female`; tap → `S5_age` |
| S5_age | eyebrow, H1; `number-input` (integer, placeholder "30", big serif) centred; Continue | input customId `age` |
| S6_body | eyebrow, H1, body; segmented toggle = `single_choice` group `units` (`metric` default, `imperial`); HEIGHT/WEIGHT columns; metric pair visible when `units.selectedOptionId != imperial`, imperial trio when `== imperial`; Continue | `height_cm`, `weight_kg`, `height_ft`, `height_in`, `weight_lb`, group `units` |
| S7_activity | 4 cards emoji + label + sub + radio | group `activity`; `sedentary, light, moderate, active`; tap → `S8_pain_points` |
| S8_pain_points | `multi_choice` group, 5 rows emoji + label + checkbox; Continue always visible | group `pain_points`; `too_long, gave_up, accuracy, eating_out, first_time` |
| S9_problem | scrollable; eyebrow, H1, lead with bold span; static CICO card (surplus phase frozen); breaker; 2 trap cards; citation link (openUrl); footer CTA "So what's the answer?" | — |
| S10_fix | scrollable; header; fix card 1 (badge 1, proof meal card, macro pills), fix card 2 (chips); mascot 104 + "That's YumYummy"; footer CTA `Build my plan` | CTA: `custom quiz_done` |

## Flow 2 `pw_main` (one screen, `PW_A_trial_all`)

| Native | JSON |
|---|---|
| Top bar Restore (right) | text, tap `restorePurchases` |
| H1 headline | `fr_h1` centred |
| Hero card (label + goal_line / maintain_line) | card stack: eyebrow `YOUR PLAN — LOCKED IN` + one `fr_h2` text `<HERO_LINE/>`; the app resolves the line per goal and passes it as custom tag `HERO_LINE` (no fallback property exists, CHECKLIST #1) |
| Laurels | 3 pills, custom tags `<RATING/>` / `<USERS/>` |
| Testimonial quote (asked for in brief; NOT rendered by native A) | quote card, flagged |
| Trial timeline (4 steps) / paid timeline | two timeline stacks, conditional visibility on `plans.selectedProduct.is_free_trial` (== true / != true) |
| Plan cards yearly (BEST VALUE, default) / monthly / weekly | `product` elements in `product` group `plans`; main = `<uuid>.prod_price_per_week` + `/wk`; sub = trial variant (`offer_full_duration` free trial, then billed … at `prod_price`) / paid variant gated per product `is_free_trial`; radio ring + dot; rec tag opacity 0→100 on select |
| Above-CTA line | two texts gated on `is_free_trial` (`#16A34A`) |
| CTA | purchase `plans.selectedProduct`; label trial / non-trial variants |
| Legal disclosure + Restore · Terms · Privacy | texts; `restorePurchases`, `openUrl` (placeholder URLs) |
| Close button | none (hard paywall) |

Product ids/offer ids come from `products.json` (placeholders until `adapty products list`); the build
script derives `flowProductId`s, the screen registry and every price variable from it.
