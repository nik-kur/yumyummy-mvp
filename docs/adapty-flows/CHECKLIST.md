# Online checklist — `onb_main` + `pw_main`

Everything below needs a working Adapty developer token (current one is expired → 403). Nothing here
has been run. Offline state: both configs built by `build_flows.py`, `verify-config.py` OK, schema
check clean apart from the documented false positives, all 11 screens rendered locally
(`previews/montage_onb_main.png`, `previews/montage_pw_main.png`).

```bash
SP=/private/tmp/claude-501/-Users-nikita-Documents-YumYummy-yumyummy-mvp/2146d804-62ee-4e07-81a9-76a197534119/scratchpad
ADAPTY=$SP/cli/node_modules/.bin/adapty          # v0.8.9
cd $SP/flows
```

## 0. Auth + app
```bash
$ADAPTY auth login                 # browser, user completes it
$ADAPTY auth whoami
$ADAPTY apps list --json           # -> APP=<YumYummy app UUID>
```

## 1. Products → substitute placeholders, rebuild (paywall only)
```bash
$ADAPTY products list --app $APP --page-size 100 --json > products.live.json
$ADAPTY products get <uuid> --app $APP --json     # for each of the 3, to read the offers
```
Match on store id: `ai.yumyummy.app.yearly` (annual), `ai.yumyummy.app.monthly` (monthly),
`ai.yumyummy.app.weekly_upd` (weekly). Edit **`products.json`** (not the JSON config):
- `product_id` ← Adapty product UUID (replaces `PRODUCT_UUID_YEARLY` / `_MONTHLY` / `_WEEKLY`)
- `offer_id` ← id of the 3-day free-trial offer on that product (replaces `OFFER_ID_TRIAL_*`).
  If the trial is not modelled as an Adapty offer, set `null` AND remove the
  `offer_full_duration` spans from the trial sub-lines in `build_flows.py` (`plan()` → `sub_t`):
  per the Adapty docs `offer_*` variables need a product bound with an offer or the flow does not publish.

Then `python3 build_flows.py`. That one re-run rewrites every place the ids live:
`_meta.screens.PW_A_trial_all.products[]` (ids + re-derived `flowProductId`s), `screens[0].products`
registry, each `product` element `props.product.{id,offerId}`, every price variable
(`<uuid>.prod_price_per_week`, `<uuid>.prod_price`, `<uuid>.offer_full_duration` + `productRef`),
and the per-card `<uuid>.is_free_trial` visibility conditions. Re-run
`python3 ../adapty-skills/skills/flow-generator/references/verify-config.py pw_main.json`.
Period check (hard stop if wrong): all cards use `prod_price_per_week` (shorter-or-equal to every
period → renders) and `prod_price` (own period).

## 2. Create the two flows (new rows, always `draft`)
```bash
$ADAPTY flows create --app $APP --name "onb_main" --json   # -> ONB_FLOW
$ADAPTY flows create --app $APP --name "pw_main"  --json   # -> PW_FLOW
```

## 3. Publish gate (validate) — read `valid`, not the exit code
```bash
$ADAPTY flows config validate $ONB_FLOW --app $APP --config-file onb_main.json --json
$ADAPTY flows config validate $PW_FLOW  --app $APP --config-file pw_main.json  --json
# or all three gates at once:
../adapty-skills/skills/flow-generator/references/gates.sh onb_main.json $APP $ONB_FLOW
```
One fatal per run — fix, rebuild, repeat until `valid: true`. Things most likely to surface:
the nested `global` progress-bar reference inside the header row, the `productRef` on
`plans.selectedProduct.is_free_trial` conditions, the `<TAG/>` tokens in text, the cross-screen `goal.selectedOptionId` switch on S3.

## 4. Media upload (images only; keep each `--json` file — it is the only copy of `preview_base64`)
Crop transparent margins first (media.md), upload once each:
```bash
mkdir -p media
python3 -c "from PIL import Image; im=Image.open('/Users/nikita/Documents/YumYummy/yumyummy-mvp/mobile/assets/mascot/mood_stellar_t.png').convert('RGBA'); im.crop(im.getchannel('A').getbbox()).save('media/mood_stellar_t.png')"
python3 -c "from PIL import Image; im=Image.open('/Users/nikita/Documents/YumYummy/yumyummy-mvp/mobile/assets/mascot/mood_great_t.png').convert('RGBA'); im.crop(im.getchannel('A').getbbox()).save('media/mood_great_t.png')"
$ADAPTY flows media upload media/mood_stellar_t.png --app $APP --json > media/mood_stellar_t.json
$ADAPTY flows media upload media/mood_great_t.png   --app $APP --json > media/mood_great_t.json
```
| # | asset (path) | where | box |
|---|---|---|---|
| 1 | `mobile/assets/mascot/mood_stellar_t.png` (480×480, transparent) | S1_welcome, element `el_s01_001I` ("Mascot mood_stellar_t.png 64x64") | 64×64, `objectFit: fit` |
| 2 | `mobile/assets/mascot/mood_great_t.png` (480×480, transparent) | S10_fix, element `el_s10_038I` ("Mascot … 104x104") | 104×104, `objectFit: fit` |
| – | `mobile/assets/avatars/{maria,denis,sara,james,priya,tom,elena,chris,sophie,alex}.jpg` (128×128) | **not used** by these two flows: they belong to N3 plan-reveal testimonials, which is app-side (after `quiz_done`). Upload only if N3 is later moved into a flow (circle, `borderRadius` = half, `cover`). | — |

Bind: in `build_flows.py` replace `fk.image(fk.PLACEHOLDER, …)` with
`fk.image(url, media_id=id, preview=preview_base64, fit='fit', fixed_w=…, fixed_h=…)` reading the
values from `media/*.json`, rebuild, re-verify. (Or upload in the builder on the already-sized element.)

## 5. Write the configs (new flows have no config → no approval gate, no lock token)
```bash
$ADAPTY flows config update $ONB_FLOW --app $APP --config-file onb_main.json --json > onb_main.working.json
$ADAPTY flows config update $PW_FLOW  --app $APP --config-file pw_main.json  --json > pw_main.working.json
```
Any later write: `UA=$($ADAPTY flows config get $FLOW --app $APP --json | jq -r .updated_at)` then
`--expected-updated-at "$UA"`, and patch the fetched config rather than re-running the build script
once anyone has edited in the builder (merge.md).

## 6. Builder-only steps (https://app.adapty.io/flows/<FLOW_ID>/builder)
- **Fonts** (cannot be uploaded by CLI): upload Fraunces SemiBold 600, Fraunces Bold 700, Inter Regular
  400, Inter Medium 500, Inter SemiBold 600, JetBrains Mono Medium 500 (files: `mobile/node_modules/@expo-google-fonts/{fraunces,inter,jetbrains-mono}/…ttf`).
  Then set the family on each typography preset by its name prefix: `fr_*` → Fraunces (600, or 700 for
  `fr_stat`, `fr_num34`, `fr_label28`), `in_*` → Inter (weight per preset), `jb_*` → JetBrains Mono 500.
  Until then everything renders in the system font. Fonts must also ship in the app bundle.
- Custom tags: confirm the builder recognises `<TAG/>` in the hero/laurel texts (it auto-suggests after `<`); add a fallback there if the builder UI offers one.
- Device preview both flows in the Adapty app (link via `mobile-preview.mjs` after the write).

## 7. Device checks the local render could not do
- Progress bar: S2 shows 1/12 filled … S10 shows 9/12 (12 manual segments); current segment animates.
- Tap on a goal/gender/activity card selects it AND navigates; the `flow_user_input` event carries
  `element_id` = `goal`/`gender`/`activity`/`pain_points`/`units` and `item_ids` = option customIds;
  number inputs report `age`, `height_cm`, `weight_kg` (or `height_ft`, `height_in`, `weight_lb`).
- S3 copy switches with the answer on S2 (cross-screen `goal.selectedOptionId`); citation opens the right PubMed URL.
- S6 Imperial tab swaps the input pairs; selected segment turns ink with light label.
- S1 "Get Started" fires `request_att` then navigates; "Sign in" fires `sign_in`; S10 fires `quiz_done`.
- S1 demo carousel auto-advances every 3.3 s (`scrollAnimation`) and does not show a neighbour peek on
  a 375pt device (slide is fixed 310pt).
- Paywall: `<HERO_LINE/>`, `<RATING/>`, `<USERS/>` are replaced by the app's `customTags` values; prices resolve, yearly preselected, rec tag appears only on the selected card, trial vs
  non-trial copy flips on `is_free_trial` (preview only ever shows the non-trial branch).
- Fonts under 14pt (eyebrows 11, captions 12) are reported to render at 14 on device (flow-schema.md).
- `statusBarTheme: light` gives dark status-bar text on the paper background.

## 8. Publish (after the user says yes)
```bash
$ADAPTY flows publish $ONB_FLOW --app $APP --yes --json ; $ADAPTY flows get $ONB_FLOW --app $APP --json   # poll until published
$ADAPTY flows publish $PW_FLOW  --app $APP --yes --json ; $ADAPTY flows get $PW_FLOW  --app $APP --json
```
(`publishing` ≠ published; on `publication_failed` read `transform_error` from `flows config get`.)

## 9. Placements (irreversible developer ids — confirm first; ids must be free across ALL placements)
```bash
$ADAPTY placements list --app $APP --page-size 100 --json     # `main` is the existing PAYWALL placement — do not reuse
$ADAPTY placements create --app $APP --title "Onboarding main (flow)" --developer-id "onb_main" \
  --audiences '[{"content_type":"flow","flow_id":"'"$ONB_FLOW"'","segment_ids":[],"priority":0}]'
$ADAPTY placements create --app $APP --title "Paywall main (flow)" --developer-id "pw_main" \
  --audiences '[{"content_type":"flow","flow_id":"'"$PW_FLOW"'","segment_ids":[],"priority":0}]'
```
Placement link: `https://app.adapty.io/placements/flows/<PLACEMENT_UUID>` (UUID, not developer id).

---

## Deviations from the spec (what the builder cannot express, or what was chosen)

1. **Custom tags**: texts use Adapty's documented custom-tag syntax `<HERO_LINE/>`, `<RATING/>`,
   `<USERS/>` (case-sensitive; source:
   https://adapty.io/docs/custom-tags-in-paywall-builder). The app passes
   `createFlowView(flow, { customTags: { HERO_LINE: '72 kg by Dec 14', RATING: '4.9', USERS: '12,000' } })`
   (no brackets; react-native-adapty 4.2.1 has `customTags`). `HERO_LINE` is resolved app-side per goal
   ("<target> kg by <date>" for lose/gain, "Your zone: <kcal> kcal" for maintain/just_track), which
   replaces the old goal_line / maintain_line pair. TARGET_WEIGHT / TARGET_DATE / DAILY_KCAL / GOAL are
   no longer used in any text.
   **No fallback property exists** in the flow schema, the component catalog or any fixture (grep
   `fallback` = 0 hits; `<TAG/>` inside text = 0 hits in real exports), so there is no per-text
   fallback line: the app MUST pass every tag, or the raw token shows. Unverified until device preview
   that the flow renderer substitutes `<TAG/>` inside rich-text spans (legacy-builder doc) — device check,
   step 7. The `variables[]` entries in `pw_main` (incl. HERO_LINE) stay declared-but-unreferenced (builder panel only).
2. **Hero line choice by goal**: done app-side — one `<HERO_LINE/>` text; the hidden maintain line and
   its visibility were removed. Native hides the whole hero card when no line resolves; here the card
   always shows, so the app must always pass `HERO_LINE`.
3. **Age stepper (±, clamp 14–99)** → `number-input` `age` (integer, placeholder "30"); no arithmetic in
   actions, no min/max. App must clamp and fall back to 30 when empty.
4. **Wheel pickers (height/weight)** → `number-input`s with unit labels; no clamping (120–230 cm,
   30–250 kg) — app-side. Placeholders 175 / 75 (imperial 5 / 9 / 165) are not values: an untouched
   field sends nothing.
5. **Imperial toggle**: implemented as `single_choice` group `units` + conditional visibility; imperial
   height is two fields (`height_ft`, `height_in`) instead of one 48–90 in wheel; no conversion
   between pairs on toggle (values do not carry over).
6. **Continue buttons** are always enabled (no disable mechanism; native also never blocks).
7. **Auto-advance** fires immediately on tap (native waits 280 ms with the highlight shown).
8. **WelcomeDemo** → 3-slide auto-scrolling `carousel` (one static frame per phase); no scan line,
   corner brackets, waveform/typing/cursor animation, result fade-in; mascot bounce/tilt animations dropped.
9. **S9 CICO chart**: static surplus phase only (no bar-height flip, no deficit phase, no fades).
10. **S3 citation** opens in the external browser (`openUrl external`); S9 link same.
11. **Icons**: lucide → phosphor (CaretLeft, TrendDown, ForkKnife, Barbell, Eye, Check, ArrowSquareOut,
    Camera, Microphone, Keyboard, LockOpen, Bell, Star). CircleCheck rebuilt as a ring + Check.
12. **Fonts**: system font until uploads (step 6). Overlines written in uppercase literally.
13. **Hairline widths**: RN `hairlineWidth` borders authored as 0.5.
14. **ATT**: no request-permission action exists in the schema, catalog or fixtures → `custom` action
    `request_att` before the navigate (SDK has `onRequestPermission`, but nothing produces it from config).
15. **Paywall**: testimonial quote card added because the brief asked for it — native Variant A does
    NOT render `social.quote`; delete it for a pixel-faithful A. Recommendation tag uses opacity (space
    reserved on every card) instead of appearing only on the selected card (avoids reflow on tap);
    rec tag text is always the `default` goal copy (`✦ Recommended for building the habit`).
    CTA stays inside the scroll (as native); no "Processing…" state, no store-unavailable notice / Retry,
    no fallback display prices (builder handles loading). Terms/Privacy URLs are placeholders
    `https://yumyummy.ai/terms` / `/privacy` (the app uses `/terms.html` / `/privacy.html`).
    Trial/no-trial variants (timeline, sub-lines, above-CTA, CTA label, disclosure) are gated on
    `is_free_trial`; the local preview only shows the no-trial branch.
16. **Progress bar**: 12 manual segments instead of one continuous animated width; fill should be
    identical (step/12) but segment edges may show at gap 0 — device check.
17. **Analytics**: native PostHog `onboarding_screen_*` events are not emitted by the flow; screen ids
    (`S1_welcome` … `S10_fix`, `PW_A_trial_all`) are the flow's `instanceId` for the app to map.
18. Branch after S10 (target-pace vs loader), N1–N3, and the post-purchase chain stay in the app.

---
## Run log (2026-09-30)
Done: app `356b7d68-ddae-41f8-8d3a-2bac9ce1cfa2`; products bound (yearly `5e30a5fb…`, monthly `cf5874b1…`,
weekly `b14a44af…`, **no offer ids** — CLI exposes no offers and no existing paywall/flow binds one);
flows `onb_main` a8b7ec17-d855-48ab-9b31-efdc56f19663 and `pw_main` 482e6945-abf5-4e6e-8407-57ba1ad13c12
created, validated (`valid: true`, 0 issues), mascots uploaded (media ids 541960, 541961) and bound, configs
written (round trip identical), **published**; flow placements `onb_main` (6f4fab8b-ceda-4798-8dfe-4807a21fc1d9)
and `pw_main` (4879de7b-fc4a-4589-8648-76708f6cba52), All users. Fonts: left to the coordinator (builder).
Open risk: with no offer bound, `offer_full_duration` and `is_free_trial` may resolve empty/false on device →
paywall would show the no-trial copy and "  free trial" lines; verify in the device preview first.
