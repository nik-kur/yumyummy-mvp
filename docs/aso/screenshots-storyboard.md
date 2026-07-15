# App Store Screenshots + App Preview — Storyboard

Spec for the 6.9" iPhone screenshot set and the App Preview video. This is the
creative brief a designer (or you in Figma/Screenshot tooling) executes; source
UI frames already exist in `docs/design-review/` (Variant A — the shipped
direction).

## Technical requirements
- **6.9" (iPhone 16 Pro Max):** `1290 × 2796` px, PNG/JPG, up to 10.
- The 6.9" set is the master; App Store Connect auto-scales down to 6.5"/6.1"
  if you don't upload those. You can upload the same frames to 6.5" (1284×2778)
  to be safe.
- Design headline treatment **off-app** (per design review): cream/terracotta,
  Fraunces display headline top ~22%, device mockup below. Keep in-app calm.
- Loud where the store is loud, calm where the app is calm.

## The 4-second rule
Screenshots 1–3 must land the promise before the user swipes past: **fast
logging + numbers you can trust.** Lead with the signature "Logged." moment.

## Frame set (7 frames)

| # | Headline (overlay) | Sub | Source frame | Why |
|---|---|---|---|---|
| 1 | **Logged. And the number is real.** | Every macro cites its source | `docs/design-review/15_7-logged-tick.png` | Signature moment; "USDA VERIFIED" badge visible. The design-review recommendation: lead with the Source Stamp + "Logged." |
| 2 | **Just type what you ate.** | AI parses it in seconds | `docs/design-review/10_2-text-parse.png` | Shows the core speed + itemized parse with source chips. |
| 3 | **Or snap it. Plate, package, or label.** | One photo, every item identified | `docs/design-review/12_4-photo-plate-package-or-label.png` | Capture breadth; strong visual. |
| 4 | **From the source. Not the crowd.** | USDA · EU labels · manufacturers | `docs/design-review/16_1-home-today.png` | The "3 SOURCES" home view — the differentiator, on the daily screen. |
| 5 | **Ask what to eat next.** | Suggestions that fit your macros | `docs/design-review/20_5-what-to-eat.png` | AI advisor value beyond logging. |
| 6 | **A quiet weekly truth.** | No streaks. No shame. | `docs/design-review/24_1-weekly-summary.png` | Emotional positioning vs. gamified competitors. |
| 7 | **Start free for 3 days.** | $9.99/mo after · cancel anytime | `docs/design-review/33_1-paywall-trial-ending.png` | Clear CTA + price anchor; annual save-pill. |

Optional 8th (localized markets / restaurant angle):
`docs/design-review/28_2-agent-web-search.png` — **"Ate out? We'll look it up."**

## Headline copy rules
- Sentence case, short, one idea per frame. Terracotta accent on the key word.
- No urgency/countdown language (brand rule — proof, not pressure).
- Numbers stay tabular; never fabricate a rating/user count in the art.

## App Preview video (15–30s, portrait 1290×2796 / 886×1920 accepted)

Source clips live in `Demos/` (real captured flows). Cut order:

1. **0:00–0:03 — Hook.** Cold open on the composer: type "two scrambled eggs
   and sourdough." (`Demos/assets/h_s2_typing.mp4`)
2. **0:03–0:07 — Parse.** Items resolve with source chips; totals tick up.
   (`Demos/assets/h_s3_sent.mp4` / text-parse capture)
3. **0:07–0:11 — Logged.** The ring-stroke "Logged." animation + "USDA
   VERIFIED". Hold the beat. (`Demos/assets/hero_final.mp4`)
4. **0:11–0:16 — Breadth.** Quick cuts: voice memo, photo of a plate, "what to
   eat?" suggestion. (`Demos/assets/photo_demo.mp4`, `speed_demo_hq.mp4`)
5. **0:16–0:22 — Trust.** Home dashboard with "3 SOURCES"; tap a number to
   reveal the source. (`Demos/assets/h_s4_response.mp4`)
6. **0:22–0:26 — CTA.** End card: wordmark + "Start free for 3 days."

Notes:
- First 3 seconds autoplay muted in the store — the hook must read without
  sound. Burn in captions.
- Keep the in-app footage calm; put energy in pacing/cuts, not motion graphics.
- If a clean automated cut isn't possible from `Demos/`, flag for manual edit —
  the storyboard above is editor-ready.

## Handoff checklist
- [ ] Export 7 frames at 1290×2796 (and 1284×2778 duplicate set).
- [ ] App Preview ≤ 30s, poster frame = the "Logged." moment.
- [ ] Upload in App Store Connect (6.9" slot first).
- [ ] Verify no fabricated ratings/claims in overlays (App Review).
```
