# YumYummy mobile — Intro onboarding + Paywall spec (for no-code rebuild)

Source repo: `/Users/nikita/Documents/YumYummy/yumyummy-mvp/mobile` (Expo Router / React Native). All paths below are relative to `mobile/` unless absolute. Copy strings are verbatim from code. `’` and `'` are kept as in source (curly in some headlines, straight in others; noted where it matters).

---------------------------------------------------------------------------
## 0. GLOBAL: navigation order, shared shell, tokens

### 0.1 Real navigation order (follow of `router.push` calls)

```
(intro)/index            -> <Redirect href="/(intro)/welcome" />          (index.tsx)
S1  welcome      (welcome.tsx)      -> push /(intro)/goal
S2  goal         (goal.tsx)         -> push /(intro)/why           (auto-advance 280 ms after tap)
S3  why          (why.tsx)          -> push /(intro)/gender
S4  gender       (gender.tsx)       -> push /(intro)/age           (auto-advance 280 ms)
S5  age          (age.tsx)          -> push /(intro)/body
S6  body         (body.tsx)         -> push /(intro)/activity
S7  activity     (activity.tsx)     -> push /(intro)/pain-points   (auto-advance 280 ms)
S8  pain-points  (pain-points.tsx)  -> push /(intro)/problem
S9  problem      (problem.tsx)      -> push /(intro)/fix
S10 fix          (fix.tsx)          -> BRANCH on goal_type:
                                        goal_type === 'lose' || 'gain'  -> push /(intro)/target-pace
                                        goal_type === 'maintain' || 'just_track' (or null) -> push /(intro)/loader
N1  target-pace  (target-pace.tsx)  -> push /(intro)/loader            (only lose/gain reach it)
N2  loader       (loader.tsx)       -> router.replace /(intro)/plan-reveal   (auto, ~3.4 s)
N3  plan-reveal  (plan-reveal.tsx)  -> router.push /paywall            (or router.replace /(tabs) if a signed-in user already has billing.access_status in {trial, active})
    paywall      (app/paywall.tsx)  -> purchase/restore (signed out) -> router.replace /save-plan -> /postbuy -> /(tabs)
```

Dead code: **S11 `try-it.tsx`** ("Try it — tap a meal") exists but NOTHING links to it (grep of `src` finds no reference; S10 fix goes straight to N1/loader). It is documented in §S11 for completeness but is NOT part of the live flow. Its header still says "Step 8 of 8" (stale).

Stack config (`(intro)/_layout.tsx`): `<IntroProvider>` wraps an expo-router `Stack` with `headerShown:false`, `contentStyle.backgroundColor = colors.bg (#F7F1E6)`, `gestureEnabled:false` (no swipe-back). Back is only via the on-screen `<` button in IntroHeader (`router.back()`), which exists on S2..S10 and N1 (NOT on S1, N2 loader, N3 plan-reveal).

Entry: the launch router (`app/index.tsx`) sends signed-out users to `/(intro)` (resumes from local draft). The welcome screen also has "Already have an account? Sign in" -> `router.replace('/(auth)/sign-in')`.

### 0.2 Shared shell (`components/Screen.tsx`) — used by every intro screen
`<Screen grow edges={['top','bottom','left','right']}>`: SafeAreaView (all 4 edges), background `colors.bg #F7F1E6`, dark status-bar text, inner View `flex:1` with `paddingHorizontal: 20` (space.lg). So **every intro screen has 20 px side gutters** plus device safe-area. (S11 try-it uses `scroll` variant, unused.)

### 0.3 IntroHeader (top bar with back + progress) — `components/IntroHeader.tsx`
- Row: `flexDirection:row; alignItems:center; gap:12; marginTop:8; marginBottom:8`.
- Back button: 32x32 circle, bg `surface #FFFDF9`, border 1px `hairline #E7DFD1`, icon lucide `ChevronLeft` size 18, color `ink #19150F`, strokeWidth 1.5, hitSlop 10, accessibilityLabel "Go back".
- Progress track: flex 1, height 4, pill radius, bg `terracottaSoft #EFDFD1`; fill = `terracotta #B85A3A`, width = `round(step/12*100)%`.
- Step -> fill: S2 goal step1 = 8%; S3 why 2 = 17%; S4 gender 3 = 25%; S5 age 4 = 33%; S6 body 5 = 42%; S7 activity 6 = 50%; S8 pain-points 7 = 58%; S9 problem 8 = 67%; S10 fix 9 = 75%; N1 target-pace 10 = 83%. (Constant LAST_STEP = 12 = plan-reveal; maintain/track users skip N1 so they jump 75% -> loader with no bar.) No numeric "Step x of y" label anywhere in the live flow.
- Progress is NOT animated (width jumps per screen).

### 0.4 Standard "question screen" header block (S2, S4, S5, S6, S7, S8)
`header: marginTop 12, marginBottom 20, gap 4`; contents top to bottom: overline/eyebrow (left-aligned), h1 with `marginTop:4`, optional body line (inkMuted). Left aligned. Then content area `flex:1` (options centered vertically with `justifyContent:'center'` in S2/S4/S7/S8), CTA pinned at bottom via `marginTop:'auto'` where there is a Continue button.

### 0.5 Text presets (`theme/typography.ts`) — font files in §Assets
| variant | font | size / lineHeight | color | notes |
|---|---|---|---|---|
| hero | Fraunces_600SemiBold | 56 / 58 | ink | tabular-nums (used for Age number) |
| heroNum | Fraunces_600SemiBold | 60 / 60 | ink | (unused in intro) |
| display | Fraunces_600SemiBold | 36 / 40 | ink | (B2 emoji) |
| h1 | Fraunces_600SemiBold | 28 / 32 | ink | headlines |
| h2 | Fraunces_600SemiBold | 22 / 28 | ink | |
| macroValue | Fraunces_600SemiBold | 18 / 22 | ink | |
| title | Inter_600SemiBold | 18 / 24 | ink | option labels, tabular |
| body | Inter_400Regular | 16 / 26 | ink | |
| bodyStrong | Inter_600SemiBold | 16 / 26 | ink | |
| small | Inter_400Regular | 14 / 21 | inkMuted #6B6258 | |
| caption | Inter_500Medium | 12 / 16 | inkMuted | tabular |
| overline / eyebrow | JetBrainsMono_500Medium | 11 / 14, letterSpacing 1.6, UPPERCASE (textTransform) | inkMuted (overridden to terracottaText on intro screens) | |
`AppText` props: `variant`, `color` override, `center` (textAlign center), `style`.
Important: overline text is written in sentence case in code but RENDERED UPPERCASE (e.g. "About you" -> "ABOUT YOU").

### 0.6 Button (`components/Button.tsx`) — the CTA used on all intro screens (`variant="brand"`)
- Full width (alignSelf stretch), minHeight 54, horizontal padding 24, borderRadius 12 (radius.md; never pill), bg `terracotta #B85A3A`, label color `white #FFFFFF`, font Inter_600SemiBold 16 / lineHeight 20, centered. Haptic `selectionAsync` on press. Pressed opacity 0.85. Disabled opacity 0.45 (and not pressable). `loading` replaces label with ActivityIndicator (color = label color).
- Other variants (used on paywall "Retry"): `secondary` = transparent, border 1px hairlineStrong `#D8CCB9`, label ink; size `md` = minHeight 44, padding 16.

### 0.7 Design tokens (`theme/tokens.ts`)
Colors: bg `#F7F1E6` (paper canvas) · surface `#FFFDF9` (cards) · surfaceAlt `#FBF6EE` · ink `#19150F` · inkMuted `#6B6258` · inkFaint `#938A7C` · hairline `#E7DFD1` · hairlineStrong `#D8CCB9` · terracotta `#B85A3A` (CTA fill, selected border, bar fill) · terracottaText `#9A4628` (terracotta as text/eyebrows) · terracottaSoft `#EFDFD1` (selected card bg, tints) · infoBlue `#1F5C99` · infoBlueSoft `#E7EFF8` · success `#2E6B4E` · successSoft `#E3F0E8` · oliveSoft `#E3E6CE` · warning `#8A5A14` · warningSoft `#FBEFD6` · error `#9A2A1F` · errorSoft `#FBEAE7` · protein `#5A6A3A` · fat `#8A5A14` · carbs `#2C6CA8` · white `#FFFFFF`. (Dark-mode tokens exist but unused.)
Ad-hoc colors used in intro: `#C97A6A` (surplus strip, S9), `#7FA06F` (deficit strip, S9), `#D99A28` (star gold, N3 testimonials), `#F2EADB` (welcome demo stage bg), `#16A34A` (DONE_GREEN on paywall).
Spacing: xs 4 · sm 8 · md 12 · base 16 · lg 20 · xl 24 · xxl 32 · xxxl 48.
Radius: sm 8 · md 12 · lg 16 · xl 20 · pill 999.
Elevation: borders not shadows; cards = `surface` bg + 1px (or hairlineWidth ≈ 0.5px) `hairline` border, radius 16, no shadow. (`shadow.float` only for sheets, not used in intro.)

### 0.8 Common option-card style (S2 goal, S7 activity, S8 pain points, S11 presets)
Card: row, align center, bg `surface`, radius 16, border 1.5px `hairline`; **selected**: border `terracotta`, bg `terracottaSoft`. Unselected trailing indicator = 22x22 circle border 1.5 `hairlineStrong` (single-select) or 22x22 rounded-8 checkbox (multi-select). Selected single-select indicator = lucide `CircleCheck` 22 terracotta strokeWidth 1.5.

### 0.9 Analytics
`track(event, props)` = PostHog (`analytics/posthog.ts`). Every intro screen fires `onboarding_screen_viewed {screen: '<id>'}` on mount and `onboarding_screen_completed {screen:'<id>', ...}` on advance. Ids: `S1_welcome, S2_goal, S3_why, S4_gender, S5_age, S6_body, S7_activity, S8_pain_points, S9_problem, S10_fix, N1_target_pace, N2_loader, N3_plan_reveal` (dead: `S11_try_it`). Extra props noted per screen.

### 0.10 Intro draft (persisted state) — `state/introDraft.ts`, `state/introContext.tsx`
AsyncStorage key `@yy_intro_draft`; loaded on IntroProvider mount; every `set(patch)` merges and saves. Fields + defaults:
```
goal_type: 'lose'|'maintain'|'gain'|'just_track'|null   (null)
pain_points: string[]                                   ([])
gender: 'male'|'female'|null                            (null)
age: number                                             (30)
height_cm: number                                       (175)
weight_kg: number                                       (75)
activity_level: 'sedentary'|'light'|'moderate'|'active'|'very_active'|null   (null; UI only offers first four)
target_weight_kg: number|null    (null)   // N1
deficit_pct: number|null         (null)   // N1 (% of TDEE, rounded)
target_weeks: number|null        (null)   // N1
target_calories: number|null     (null)   // N1 or loader
target_protein_g / target_fat_g / target_carbs_g: number|null (null)
```
Synced to backend after sign-in (`save-plan.tsx`): goal_type, gender, age, height_cm, weight_kg, activity_level, target_calories, target_protein_g, target_fat_g, target_carbs_g, onboarding_completed:true (target_weight_kg / weeks / deficit / pain_points are NOT sent to backend; pain_points, goal, target_weight, target_calories go to Adapty custom attributes on N3).

---------------------------------------------------------------------------
## S1 — Welcome (`src/app/(intro)/welcome.tsx`)
**Analytics:** viewed `S1_welcome`; completed `S1_welcome` on Get Started. No progress bar, no back button.

**Layout (Screen all edges; two blocks):**
1. `body` (flex 1, vertically CENTERED, extra paddingHorizontal 20 => total side inset 40, gap 20):
   - `header` (centered column, gap 8):
     - Mascot (`MascotBadge variant="welcome" size=64`, image `assets/mascot/mood_stellar_t.png`, 480x480 transparent PNG shown at 64x64, resizeMode contain, marginBottom 4). Animation: gentle infinite bounce translateY 0 -> -6 -> 0, 700 ms each leg, ease-in-out, reverse-repeat.
     - H1 centered: `The food tracker you’ll actually keep up with` (apostrophe is curly `’`). Fraunces 600 28/32 ink, marginTop 4.
     - Sub (variant title Inter 600 18, **overridden to color inkMuted**, centered, lineHeight 26, maxWidth 320): `Any meal, any way — verified calories in ~10 seconds.`
   - `demoWrap` (stretch): **WelcomeDemo** auto-playing card (below).
2. `bottom` (gap 12, paddingBottom 20, paddingHorizontal 20 => inset 40 total):
   - Button brand: `Get Started`
   - Trust chips row (wrap, centered, gap 8): three pills, bg `surface`, border hairlineWidth `hairline`, radius pill, padding 12 x 5, caption text inkMuted: `★ 4.9` · `12,000+ trackers` · `✓ Verified data`
   - Link (small 14, color terracottaText, centered): `Already have an account? Sign in` -> `/(auth)/sign-in` (router.replace)

**WelcomeDemo (`components/WelcomeDemo.tsx`)** — auto-cycling, no user interaction. Card shell: bg surface, border hairlineWidth hairline, radius 20 (xl), padding 12, marginVertical 12.
- Mode pills row (centered, gap 8, marginBottom 12): `Photo` (lucide Camera), `Voice` (Mic), `Text` (Keyboard); icon size 12 stroke 1.5 + caption label (fontWeight 600), padding 12x5, pill. Inactive: bg `bg #F7F1E6`, border hairline, text inkMuted. Active: bg/border `terracotta`, text white.
- Stage: height 128, radius 12, bg `#F2EADB`, overflow hidden, centered content.
- Result slot: fixed height 76, marginTop 12. Result card fades in (opacity 0->1 + translateY 8->0 over 350 ms) after a per-phase delay: bg surface, border hairlineWidth hairline, **left border 3px terracotta**, radius 12, padding 16x12, row space-between:
  - left: `{kcal}` in h2 (Fraunces 22) + ` kcal` (caption inkMuted), below it the meal name (caption inkMuted)
  - right (aligned end, gap 4): SourceBadge pill (`◎ {SOURCE UPPERCASE}`, JetBrains Mono eyebrow 11px letterSpacing 1, color infoBlue on infoBlueSoft bg, radius pill, padding 8x3) and macros caption.
- Cycle: phase index advances every **3300 ms** (0 -> 1 -> 2 -> 0 ...). Result card is hidden at phase start and shown after `delayMs`.
- Phases (verbatim):
  | # | mode | stage content | result name | kcal | macros | source | result delay |
  |---|---|---|---|---|---|---|---|
  | 0 | Photo (active pill) | big emoji `🥑🍳🍞` (42px, letterSpacing 3) + a 3px terracotta scan line (left/right 8%) sweeping down/up (1250 ms ease-in-out to 72px then back to 20px in 400 ms, looped) + 4 terracotta L-shaped corner brackets (20x20, 2.5px, radius 6, inset 10) | `Avocado toast & eggs` | 412 | `P 22g · F 24g · C 28g` | `USDA` | 1350 ms |
  | 1 | Voice | italic body quote `“Starbucks cappuccino and a butter croissant”` + 7 terracotta waveform bars (5px wide, radius 3, animate height 8<->32, 425 ms each, staggered delays 0,100,200,50,150,250,100 ms) | `Cappuccino & butter croissant` | 350 | `P 11g · F 18g · C 38g` | `Starbucks` | 1350 ms |
  | 2 | Text | typed text (title 18, centered) `tunacado from joe & the juice` typed one char per 45 ms with a blinking terracotta `|` cursor (500 ms) | `Tunacado sandwich` | 570 | `P 25g · F 40g · C 29g` | `Joe & The Juice` | 1700 ms |

---------------------------------------------------------------------------
## S2 — Goal (`src/app/(intro)/goal.tsx`)
**Progress:** IntroHeader step 1 of 12 (8%).
**Copy:**
- Eyebrow: `About you` (renders ABOUT YOU, terracottaText)
- H1: `What’s your goal right now?` (curly apostrophe)
- Options (single-select cards; label only, NO sub-label):
  | key (stored) | lucide icon | label |
  |---|---|---|
  | `lose` | TrendingDown | `Lose weight` |
  | `maintain` | Utensils | `Maintain & eat healthier` |
  | `gain` | Dumbbell | `Gain muscle` |
  | `just_track` | Eye | `Just track my food` |
**Layout:** IntroHeader; header block (§0.4); list `flex:1, justifyContent:center, gap:16` of 4 option cards (§0.8). Each card: 44x44 icon tile (radius 12, bg terracottaSoft; icon 22px, stroke 1.5, terracotta) | label (title Inter 600 18 ink, flex 1) | radio circle. Selected: border terracotta, bg terracottaSoft, icon tile bg terracotta with white icon, trailing `CircleCheck` 22 terracotta. No Continue button.
**Interaction:** single-select, AUTO-ADVANCE: tap -> `set({goal_type})`, track completed `{screen:'S2_goal', goal:key}`, then after 280 ms push `/(intro)/why` (double taps ignored via ref). Selection highlight shows during the 280 ms.
**Pre-selection:** the card reflects `intro.goal_type` (null on fresh install; persisted value on return).

---------------------------------------------------------------------------
## S3 — Why this works (`src/app/(intro)/why.tsx`)
**Progress:** step 2 of 12 (17%). Goal-specific content; `goal_type ?? 'lose'` is used if null.
**Layout top to bottom:** IntroHeader; eyebrow (left aligned, marginTop 12) `Why this works` (terracottaText); centered content block (flex 1, vertically centered, paddingHorizontal 8): BIG STAT -> stat caption -> headline -> body -> tappable citation with `ExternalLink` icon (12px, infoBlue, stroke 1.5, gap 4; tapping opens the PubMed URL in the browser); Button brand `Continue` pinned bottom (marginTop auto).
**Styles:** big stat = Fraunces_700Bold 60 / lineHeight 66, color `terracotta #B85A3A`, centered; stat caption = small (14, inkMuted) centered, marginTop 4; headline = h1 centered marginTop 16; body = body (16/26) inkMuted centered marginTop 8; citation = caption 12 `inkFaint #938A7C` centered, marginTop 16, row with icon.
**Copy per goal (verbatim):**
| goal | stat | statcap | headline (h) | body (b) | citation (foot) | url |
|---|---|---|---|---|---|---|
| lose | `2×` | `more weight lost, on average` | `Tracking is your biggest lever` | `People who log their meals consistently lose about twice as much weight as those who don't — and keep it off longer.` | `Kaiser Permanente study of 1,685 adults · Am J Prev Med, 2008` | https://pubmed.ncbi.nlm.nih.gov/18617080/ |
| maintain | `#1` | `predictor of keeping it off` | `The habit that makes it stick` | `Simply writing down what you eat is one of the strongest predictors of maintaining a healthy weight for good.` | `National Weight Control Registry · Am J Clin Nutr, 2005` | https://pubmed.ncbi.nlm.nih.gov/16002825/ |
| gain | `2×` | `faster lean gains` | `Muscle is a numbers game` | `Hit your protein and calorie targets consistently and you build lean mass far faster than training alone.` | `Meta-analysis of 49 trials · Br J Sports Med, 2018` | https://pubmed.ncbi.nlm.nih.gov/28698222/ |
| just_track | `~30%` | `how much people misjudge intake` | `Awareness changes everything` | `Most people misjudge what they eat by about a third. Just seeing the real numbers is often enough to shift habits.` | `Lichtman et al. · New England Journal of Medicine, 1992` | https://pubmed.ncbi.nlm.nih.gov/1454084/ |
(In the `lose` body the apostrophe in "don't" is a straight `'`.)
**Interaction:** Continue (no validation) -> completed `S3_why` -> push `/(intro)/gender`. Nothing written to the draft.

---------------------------------------------------------------------------
## S4 — Gender (`src/app/(intro)/gender.tsx`)
**Progress:** step 3 of 12 (25%).
**Copy:** eyebrow `Your metabolism`; H1 `How should we calculate your metabolism?`; body (16, inkMuted) `We use this for your calorie formula only.`
**Options:** two square cards side by side: `👨` + `Male` (key `male`); `👩` + `Female` (key `female`).
**Layout:** header block; options row `flex:1, flexDirection:row, gap:16, center/center`; each card `flex:1, aspectRatio:1, maxHeight:160`, bg surface, radius 16, border 1.5 hairline, contents centered column gap 8: emoji (fontSize 40/lineHeight 48) then label (title 18 Inter 600). Selected: border terracotta, bg terracottaSoft. No check mark. No Continue button.
**Interaction:** single-select AUTO-ADVANCE (280 ms) -> `set({gender})`, completed `S4_gender` -> push `/(intro)/age`. Only binary options (Mifflin–St Jeor needs it).

---------------------------------------------------------------------------
## S5 — Age (`src/app/(intro)/age.tsx`)
**Progress:** step 4 of 12 (33%).
**Copy:** eyebrow `Your metabolism`; H1 `How old are you?`; CTA `Continue`.
**Layout:** header block; `picker` row (flex 1, centered both axes, gap 32): round minus button (48x48 circle, bg surface, border 1px hairline, lucide `Minus` 24 ink stroke 1.5, hitSlop 12) — number — round plus button (lucide `Plus`). Number = `hero` variant (Fraunces 600 56/58 ink, tabular). CTA pinned bottom.
**Interaction:** stepper only (no keyboard input). Tap +/- changes by 1, clamped **14..99**; no press-and-hold. Initial = `intro.age` (default 30). Continue -> `set({age})`, completed `S5_age` -> push `/(intro)/body`.

---------------------------------------------------------------------------
## S6 — Height + weight (`src/app/(intro)/body.tsx`)
**Progress:** step 5 of 12 (42%).
**Copy:** eyebrow `Your metabolism`; H1 `Your height and weight`; body (inkMuted) `Used to calculate your calorie target. We never share this data.`; segmented toggle `Metric` | `Imperial`; column labels (overline, inkMuted, centered) `Height` and `Weight` (render uppercase); CTA `Continue`.
**Layout:** header block; SegmentedControl full width (marginBottom 20): container bg surfaceAlt, border 1px hairline, radius 12, padding 4, gap 4; segments flex 1, paddingV 12, radius 8, bodyStrong label; selected segment bg `ink #19150F` with label `bg #F7F1E6`; unselected label inkMuted. Default = Metric. Then two WheelPicker columns side by side (`flex:1` each, gap 24 between columns, vertically centered, each column = overline label above wheel, gap 8). CTA pinned bottom.
**WheelPicker (`components/WheelPicker.tsx`):** vertical snapping list; itemHeight 44, 5 visible rows => 220 px tall; centered row highlighted by a band bg `terracottaSoft` at 50% opacity, radius 8; selected value = h2 (Fraunces 600 22/28) ink; other rows = title (Inter 600 18) `inkFaint`. Scroll-snap with fast deceleration; value commits on momentum-scroll end (no tap-to-select, no haptics).
**Data:**
- Metric: height wheel 120..230 shown as `{n} cm`; weight wheel 30..250 shown as `{n} kg`.
- Imperial: height wheel 48..90 inches shown as `5'9"` (feet'inches"); weight wheel 66..551 shown as `{n} lb`.
- Canonical storage always cm/kg. Conversions: cm->in `round(cm/2.54)`, in->cm `round(in*2.54)`, kg->lb `round(kg*2.2046)`, lb->kg `round(lb/2.2046)`; clamp height 120..230 cm, weight 30..250 kg. Toggling units re-mounts the wheels showing the converted current value.
- Defaults from draft: height 175 cm, weight 75 kg (clamped).
**Interaction:** Continue -> `set({height_cm, weight_kg})`, completed `S6_body` -> push `/(intro)/activity`. (Unit choice is not persisted.)

---------------------------------------------------------------------------
## S7 — Activity (`src/app/(intro)/activity.tsx`)
**Progress:** step 6 of 12 (50%).
**Copy:** eyebrow `Your metabolism`; H1 `How active is your typical week?`
**Options (single-select, emoji + label + sub):**
| key | emoji | label | sub-label |
|---|---|---|---|
| `sedentary` | 🪑 | `Mostly sitting` | `Desk job, little movement` |
| `light` | 🚶 | `Lightly active` | `Walks, 1–2 workouts a week` |
| `moderate` | 🏃 | `Active` | `3–5 workouts a week` |
| `active` | 🏋️ | `Very active` | `Training 6–7 days a week` |
**Layout:** header block; list (flex 1, centered, gap 16) of option cards (§0.8): emoji (26px, lineHeight 32) | text column (label = title 18 ink; sub = small 14 inkMuted; gap 2) | radio / `CircleCheck`. No Continue.
**Interaction:** single-select AUTO-ADVANCE 280 ms -> `set({activity_level})`, completed `S7_activity` -> push `/(intro)/pain-points`. Multipliers in §Logic: sedentary 1.2, light 1.375, moderate 1.55, active 1.725 (`very_active` 1.9 exists in code but is not offered).

---------------------------------------------------------------------------
## S8 — Pain points (`src/app/(intro)/pain-points.tsx`)
**Progress:** step 7 of 12 (58%).
**Copy:** eyebrow `Be honest`; H1 `What made tracking hard before?`; body (inkMuted) `Pick all that apply.`; CTA `Continue`.
**Options (MULTI-select, emoji + label; stable ids stored):**
| id | emoji | label |
|---|---|---|
| `too_long` | ⏱️ | `Logging took too long` |
| `gave_up` | 📉 | `I gave up after a few days` |
| `accuracy` | 🤔 | `Never sure the calories were right` |
| `eating_out` | 🍽️ | `Eating out broke everything` |
| `first_time` | 🌱 | `First time tracking` |
**Layout:** header block; list (flex 1, centered, gap 12); each card: row, gap 12, padding 12 vertical x 16 horizontal, bg surface, radius 16, border 1.5 hairline; emoji (20px / lh 26) | label (title 18, flex 1) | checkbox 22x22, radius 8, border 1.5 hairlineStrong, unchecked = empty; checked = fill `terracotta` + border terracotta + white lucide `Check` 14px stroke 2.5. Selected card: border terracotta, bg terracottaSoft. CTA `Continue` pinned bottom.
**Interaction:** toggle any number (including zero — Continue is always enabled, no validation). Continue -> `set({pain_points: ids[]})`, completed `S8_pain_points {pain_points: ids[]}` -> push `/(intro)/problem`. Pre-fills from draft.

---------------------------------------------------------------------------
## S9 — Problem / "It all comes down to one thing" (`src/app/(intro)/problem.tsx`)
**Progress:** step 8 of 12 (67%).
**Layout:** IntroHeader; a vertical ScrollView (content `flexGrow:1`, justify center, paddingTop 8, paddingBottom 16, scroll indicator hidden) containing in order:
1. Eyebrow (left) `The truth`
2. H1 (marginTop 8) `It all comes down to one thing`
3. Lead (body, inkMuted, marginTop 8): `Weight change is driven by one equation: ` followed inline by bold (bodyStrong, ink) `calories in vs. calories out.`
4. **CicoBalance card** (marginTop 20): bg surface, radius 16, border 1px hairline, padding 16, gap 12:
   - Two vertical bars side by side (row, gap 20, align flex-end, centered, container height 154). Each column width 86: a bar (width 100%, radius 12, rounded, content bottom-centered) above a label (small, inkMuted).
     - Bar 1 label `In`, fill `terracotta`; Bar 2 label `Out`, fill `ink #19150F`. Numbers inside bars are white, 12px/16 (Inter default), marginBottom 8.
     - Bar 2 number always `2,200`. Bar 1 number `2,450` (surplus phase) or `1,950` (deficit phase).
   - Below bars a centered bodyStrong delta line (fades in/out): surplus = color `error #9A2A1F`, text `+250 kcal a day ≈ +1 kg a month`; deficit = color `success #2E6B4E`, text `−250 kcal a day ≈ −1 kg a month` (the minus is U+2212 `−`).
   - Caption (inkFaint, centered): `Illustrative numbers`
   - **Animation:** starts in surplus phase: In bar height 128 (TALL), Out bar 112 (SHORT). 850 ms after phase start a 16px-high colored strip fades in at the TOP of the taller bar (surplus: `#C97A6A` on the In bar; deficit: `#7FA06F` on the Out bar) along with the delta text (300 ms fade). Every **3400 ms** the delta fades out (200 ms), the phase flips, bar heights animate 600 ms (In: 128<->112, Out: 112<->128) then strip/delta fade back in after 850 ms. Loops forever.
5. Breaker (body, inkMuted, marginTop 20): `Sounds simple. But two things quietly break it:`
6. Two trap cards (each marginTop 12; bg surface, radius 16, border 1px hairline, padding 16, row gap 12): emoji (22px lh 28) + column (title 18 ink; text small 14 inkMuted; gap 2):
   - `📏` / `The margin is tiny` / `The gap between losing and gaining is often just 200–300 kcal a day. One dressing. One latte.`
   - `🎯` / `Guesses are usually wrong` / `Most people misjudge what they eat by 20–40%. "Feels healthy" doesn't mean the numbers add up.` (straight quotes / apostrophe)
7. Research citation link (marginTop 16; caption 12 inkFaint + `ExternalLink` 12px infoBlue; wraps): `Research: self-reported food intake is off by ~30% on average (Lichtman et al., NEJM 1992).` -> opens https://pubmed.ncbi.nlm.nih.gov/1454084/
Then CTA OUTSIDE the scroll, pinned (marginTop 8): Button brand `So what's the answer?` (straight apostrophe).
**Interaction:** CTA -> completed `S9_problem` -> push `/(intro)/fix`. No draft writes.

---------------------------------------------------------------------------
## S10 — Fix / "So we built both into one app" (`src/app/(intro)/fix.tsx`)
**Progress:** step 9 of 12 (75%).
**Layout:** IntroHeader; ScrollView (content flexGrow 1, `justifyContent:'space-between'` so header / cards / mascot spread over the height; paddingTop 8, paddingBottom 16) with three groups:
1. Header: eyebrow `The answer`; H1 (marginTop 8) `So we built both into one app`
2. Cards block (gap 16, paddingVertical 12):
   - **Fix card 1** (bg surface, radius 16, border 1px hairline, padding 16, gap 12):
     - Head row (gap 12, centered): number badge 28x28, radius 8, bg terracotta, white `1` (Inter 600 14/18); title (title 18 ink) `Precise — so it actually counts`
     - Desc (small 14 inkMuted): `Every meal checked against official databases and verified brand data — USDA, restaurant menus, packaged foods. Not AI guesses.`
     - Proof meal card (bg surfaceAlt, radius 12, border 1px hairline, padding 12, gap 8): row space-between: name (bodyStrong 16) `Oikos Greek yogurt, 150g` + SourceBadge `◎ DANONE` (infoBlue on infoBlueSoft pill, JetBrains Mono 11); kcal row baseline: `90` (Fraunces_700Bold 34/40 ink) + `kcal` (small inkMuted); macro pills row (gap 8, each pill padding 12x3, pill radius, caption 12): `P 15g` (text protein #5A6A3A on oliveSoft #E3E6CE), `F 0g` (text fat #8A5A14 on warningSoft #FBEFD6), `C 6g` (text carbs #2C6CA8 on infoBlueSoft #E7EFF8).
   - **Fix card 2** (same card style): number badge `2`; title `Frictionless — so you keep it up`; desc (small inkMuted) `Log any meal in ~10 seconds — photo, text, or voice. No barcodes, no scrolling.`; chips row (gap 8) of three pills (bg surfaceAlt, border 1px hairline, padding 12x4, pill; text small 14 ink): `📷 Photo`, `🎤 Voice`, `⌨️ Text`.
3. Mascot row (centered, gap 12, paddingVertical 8): `MascotBadge variant="thumbsUp" size 104` = `assets/mascot/mood_great_t.png` (480x480 PNG displayed 104x104) with animations: bounce translateY 0->-6->0 (700 ms legs) + tilt rotate -4deg<->4deg (900 ms legs), both infinite ease-in-out; beside it a serif label (Fraunces_700Bold 28/32 ink, flexShrink 1) `That's YumYummy` (straight apostrophe).
CTA outside scroll (marginTop 12): Button brand `Build my plan`.
**Interaction:** CTA -> completed `S10_fix` -> IF `goal_type` is `lose` or `gain` push `/(intro)/target-pace`, ELSE push `/(intro)/loader`. No draft writes.

---------------------------------------------------------------------------
## S11 — Try it (DEAD / UNREACHABLE) (`src/app/(intro)/try-it.tsx`)
Not linked from anywhere. Do not rebuild unless wanted. Contents: scroll screen; overline `Step 8 of 8`; H1 `Try it — tap a meal`; body `See how fast YumYummy finds the real numbers.`; three preset rows (Zap icon 16 terracotta + body text; card radius 16 border 1.5 hairline, active = terracotta border): `Oat milk latte, grande` -> result `Oat Milk Latte (Grande)` 270 kcal P5 F7 C47 `Starbucks menu`; `Grilled chicken bowl with rice` -> `Grilled Chicken Rice Bowl` 520 kcal P38 F12 C64 `USDA + recipe est.`; `Kind bar dark chocolate nuts` -> `KIND Bar (Dark Choc.)` 200 kcal P6 F15 C17 `Kind nutrition label`. Result Card: name (title), 4 columns kcal(h2)/protein/fat/carbs (macroValue colored protein/fat/carbs + caption labels), `Source: {source}` caption infoBlue. CTA `Build my plan` disabled until a meal is tapped; routing identical to S10. Events: `tryit_interacted {meal}`, completed `S11_try_it`.

---------------------------------------------------------------------------
## N1 — Target & pace (`src/app/(intro)/target-pace.tsx`) — ONLY lose/gain
**Progress:** step 10 of 12 (83%).
**Goal mapping:** `goal = intro.goal_type === 'gain' ? 'gain' : 'lose'`; `lose = goal==='lose'`.
**Layout:** IntroHeader; ScrollView (paddingBottom 16, no indicator) with:
1. Eyebrow `Your target`
2. H1 (marginTop 8) `Set your goal — see what it takes`
3. Lead (body, inkMuted, marginTop 8, marginBottom 20): `You burn about ~{TDEE} kcal a day at your activity level. Drag the sliders — watch what changes.` — `{TDEE}` = computePlan(...).tdee formatted with thousands separator en-US (e.g. `2,336`); note the literal `~` after "about".
4. **Target weight block** (bg surface, radius 16, border 1px hairline, padding 16 x 12, marginBottom 12): header row space-between: `Target weight` (bodyStrong ink) | `{target} kg` (bodyStrong terracottaText). Below: WheelPicker (same component as S6) with values `tmin..tmax`, suffix `kg`. Optional warning (lose only, when `target < bmiFloor`): caption 12 `warning #8A5A14`, centered, marginTop 8: `Heads up: this is below the healthy BMI range for your height ({bmiFloor} kg).`
5. **By-when block** (same card style): header row: `By when` | `{weeks} wk · by {DATE}` (bodyStrong terracottaText), DATE = today + weeks*7 days formatted `toLocaleDateString('en-US',{month:'short',day:'numeric'})` e.g. `Mar 14`. Native slider: min 4, max 52, step 1, value `weeks`; min track terracotta, max track hairlineStrong, thumb terracotta. Scale row under it (caption 12 inkFaint, space-between): `4 wk` … `52 wk`.
6. **Live plan card** (bg surface, radius 16, border **1.5px hairlineStrong**, padding 16, gap 8):
   - kcal row (baseline, gap 8): big number (Fraunces_700Bold 36/42 ink) `{cal}` (en-US thousands separator, min 0) + `kcal/day` (small inkMuted) + right-aligned pace chip (bg surfaceAlt, border 1px hairline, pill, padding 12x3, small ink): `−{pace} kg/wk` (lose; U+2212) or `+{pace} kg/wk` (gain), pace to 1 decimal.
   - Deficit track: height 8, pill, bg surfaceAlt; fill width = `min(pct,30)/30*100 %`, fill color = tier color.
   - Caption (12 inkMuted): `{pct}% below your burn` (lose) / `{pct}% above your burn` (gain)
   - Tier label (bodyStrong, colored by tier, marginTop 4) and optional sub (small inkMuted).
7. Sources link (marginTop 12, centered): `SourcesLink` = lucide `BookOpen` 14 infoBlue + caption infoBlue `Burn & pacing based on published research — see sources` -> router.push `/sources` (citations screen, Guideline 1.4.1).
CTA outside scroll (marginTop 8): Button brand `Lock it in`.

**Defaults (all derived from draft):**
- `weight = intro.weight_kg`; `gender = intro.gender ?? 'male'`; `tdee` from `computePlan({gender, age, height_cm, weight_kg, activity_level ?? 'light', goal_type})`.tdee.
- Wheel bounds: lose: `tmax = weight-1`, `tmin = min(40, tmax)`; gain: `tmax = max(weight+1, min(weight+30, 250))`, `tmin = weight+1`. Step 1 kg.
- `bmiFloor = round(18.5 * (height_cm/100)^2)` kg.
- Default target: lose = `max(tmin, weight-8)`; gain = `min(tmax, weight+6)`. If draft already has target within [tmin,tmax] it is reused.
- Default weeks: `dw=|weight-defaultTarget|`; `tgtDaily = (lose?0.15:0.08)*tdee`; `w = ceil(dw*7700/tgtDaily/7)`; clamp `lose: 8..40`, `gain: 12..52`. (Draft `target_weeks` reused if present.)
- Worked example (male, 30, 175 cm, 75 kg, 'light'): BMR 1698.75, TDEE 2336; default target 67 kg; default weeks 26; cal 2,000; pace 0.3 kg/wk; pct 14 -> tier "Steady — sustainable for most people".

**Live math:** `KCAL_PER_KG = 7700`; `floor = gender==='female' ? 1200 : 1500`; `dw = |weight - target|`; `dailyDelta = dw*7700/(weeks*7)`; `cal = round((lose ? tdee - dailyDelta : tdee + dailyDelta)/10)*10`; `pace = dw/weeks` (kg/wk); `pct = round(dailyDelta/tdee*100)`.
**Tiers (copy verbatim, color: bad=error #9A2A1F, mid=warning #8A5A14, ok=success #2E6B4E):**
- LOSE:
  - if `cal < floor` OR `pct > 25` -> level bad, label `Too aggressive`, sub `This pace drops you below a safe minimum. Try {SUGGEST} weeks or more — you'd still finish by {SUGGEST_DATE}.` where `maxDelta = min(0.25*tdee, tdee-floor)`, `SUGGEST = ceil(dw*7700/maxDelta/7)`, `SUGGEST_DATE = date(today + SUGGEST weeks)` (en-US `Mon D`).
  - else if `pct > 18` -> mid `Ambitious — doable, needs consistency`
  - else if `pct > 10` -> ok `Steady — sustainable for most people`
  - else ok `Gentle — barely feels like a diet`
- GAIN:
  - `pct > 15` -> bad, label `Aggressive — expect fat gain too`, sub `Slow down to keep gains lean. Try {SUGGEST} weeks or more.` with `SUGGEST = ceil(dw*7700/(0.15*tdee)/7)`
  - `pct > 8` -> mid `Steady build`
  - else ok `Lean gain — slow and clean`
**Lock it in (`lockIn`):** if lose and `cal < floor` -> `finalCal = floor`, `finalWeeks = ceil(dw*7700/(tdee-floor)/7)` (if tdee-floor>0); else unchanged. `macros = macrosForCalories(finalCal, weight, goal)`. `intro.set({ target_weight_kg: target, deficit_pct: pct, target_weeks: finalWeeks, target_calories: finalCal, target_protein_g, target_fat_g, target_carbs_g })`. Track completed `N1_target_pace {target_weight_kg, target_weeks, deficit_pct, tier: 'ok'|'mid'|'bad'}` -> push `/(intro)/loader`. The CTA is NEVER blocked even on "Too aggressive" (it silently clamps).

---------------------------------------------------------------------------
## N2 — Loader (`src/app/(intro)/loader.tsx`)
**Progress:** none (no IntroHeader, no back button).
**Layout:** everything centered (flex 1, center, gap 20):
- Ring: SVG 130x130; two circles r=(130-10)/2=60, stroke 10, fill none: track stroke `terracottaSoft`, arc stroke `terracotta` with round linecap, `strokeDasharray = circumference`, `strokeDashoffset = C*(1 - pct/100)`, rotated -90deg so it starts at 12 o'clock.
- Centered in ring: `{pct}%` Fraunces_700Bold 26/32 ink.
- Status line (title 18 Inter 600 ink, centered, horizontal padding 24): changes by pct: index = `min(3, floor(pct/26))`:
  - pct 0–25: `Calculating your metabolism…`
  - 26–51: `Finding your calorie margin…`
  - 52–77: `Verifying food data for your region…`
  - 78–100: `Almost there…`
  (ellipsis is the single character `…`)
- Caption (12 inkFaint, centered): `300,000+ meals logged with YumYummy`
**Timing:** `pct += 2` every **60 ms** => 0->100 in 50 ticks = **3.0 s**; at 100 fires completed `N2_loader`, waits **400 ms**, then `router.replace('/(intro)/plan-reveal')` (no back). Total ≈ 3.4 s. Ring advances in discrete 2% steps (not eased).
**Logic on mount:** `track viewed N2_loader`. If `!intro.target_calories && gender && activity_level && goal_type` (the maintain / just_track path that skipped N1): `plan = computePlan({gender, age, height_cm, weight_kg, activity_level, goal_type})` -> `set({target_calories: plan.calories, target_protein_g: plan.protein, target_fat_g: plan.fat, target_carbs_g: plan.carbs})`. (Quirk: if target_calories already exists in the draft from an earlier pass it is not recomputed.)

---------------------------------------------------------------------------
## N3 — Plan reveal (`src/app/(intro)/plan-reveal.tsx`)
**Progress:** none (no IntroHeader/back). Shown via `replace` from loader.
**Layout (body column, flex 1, gap 16):**
1. Header (centered, gap 8, marginTop 8): eyebrow `Your plan is ready` (terracottaText, centered); H1 centered `Here’s your daily target` (curly apostrophe).
2. **Plan card** (bg surface, radius 16, border 1px hairline, padding 20 vertical x 16 horizontal, gap 16, centered): kcal row (baseline, gap 8): `{cal}` (Fraunces_700Bold 64/72 ink, en-US thousands sep) + `kcal/day` (small inkMuted). Macro row (stretch, gap 8): three equal boxes, radius 12, paddingV 12, centered, gap 2:
   - bg oliveSoft `#E3E6CE`: `{protein} g` (bodyStrong, color protein #5A6A3A) over `Protein` (caption, protein)
   - bg warningSoft `#FBEFD6`: `{fat} g` (bodyStrong, fat #8A5A14) over `Fat`
   - bg infoBlueSoft `#E7EFF8`: `{carbs} g` (bodyStrong, carbs #2C6CA8) over `Carbs`
   (shows `—` if a value is missing.) Then SourcesLink centered: `Mifflin–St Jeor equation — see the science` -> `/sources`.
3. **Branch card:**
   - IF `goal_type` is lose/gain AND `target_weight_kg` AND `target_weeks` set -> **Trajectory card** (bg surface, radius 16, border 1px hairline, padding 12, gap 8): SVG line chart (viewBox 330x190, width 100%, height 190) and a facts row (wrap, centered, gap 8) of pills (bg surfaceAlt, border 1px hairline, pill, padding 12x4, caption 12 ink):
     - `−{pace} kg/week` (lose, U+2212) or `+{pace} kg/week` (gain); pace = |weight_kg - target_weight_kg| / target_weeks, 1 decimal
     - `{cal} kcal/day` (en-US thousands sep)
     - if `deficit_pct` truthy: `{deficit_pct}% below burn` (lose) / `{deficit_pct}% above burn` (gain)
     **Chart:** padL 14, padR 60, padT 22, padB 30. y-range = [min(weight,target)-0.8, max(weight,target)+0.8] (span min 1.5). 40 points, t=i/39. Lose: `base = target + (weight-target)*(1-t)^1.35`; gain: `base = weight + (target-weight)*t^1.35`; plus a wobble `waveAmp = span*0.07*(1 - t*0.65)`, `wave = waveAmp*(0.55 sin(5.2πt) + 0.35 sin(2.4πt+0.8) + 0.1 sin(8.1πt+1.4))`, plus a plateau bump `+0.45*waveAmp` for 0.32<t<0.48. Elements: dashed target line (1px hairlineStrong, dash 4 4) across the plot at the target y; polyline stroke terracotta 2.5px no fill; start dot r 4.5 fill ink; end dot r 5.5 fill terracotta; start label `{weight} kg` (11px inkMuted, offset +8,-8); end label `{target} kg` (11px bold terracottaText, offset +10,+4); x-axis labels 10px inkFaint: left = today `Mon D`, right (end-anchored at plot right edge) = today + target_weeks weeks `Mon D` (en-US short month + day).
   - ELSE (maintain / just_track, or no target) -> **Zone card** (bg infoBlueSoft `#E7EFF8`, radius 16, padding 16): body 16 ink: `⚖️ Your maintenance zone: ` + bold (bodyStrong) `{LO}–{HI} kcal` + `. Stay inside it — weight stays put.` where `LO = round(cal*0.97/10)*10`, `HI = round(cal*1.03/10)*10`, en-US thousands sep, en dash between.
4. **Testimonial carousel** (wrapper flex 1, minHeight 140; card bg surface, radius 16, border 1px hairline, padding 16, content spaced between): auto-rotates every **3200 ms** with cross-fade (250 ms fade out, swap, 250 ms fade in); no swipe. Inner content (gap 8): top row (gap 12): circular avatar 52x52 (radius 26; image from `assets/avatars/{name}.jpg`) + column: name (bodyStrong) and descriptor (caption terracottaText); then `★★★★★` (color `#D99A28`, 15px/18); then quote (body 16, lineHeight 23) wrapped in curly quotes `“…”`. Below: dots row (gap 5, centered, wrap, marginTop 8): one 6x6 dot per testimonial (inactive hairlineStrong, active terracotta). Testimonials (name · descriptor · text, verbatim):
   1. Maria · `lost 4 kg` · `Six weeks in and down 4 kg. Logging takes me maybe a minute a day — that's the whole trick.`
   2. Denis · `maintaining` · `I stopped guessing. The app knows the real numbers, so I finally trust what I eat.`
   3. Sara · `lost 6 kg` · `Tried three trackers before. This is the first one I didn't quit.`
   4. James · `lost 8 kg` · `The weight graph actually matched reality — small ups and downs, but the trend was right.`
   5. Priya · `gaining lean mass` · `Gaining lean mass without guessing portions. Macros finally make sense day to day.`
   6. Tom · `maintaining` · `Maintenance used to feel like a second job. Now I just check in and move on.`
   7. Elena · `lost 3 kg` · `Photo logging changed everything — I log restaurant meals I used to skip entirely.`
   8. Chris · `lost 5 kg` · `Voice logging at lunch is stupidly fast. I'm on a 19-day streak now.`
   9. Sophie · `first-time tracker` · `First tracker where the numbers felt verified, not made up by AI.`
   10. Alex · `lost 7 kg` · `Down 7 kg in 10 weeks. The plan felt realistic from day one — no crash-diet vibes.`
   (Same 10 testimonials regardless of goal; starts at Maria.)
CTA (outside body, marginTop 12): Button brand `Start my plan`.
**Interaction (`pushAttributesAndNavigate`):** track completed `N3_plan_reveal`; breadcrumb; if Adapty configured: wait for identify, then `adapty.updateProfile({codableCustomAttributes:{goal: goal_type ?? 'track', pain_points: pain_points.join(','), target_weight: target_weight_kg ?? 0, target_calories: target_calories ?? 0}})` (failures swallowed). Then: if signed-in profile already `billing.access_status` in {`trial`,`active`} -> track `paywall_skipped_already_premium {source:'plan_reveal'}` + `router.replace('/(tabs)')`; else `router.push('/paywall')`.

---------------------------------------------------------------------------
## LOGIC: `utils/calories.ts` (Mifflin–St Jeor)
```
BMR  = 10*weight_kg + 6.25*height_cm - 5*age + (male ? +5 : -161)
TDEE = BMR * ACTIVITY[activity_level]      // sedentary 1.2, light 1.375, moderate 1.55, active 1.725, very_active 1.9 (unused in UI)
GOAL_DELTA: lose -0.20, maintain 0, gain +0.12, just_track 0
calories = round( TDEE * (1 + GOAL_DELTA[goal]) / 10 ) * 10        // nearest 10 kcal (computePlan; used by loader for maintain/just_track)
protein  = round(weight_kg * (goal==='lose' ? 2.0 : 1.8))          // computePlan
fat      = round(calories * 0.27 / 9)                              // 27% of kcal from fat
carbs    = max(0, round((calories - protein*4 - fat*9)/4))
returns {calories, protein, fat, carbs, bmr: round(bmr), tdee: round(tdee)}

macrosForCalories(calories, weight_kg, goal)  // used by N1 lockIn
protein = round(weight_kg * (goal==='lose' || goal==='gain' ? 2.0 : 1.8))
fat = round(calories*0.27/9); carbs = max(0, round((calories - protein*4 - fat*9)/4))
```
N1 overrides the calorie target: lose `cal = round((TDEE - dw*7700/(weeks*7))/10)*10`; gain `cal = round((TDEE + dw*7700/(weeks*7))/10)*10`. The `GOAL_DELTA` of -0.2/+0.12 is only used when N1 is skipped (and only lose/gain use N1, so GOAL_DELTA effectively only matters for maintain/just_track = 0). Safe minimums: female 1200, male 1500 kcal.
Deficit -> target date: `date = today + weeks*7 days`, `weeks` chosen on the slider (4..52) or defaulted (8..40 lose; 12..52 gain).
`GOAL_LABELS` / `ACTIVITY_LABELS` in calories.ts are for other screens (not used in intro).

---------------------------------------------------------------------------
## PAYWALL (`src/app/paywall.tsx` + `src/components/paywall/*` + `src/billing/paywallConfig.ts`)

### P.0 Screen shell and loading
- Route `/paywall`: root stack presentation `fullScreenModal`, `gestureEnabled:false` (`app/_layout.tsx`). Full-screen, no header.
- While loading (`phase==='loading'`): `Screen` (bg colors.bg) with a centered `ActivityIndicator` color terracotta.
- Flow: `activateAdapty()` -> `adapty.getPaywall(placement 'main', undefined, {loadTimeoutMs: 5000})` -> parse `remoteConfig.dataString` (JSON) with `parseRemoteConfig` (falls back to `FALLBACK_CONFIG` if empty/invalid/no variant/no plans) -> `adapty.getPaywallProducts` -> `logShowPaywall` -> track `paywall_shown {placement:'main', variant, products_available}` -> render. On any failure: fallback paywall (FALLBACK_CONFIG, variant A) rendered with display prices and purchases disabled (no products) + track `paywall_fallback_shown {placement, reason:'adapty_unavailable'|'load_failed', error?}`. Placement id = env `EXPO_PUBLIC_ADAPTY_PLACEMENT_MAIN` or `'main'`. Access level `premium`.
- Apple Search Ads users: after ready, waits up to 20 s for attribution; if the targeted paywall differs, it hot-swaps the config/products once (`paywall_variant_swapped {from_variant,to_variant,reason:'apple_search_ads'}`), never during a purchase.
- On mount (unless `dismissable`), also checks Adapty `hasActivePremium()`; if already premium: `paywall_skipped_already_premium {placement, source:'paywall_mount', signed_in}`, `startJourney()`, then signed-out -> `/save-plan` (marker source `existing_access`); signed-in -> sync billing, `refreshProfile`, `router.replace('/(tabs)')`.
- **Close-button rule:** hard paywall — NO close button, swipe-dismiss disabled; exits only via successful purchase/restore. Only when opened with `?dismissable=1` (Profile -> "Manage plan"/"See plans") is a close button overlaid: 34x34 circle, bg `surfaceAlt`, lucide `X` 20 inkMuted stroke 2, position absolute `top: safeAreaTop + 4`, `left: 20`; tap -> track `paywall_closed {dismissable:true}` then `router.back()` (or `replace('/(tabs)')`).
- Variant resolution (`resolveVariant(config.variant)`): `A_clean_v3` / `A_trial_all_v1` -> **A** (`PaywallRenderer`); `B_trial_designer` -> **B** (`VariantB`); `B2_coffee_compare` -> **B2**; `C_result_hook` -> **C**; `S_hero_v1`, `M_single_trial_v1`, `W_single_trial_v1` -> **S** (`VariantSHero`); anything unknown -> A.
- NOTE: which variant is live is decided server-side in Adapty (placement `main`, audiences/A-B). The repo has reference configs in `/Users/nikita/Documents/YumYummy/yumyummy-mvp/config/paywalls/*.json` (a, a_trial_all, b, b2, c, m_single_trial, w_single_trial) — dumped in §P.8. I could not read the live Adapty dashboard, so the currently live variant is UNRESOLVED from code alone. The bundled `FALLBACK_CONFIG` (no Adapty) is variant A with the `trial_all` copy (§P.2). (`assets/billing/fallback_paywall.json` exists but is not referenced by any source file.)

### P.1 Remote-config contract (`PaywallRemoteConfig`)
```
variant: string; headline: string;
hero: { label, goal_line, maintain_line }
social: { laurels: string[], quote: {text, author} }        // quote is NOT rendered by any current variant
timeline?: { enabled_for? (legacy, ignored), steps: [{icon,'t','d', done?}] }
plans: [{ product, badge?, rec_tag_by_goal?{lose|default}, price_style? ('trial_big'), sub?, display_price?, display_sub? }]
cta: { trial?, yearly?, monthly?, weekly? }
above_cta: string; hard_paywall: boolean
(B extras: primary_selector.options[{key,label,desc,product}], view_all_plans_label; B2 extra: compare_card{left,right{emoji,label,price}}; C extras: result_card{title,lines[{label,value}]}, show_more_plans_label)
```
IRON RULE: real prices, trial presence, and trial length ALWAYS come from StoreKit products (`paywall.products`), never from config; config `display_*` strings are offline stand-ins only.

**Placeholders** (`fillPlaceholders` replaces `{KEY}`; unresolved ones stay as literal text, detected by `/\{\w+\}/`):
| placeholder | source |
|---|---|
| `{TARGET_WEIGHT}` | `"{draft.target_weight_kg} kg"` (intro draft; undefined if none) |
| `{TARGET_DATE}` | today + draft.target_weeks*7 days, en-US `Mon D` (undefined if no weeks) |
| `{DAILY_KCAL}` | `String(draft.target_calories ?? profile.target_calories)` |
| `{RATING}` | default `4.9` |
| `{USERS}` | default `12,000` |
| `{PRICE_M}` | StoreKit localized price of product whose id contains `monthly`, else `$9.99` |
| `{PRICE_W}` | StoreKit localized price of product whose id contains `weekly`, else `$4.99` |
`goal` passed to renderers = `draft.goal_type ?? profile.goal_type`.

**Product ids:** `ai.yumyummy.app.yearly` ($89.99/yr in display copy), `ai.yumyummy.app.monthly` ($9.99/mo), `ai.yumyummy.app.weekly_upd` ($4.99/wk). Single-plan configs use monthly (`M_single_trial_v1`) or weekly_upd (`W_single_trial_v1`). Display copy everywhere states a **3-day free trial**.

**Helper formats (`paywallConfig.ts`):**
- `priceLabel(p)` = store `price.localizedString`.
- `perWeekPrice(p)` = price / days-in-period * 7 (year=365d, month=30.4d, week=7d, day=1d), 2 decimals, currency symbol prefix; `periodPriceLabel` = `"{perWeek}/wk"` (e.g. `$1.73/wk`).
- `trialLength(p)` = store's localized free-trial period string, e.g. `3 days` (undefined if store gave no free-trial phase -> customer is "ineligible/returning").
- `billingCadence(p)`: year -> `billed annually at {PRICE}`; month -> `billed monthly at {PRICE}`; week -> `billed weekly`; day -> `billed daily`.
- `resolveCtaKey`: if trial present and `config.cta.trial` exists -> `trial`; else by period year -> `yearly`, month -> `monthly`, week -> `weekly` (fallback by product-id substring).
- `subscriptionTerms(p)` (used by S): if price+interval known: trial ? `Free for {TRIAL}, then {PRICE} {INTERVAL}. Renews automatically unless cancelled at least 24 hours before the end of the current period. Cancel anytime in your Apple Account settings.` : `{PRICE} {INTERVAL}. Renews automatically unless cancelled at least 24 hours before the end of the current period. Cancel anytime in your Apple Account settings.`; INTERVAL = `per year|month|week|day` or `every N {unit}s`; if no price: just `Renews automatically unless cancelled at least 24 hours before the end of the current period. Cancel anytime in your Apple Account settings.`
- **PAID_TIMELINE_STEPS** (shown instead of config timeline when the store granted NO trial): `✓ Done — Your personal plan — built` (done) · `🔓 Today — Full access unlocked` · `🔔 Day 2 — You'll set up your full tracking system and see how simple it is` · `★ Day 3 — You'll start noticing changes in your routine and eating trends`.
- Timeline icon mapping (emoji in config -> lucide): `✓` -> `CircleCheck`, `🔓` -> `LockOpen`, `🔔` -> `Bell`, `★` -> `Star` (default Star).

**FALLBACK_CONFIG copy (bundled, variant `A_clean_v3`):**
headline `Nutrition tracking that finally works`; hero label `YOUR PLAN — LOCKED IN`, goal_line `{TARGET_WEIGHT} by {TARGET_DATE}`, maintain_line `Your zone: {DAILY_KCAL} kcal`; laurels `★ {RATING} rating`, `{USERS}+ trackers`, `✓ Verified data`; (social quote `Finally started losing — the numbers were just right.` / `Maria · −4 kg in 6 weeks` — not rendered); timeline steps: `✓ Done — Your personal plan — built` (done), `🔓 Today — Full access unlocked — you pay nothing`, `🔔 Day 2 — We'll remind you 24h before any charge`, `★ Day 3 — Trial ends — cancel anytime before`; plans: yearly (badge `BEST VALUE`, rec tags `lose`: `✦ Recommended for a steady habit`, `default`: `✦ Recommended for building the habit`, display `$1.73/wk` / `3 days free trial, then billed annually at $89.99`), monthly (`$2.30/wk` / `3 days free trial, then billed monthly at $9.99`), weekly_upd (`$4.99/wk` / `3 days free trial, then billed weekly`); cta: trial `Start 3 days free now`, yearly/monthly/weekly `Continue`; above_cta `✓ No payment due now · Cancel anytime`; hard_paywall true.

### P.2 Variant A — `PaywallRenderer.tsx` (multi-plan, default/fallback)
Container: SafeAreaView (top, bottom edges) bg `colors.bg`. Constants: TERMS_URL `https://yumyummy.ai/terms.html`, PRIVACY_URL `https://yumyummy.ai/privacy.html`, DONE_GREEN `#16A34A`.
Top to bottom:
1. **Top bar** (row, space-between, paddingH 20, paddingV 4): empty 50px spacer left; right: `Restore` (caption 12, inkFaint, hitSlop 12) -> restore flow.
2. **ScrollView** (no bounce, no indicator; contentContainer paddingH 20, paddingBottom 20):
   - H1 centered `{config.headline}` (Fraunces 28), marginTop 4, marginBottom 8.
   - **Hero card** (only if a hero line resolves): bg surface, radius 16, border hairlineWidth hairline, padding 12 x 16, centered, gap 2, marginBottom 8. Eyebrow `{hero.label}` (overline, terracottaText => `YOUR PLAN — LOCKED IN`) + line in h2 (Fraunces 22) centered. Line choice: if goal is `lose`/`gain` and `goal_line` fully resolves -> `{TARGET_WEIGHT} by {TARGET_DATE}` (e.g. `67 kg by Mar 14`); else if `maintain_line` resolves -> `Your zone: {DAILY_KCAL} kcal`; else the whole card is hidden (never shows a raw `{TOKEN}`).
   - **Laurels** (row wrap centered, gap 8, marginBottom 8): pills bg surfaceAlt, padding 12x4, pill; caption inkMuted; from `social.laurels` with placeholders filled (e.g. `★ 4.9 rating`, `12,000+ trackers`, `✓ Verified data`). (A does not filter unresolved ones.)
   - **Timeline** (marginBottom 8): vertical rows: left icon column width 26: circle 26x26 (bg terracottaSoft; done = bg `#16A34A`) with icon 14px (done: white, stroke 2.5; else terracotta, stroke 1.5); connector line between rows 2px wide, min 8px, bg hairline, vertical margin 2 (none after last row). Right column: title (bodyStrong 16 ink) = step.t, desc (caption 12 inkMuted) = step.d; paddingBottom 8, gap 1. Steps = `config.timeline.steps` if the selected plan's StoreKit product has a free trial, else `PAID_TIMELINE_STEPS`.
   - **Plan cards** (gap 8, marginBottom 12), one per `config.plans`, selectable (default selected = first plan): card bg surface, radius 16, border 1.5 hairline (selected: border terracotta), padding 12 x 16.
     - Optional badge (if `plan.badge`): top-left pill bg terracotta, radius 8, padding 8x2, marginBottom 4, overline text white. If the store returned a product but no trial, `· N DAYS FREE` is stripped from the badge text (regex `\s*·\s*\d+\s*DAYS?\s*FREE`).
     - Row: radio 22x22 circle border 1.5 hairline (selected: border terracotta + 11px terracotta dot) | info column: main label (title 18 Inter 600) + sub label (caption 12 inkMuted).
       - No product (offline): main = `plan.display_price ?? '—'`; sub = filled `display_sub ?? sub ?? ''`.
       - Product + `price_style==='trial_big'` + trial: main = `{TRIAL} free trial` (e.g. `3 days free trial`); sub = `No payment due now. Then {perWeek}/wk {cadence}.`
       - Product + trial (default style): main = `{perWeek}/wk` (e.g. `$1.73/wk`); sub = `{TRIAL} free trial, then {cadence}` (e.g. `3 days free trial, then billed annually at $89.99`).
       - Product, no trial: main = `{perWeek}/wk`; sub = `{cadence}` (or `plan.sub`).
     - Recommendation tag (only on the selected card): caption 12 `protein #5A6A3A` marginTop 4, text = `rec_tag_by_goal[goal] ?? rec_tag_by_goal.default`: `✦ Recommended for a steady habit` (goal lose) / `✦ Recommended for building the habit` (others).
   - **Above-CTA line** (caption 12, `#16A34A`, centered, marginBottom 8): with trial -> `config.above_cta || '✓ No payment due now · Cancel anytime'` (typically `✓ No payment due now · Cancel anytime`); without trial -> `✓ Cancel anytime`.
   - **CTA** Button brand full width: label = `Processing…` while purchasing (with spinner) else `config.cta[key]` (key via `resolveCtaKey`; with placeholders filled): trial -> `Start 3 days free now`; yearly/monthly/weekly (no trial) -> `Continue` (legacy A_clean_v3 config uses `Start 3 days free now` / `Continue — {PRICE_M}/mo` / `Start now — {PRICE_W}/wk`). Disabled if the selected product isn't loaded.
   - If `products.length===0`: store notice (marginTop 16, centered, gap 12): caption inkMuted `Prices shown for reference — the App Store connection isn’t available right now.` + secondary md Button `Retry` (-> reload paywall, event `paywall_retry_pressed`).
   - **Legal block (below the fold):** disclosure (caption 12 inkFaint, centered, lineHeight 16, marginTop 20): with trial `After the free trial, your subscription auto-renews at the price shown unless cancelled at least 24 hours before the end of the current period. Manage or cancel anytime in your Apple Account settings.`; without trial `Subscription auto-renews at the price shown unless cancelled at least 24 hours before the end of the current period. Manage or cancel anytime in your Apple Account settings.` Then a centered link row (marginTop 16; each caption 12 inkFaint): `Restore` · `Terms` (opens https://yumyummy.ai/terms.html) · `Privacy` (opens https://yumyummy.ai/privacy.html), separated by ` · `.

### P.3 Variant S — `VariantSHero.tsx` (single-plan "hero timeline"; configs M_/W_single_trial, `S_hero_v1`)
SafeAreaView (top, bottom) bg colors.bg. Only `config.plans[0]` is used; NO plan card, NO price card.
1. Top bar identical to A: `Restore` top right.
2. ScrollView (flexGrow 1, paddingH 20, paddingBottom 16, no bounce):
   - H1 centered `{headline}` (e.g. `Nutrition tracking that finally works`), marginTop **24**, marginBottom 8.
   - Hero card (same as A; hidden if nothing resolves).
   - Laurels row (same pills as A but **unresolved ones are filtered out**), gap 8.
   - **Timeline = centerpiece** (flexGrow 1, vertically centered, paddingH 4, paddingV 20): rows with bigger dial: icon circle **40x40** (bg terracottaSoft; done = `#16A34A`), icon 20px (done white stroke 2.5; else terracotta stroke 1.75), rail **3px** wide, min 20px, radius 2, bg terracottaSoft, vertical margin 4; row gap 16; title = title (Inter 600 18 ink), description = small (14/20 inkMuted); each content block paddingBottom 20 (0 on last). Steps: config.timeline.steps when store trial present, else PAID_TIMELINE_STEPS. Standard single-plan steps: `✓ Done — Your personal plan — built` (green) · `🔓 Today — Full access unlocked — you pay nothing` · `🔔 Day 2 — We'll remind you 24h before any charge` · `★ Day 3 — Trial ends — cancel anytime before`.
3. **Footer pinned at bottom (not scrolling)** (paddingH 20, paddingBottom 8, gap 12):
   - Above-CTA (caption, `#16A34A`, centered): trial -> `✓ No payment due now · Cancel anytime`; else `✓ Cancel anytime`.
   - CTA Button brand: `Processing…` | `config.cta[key]` (`Start my 3-day free trial` with trial; `Continue` for monthly/weekly without trial). Disabled without product.
   - Store notice when no products (same text + `Retry`).
   - **Terms line** (caption 12 inkFaint centered, lineHeight 15): with store product = `subscriptionTerms(product)` e.g. `Free for 3 days, then $9.99 per month. Renews automatically unless cancelled at least 24 hours before the end of the current period. Cancel anytime in your Apple Account settings.`; offline = `plan.display_sub ?? plan.sub` (for M: `Free for 3 days, then $9.99 per month. Renews automatically unless cancelled at least 24 hours before the end of the current period. Cancel anytime in your Apple Account settings.`; for W: `... $4.99 per week ...`).
   - Legal row: `Restore` · `Terms` · `Privacy` (same URLs/style as A).

### P.4 Variant B — `VariantB.tsx` ("Design your trial"; config `B_trial_designer`)
Plain View bg bg (no SafeAreaView — relies on parent). Top bar: spacer + `Restore` (paddingH 20, paddingTop 8). ScrollView (paddingH 20, paddingBottom 48):
- H1 centered `{headline}` (`Design your trial`), marginTop 12, marginBottom 20.
- Hero card (padding 20, centered, gap 4, marginBottom 16; surface, radius 16, hairlineWidth border): eyebrow `YOUR PLAN — LOCKED IN` + h2 centered: goal `maintain`/`just_track` -> `Your zone: {DAILY_KCAL} kcal` else `{TARGET_WEIGHT} by {TARGET_DATE}` (NO unresolved-token fallback in B — can show raw `{TARGET_WEIGHT}`).
- Primary selector (gap 12, marginBottom 16): 2 cards from `primary_selector.options` (surface, radius 16, border 1.5 hairline, padding 16; active: border terracotta + bg surfaceAlt): label (bodyStrong) + desc (caption inkMuted): `3-day free trial` / `Full access, cancel anytime` (product yearly); `Weekly pass` / `No commitment, instant access` (product weekly_upd). First is selected by default.
- `View all plans` link (small 14 terracottaText, centered, marginBottom 20) -> expands a list (gap 8) of rows (surface, radius 12, padding 12, hairlineWidth border, row space-between): product id with prefix `ai.yumyummy.app.` stripped and `_` -> space (e.g. `yearly`, `monthly`, `weekly upd`) left, price `{symbol}{amount.toFixed(2)}` right (bodyStrong). Tapping a row selects the matching selector option if one exists.
- Above CTA (caption, `success #2E6B4E`, centered, marginBottom 12): `✓ No payment due now · Cancel anytime in 2 taps`.
- CTA brand: `Processing…` | `cta[yearly|monthly|weekly]` by selected product id: yearly `Try Free for 3 Days`; monthly `Continue — {PRICE_M}/mo`; weekly `Start now — {PRICE_W}/week`. Disabled until product found.
- Disclosure (caption inkFaint centered lh 16, marginTop 12): `Subscription auto-renews unless cancelled at least 24h before the end of the current period. Manage or cancel anytime in your Apple Account settings.`; legal row: `Restore` (tappable) followed by plain, NON-tappable text ` · Terms · Privacy`.
- No store-notice/Retry block.

### P.5 Variant B2 — `VariantB2.tsx` ("Less than your morning coffee"; `B2_coffee_compare`)
Same shell as B (View, top bar `Restore`, ScrollView). Content:
- H1 centered `Less than your morning coffee`.
- **Compare row** (row, center, gap 12, marginBottom 20): two equal cards (surface, radius 16, hairlineWidth border, padding 16, centered column gap 4) with `vs` (h2, inkMuted) between them: left: emoji `☕` (display 36) / `A coffee` (bodyStrong) / `$5.00` (caption inkMuted); right (highlight: border 1.5 terracotta): `🍏` / `YumYummy / day` / `$0.25` (caption terracottaText). (Values from `compare_card`, these are the defaults.)
- **Plans** (gap 12, marginBottom 16): each row card (row, gap 12, surface, radius 16, border 1.5 hairline, padding 16; active = border terracotta): radio (22/11 terracotta) | info: price text `{symbol}{amount.toFixed(2)}` (bodyStrong; falls back to raw product id offline) + `plan.sub` (caption inkMuted, placeholders filled): yearly no sub shown (`MOST POPULAR · 3 DAYS FREE` badge pill at right only when active: bg terracotta, radius 8, padding 8x2, overline white), monthly sub `billed monthly · no trial`, weekly sub `start today · no commitment`. Default selected = first plan (yearly).
- Above CTA (success, centered): `✓ No payment due now · Cancel anytime in 2 taps`.
- CTA brand `Processing…` | `Try Free for 3 Days` (yearly) / `Continue — {PRICE_M}/mo` / `Start now — {PRICE_W}/week`.
- Disclosure (caption inkFaint centered): `Subscription auto-renews unless cancelled. Manage in Apple Account settings.` + legal row `Restore` + plain ` · Terms · Privacy`.

### P.6 Variant C — `VariantC.tsx` ("Your result is ready"; `C_result_hook`)
Same shell as B. Content:
- H1 centered `Your result is ready`.
- **Result card** (`Card` component: surface, radius 16, hairlineWidth border, padding 20; marginBottom 20): title (title 18, centered) `Your plan snapshot`; rows (gap 12, marginTop 12), each row space-between: label (body inkMuted) / value (bodyStrong, placeholders filled): `Daily target` / `{DAILY_KCAL} kcal`; `Goal` / `{TARGET_WEIGHT}`; `Timeline` / `by {TARGET_DATE}`.
- If not expanded: **primary plan card** (surface, radius 16, border 1.5 terracotta, padding 16, centered, gap 4, marginBottom 12): badge pill `MOST POPULAR · 3 DAYS FREE` (terracotta bg, white overline), big `{perMonth}/mo` (title 18) where perMonth = yearly price/12 with currency symbol (`{symbol}{x.toFixed(2)}`; shows just `/mo` if offline), caption `{symbol}{amount}/yr`. Then link `Show more plans` (small terracottaText, centered, marginBottom 20) -> expands to a list of plan rows (same style as B2 rows: radio + price; plan.sub) and hides the primary card.
- Above CTA (success, centered): `✓ No payment due now · Cancel anytime in 2 taps`.
- CTA brand: same yearly/monthly/weekly labels as B (`Try Free for 3 Days` default since yearly preselected).
- Disclosure + legal as in B2.

### P.7 Purchase / restore logic (`app/paywall.tsx`) and what happens after
- CTA tap -> `handlePurchase(product)`: track `paywall_plan_selected {product, variant}`; if Adapty not configured (dev) -> `paywall_purchase_success {mode:'dev_trial'}`, `startJourney()`, signed-out -> save-plan hand-off, else `api.startTrial(3)` + `/postbuy`. Normal: `waitForAdaptyIdentify()` -> `adapty.makePurchase(product)`:
  - success -> `paywall_purchase_success {product, variant, price, currency, has_trial}`; AppsFlyer event `af_start_trial` (if the product has a free trial; props af_content_id, af_currency, af_price) else `af_subscribe` (af_revenue + af_price); `startJourney()`; if trial: `scheduleTrialEndingReminder(now)`; **signed-out (normal acquisition)**: save `PendingPurchase {adapty_profile_id, product, source:'purchase'}` then `router.replace('/save-plan')`; signed-in: `refreshProfile()` then `router.replace('/postbuy')`.
  - `user_cancelled` -> `paywall_purchase_cancelled {product}` (stay on screen, no alert).
  - `pending` -> `paywall_purchase_pending` + Alert title `Purchase pending` / message `Your purchase needs approval and will activate once it's confirmed.`
  - error -> `paywall_purchase_failed {product, error}` + Alert `Purchase failed` / `Something went wrong. Please try again.`
  - While purchasing, CTA shows spinner + label `Processing…` (Button `loading`).
- Restore (top-right link and footer link) -> `paywall_restore_started`; `adapty.restorePurchases()`; if `premium` access active -> `paywall_restore_success {signed_in}`, `startJourney()`, signed-out -> `/save-plan` (source `restore`), signed-in -> `/postbuy`; else Alert `No subscription found` / `We couldn't find an active subscription for this Apple ID.` + `paywall_restore_empty`; on error Alert `Restore failed` / `Please try again.` + `paywall_restore_failed`.
- **Post-purchase chain (acquisition):** `/paywall` -> `/save-plan` (hard, non-dismissable "Save your plan" sign-in gate: success pill `✓ Trial started — one last step`, H1 `Save your plan`, body `Your plan is built and your trial is active. Sign in to keep them — so they’re still here tomorrow, and on every device you use.`, 3 reason rows `🔒 Your plan, diary and subscription are saved to your account, not just this phone` / `📱 Log from any device and pick up exactly where you left off` / `🍎 Apple hides your email if you want — we never see a password`, official Sign in with Apple button; on success: sync intro draft to backend, `/billing/sync`, `refreshProfile`, then `router.replace('/postbuy')`) -> `/postbuy` (push-permission opt-in: pill `✓ Trial started — you’re all set`, H1 `Turn on reminders to hit your goal`, buttons to enable reminders / skip) -> `router.replace('/(tabs)')` (Today tab). Both `/save-plan` and `/postbuy` are fullScreenModal with gestures disabled.

### P.8 Reference remote configs (from `/Users/nikita/Documents/YumYummy/yumyummy-mvp/config/paywalls/`)
- `a.json` `A_clean_v3`: headline `Nutrition tracking that finally works`; laurels `★ {RATING} App Store`, `{USERS}+ trackers`, `✓ Verified data`; timeline (`Done` green/`Today`: `Full access unlocked`/`Day 2`: `We'll remind you 24h before any charge`/`Day 3`: `Trial ends — cancel anytime before`); plans yearly (badge `MOST POPULAR · 3 DAYS FREE`, rec tags, `price_style: trial_big`, display `3 days free trial` / `No payment due now. Then $7.50/mo billed annually at $89.99.`), monthly (`$9.99/mo`, `billed monthly`), weekly_upd (`$4.99/wk`, `billed weekly`); cta yearly `Start 3 days free now`, monthly `Continue — {PRICE_M}/mo`, weekly `Start now — {PRICE_W}/wk`; above_cta `✓ No payment due now · Cancel anytime`.
- `a_trial_all.json` `A_trial_all_v1`: same copy as FALLBACK_CONFIG (all plans carry trial; badge `BEST VALUE`; cta trial `Start 3 days free now`, others `Continue`).
- `b.json` `B_trial_designer`: headline `Design your trial`; laurels `★ {RATING} App Store`…; selector options above; `view_all_plans_label` `View all plans`; cta `Try Free for 3 Days` / `Continue — {PRICE_M}/mo` / `Start now — {PRICE_W}/week`; above_cta `✓ No payment due now · Cancel anytime in 2 taps`; (social quote `I didn't believe a 3-day trial could prove anything. It did.` / `Alex · −3.2 kg in 4 weeks` — not rendered).
- `b2.json` `B2_coffee_compare`: headline `Less than your morning coffee`; compare_card ☕ `A coffee` `$5.00` vs 🍏 `YumYummy / day` `$0.25`; plan subs `billed monthly · no trial`, `start today · no commitment`; cta as B.
- `c.json` `C_result_hook`: headline `Your result is ready`; result_card as in §P.6; `show_more_plans_label` `Show more plans`; cta as B.
- `m_single_trial.json` / `w_single_trial.json` `S_hero_v1`: headline `Nutrition tracking that finally works`; one plan (monthly / weekly_upd) with display_sub `Free for 3 days, then $9.99 per month. Renews automatically unless cancelled at least 24 hours before the end of the current period. Cancel anytime in your Apple Account settings.` (weekly: `$4.99 per week`); cta trial `Start my 3-day free trial`, monthly/weekly `Continue`; timeline with `Today` = `Full access unlocked — you pay nothing`; above_cta `✓ No payment due now · Cancel anytime`.

---------------------------------------------------------------------------
## ASSETS & FONTS

### Fonts (loaded by `theme/useAppFonts.ts` from `@expo-google-fonts/*`, under `node_modules`)
| family key | file | size (bytes) | used for |
|---|---|---|---|
| `Fraunces_400Regular` | node_modules/@expo-google-fonts/fraunces/400Regular/Fraunces_400Regular.ttf | 72,472 | (registered; serifRegular — not used in intro/paywall) |
| `Fraunces_600SemiBold` | .../fraunces/600SemiBold/Fraunces_600SemiBold.ttf | 72,504 | h1, h2, hero, display, macroValue (headlines & numbers) |
| `Fraunces_700Bold` | .../fraunces/700Bold/Fraunces_700Bold.ttf | 72,492 | why big stat (60px), kcal numerals (N1 36, N3 64, S10 34), loader %, mascot label |
| `Inter_400Regular` | .../inter/400Regular/Inter_400Regular.ttf | 342,408 | body, small |
| `Inter_500Medium` | .../inter/500Medium/Inter_500Medium.ttf | 342,892 | caption |
| `Inter_600SemiBold` | .../inter/600SemiBold/Inter_600SemiBold.ttf | 343,632 | title, bodyStrong, button labels |
| `JetBrainsMono_500Medium` | .../jetbrains-mono/500Medium/JetBrainsMono_500Medium.ttf | 114,920 | eyebrows/overlines, SourceBadge |
(All are Google Fonts: Fraunces, Inter, JetBrains Mono — free to use in a builder.)
Icons: `lucide-react-native` (lucide set): TrendingDown, Utensils, Dumbbell, Eye, CircleCheck, Check, ChevronLeft, Minus, Plus, ExternalLink, BookOpen, Camera, Mic, Keyboard, Zap (dead S11), Star, LockOpen, Bell, X. Default strokeWidth 1.5.

### Images (all under `/Users/nikita/Documents/YumYummy/yumyummy-mvp/mobile/assets/`)
| file | pixel size | bytes | used on |
|---|---|---|---|
| mascot/mood_stellar_t.png | 480x480 (transparent) | 71,852 | S1 welcome mascot (variant `welcome`, 64x64) |
| mascot/mood_great_t.png | 480x480 (transparent) | 58,372 | S10 fix thumbs-up mascot (104x104) |
| avatars/maria.jpg | 128x128 | 4,502 | N3 testimonial |
| avatars/denis.jpg | 128x128 (same set) | 3,841 | N3 |
| avatars/sara.jpg | | 4,693 | N3 |
| avatars/james.jpg | | 4,265 | N3 |
| avatars/priya.jpg | | 4,436 | N3 |
| avatars/tom.jpg | | 3,495 | N3 |
| avatars/elena.jpg | | 4,619 | N3 |
| avatars/chris.jpg | | 3,816 | N3 |
| avatars/sophie.jpg | | 3,930 | N3 |
| avatars/alex.jpg | | 4,063 | N3 |
Not used by these screens (present in same folder): mascot/mood_hungry_t.png (155,891), mood_okay_t.png (66,935), mood_quiet_t.png (60,680) (MascotBadge variant `hungry` exists but no intro screen uses it). No other raster images, illustrations or SVG files are used: all charts/rings are drawn in code (react-native-svg) and the welcome demo art is emoji (🥑🍳🍞, 🪑🚶🏃🏋️, etc.). The paywall uses no images at all (icons = lucide).

### Design tokens that matter (recap)
Background `#F7F1E6`; cards `#FFFDF9` with 1px/hairline `#E7DFD1` border, radius 16; selected = border `#B85A3A` + fill `#EFDFD1`; CTA = `#B85A3A` fill, white Inter 600 16, radius 12, height 54; eyebrows JetBrains Mono 11 uppercase letterSpacing 1.6 in `#9A4628`; headlines Fraunces 600 28/32 `#19150F`; body Inter 16/26; muted text `#6B6258`; faint text `#938A7C`; side gutter 20; card gap 16 (options) / 12 (list rows) / 8 (chips); paywall accent green `#16A34A` for "done"/"No payment due" lines (variants B/B2/C use `#2E6B4E`).

---------------------------------------------------------------------------
## Unresolved / caveats
1. Which paywall variant is live is configured in the Adapty dashboard (placement `main`); not readable from code. Repo has reference JSONs (§P.8) and the bundled FALLBACK_CONFIG (variant A). Builder should decide A vs S; S (single plan) and A are the most polished (B/B2/C are older and have weaker legal text and no unresolved-token guard).
2. Wheel pickers have no haptics/tap-select in the code read here; native feel to be matched by the builder's picker.
3. Exact rendered pixel widths depend on device (designed for ~390pt wide iPhones); no explicit screen-width constants exist except the S9 bar columns (86 wide) and chart viewBox (330x190).
4. The `/sources` citations screen (linked via SourcesLink from N1 and N3) was not specified in detail here (routes `router.push('/sources')`; content = grouped PubMed/FAO/IOM citations).
