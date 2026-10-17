# Purchase events → AppsFlyer/Meta: internal material and current setup (A / B / D)

Researched 2026-10-17, read-only. Sources: Singular learning file (`YumYummy Meta Ads/docs/learning/singular-ios-measurement-learning.md`, 3,676 lines), `docs/knowledge/meta-aem-trial-optimization-2026-10.md`, `docs/knowledge/onboarding-v3-implementation-2026-10.md`, `docs/onboarding-v3-progress.md`, memory `project-meta-ads-ops.md` + `ref-singular-ios-learning.md`, mobile code on branch `onboarding-v3` vs `main` (main = commit 19a58d9 = live 1.0.10 build 61), backend `app/`.

Options under discussion:
- **A**: only Adapty → AppsFlyer S2S (`trial_started` / `subscription_started`), Sandbox field empty.
- **B**: keep client SDK `af_start_trial` / `af_subscribe`, skip sandbox with a native receipt/environment check.
- **D**: S2S for postbacks + a separately named client event used only for the SKAN conversion value.

---

## (a) Singular course: what bears on A / B / D

Quotes are from the auto-transcripts with ASR spellings normalised ("scan" → SKAN, "S two s" → S2S, "a m"/"a" → AEM, "singular" → Singular).

What the course does **not** say: it never covers sandbox purchases, and it never says whether Meta AEM treats SDK and S2S purchase events differently. It mentions "SDK versus S2S" once (Video 6). Everything below is about who sets the SKAN value, where Meta's optimisation signal comes from, thresholds, and double counting.

### SKAN conversion values: who sets them, what S2S can do
| Line(s) | Quote (≤15 words) | Bearing |
|---|---|---|
| 2094–2096 (V6) | "how you're integrated, what events you're able to track via SDK versus S2S" | The vendor treats SDK vs S2S as the first constraint on which events the SKAN model can use. |
| 2426–2430, 2453 (V7) | "the MMP will encode these as SKAN conversion values" | The MMP (AppsFlyer for us) sets the CV from its model configuration. The model lives in the MMP dashboard, not in our code. |
| 2748–2753 (V8) | "sending us revenue events regardless of SKAN just from the SDK" | Singular's SKAN revenue modelling needs SDK-sent revenue events. That is Singular's product. Whether AppsFlyer can use S2S events for the CV is a vendor question. |
| 2491–2499 (V7) | "confirm that they have received your conversion value mapping" | Option D (renaming the SKAN event) means re-sharing the mapping with Meta (Events Manager SKAN schema). |
| 2684–2689 (V8) | "at any given moment, you only have one SKAN model that is live" | Changing the AppsFlyer SKAN mapping changes it for every build at once, 1.0.10 included. |
| 2825–2828 (V9) | "you can lock the conversion value and get it faster" | CV locking exists (AAK and SKAN 4). Only relevant if B/D keep a client trial event. |
| 2982–2992 (V9) | "developer mode ... remove the time randomization, shorten the conversion windows" | AAK developer mode makes a device test of SKAN CV updates practical (see e). |

### Crowd anonymity: SKAN value at our volume
| Line(s) | Quote | Bearing |
|---|---|---|
| 2659–2660 (V8) | "about 15 installs over the last 24 hours per SKAN campaign id" | We have ~20 installs/day in total, and Meta may spread one campaign over several SKAN IDs. |
| 2668–2671 (V8) | "10 SKAN campaign IDs ... you need a larger number, it's about 150" | Same point: the threshold is per SKAN ID, not per Meta campaign. |
| 2632–2643 (V8) | "anonymity factor ... determined right there at that time when it was installed" | The tier is set once per install and applies to all three postbacks. |
| 2470–2475 (V7) | "instead of receiving values zero to 63, we'll only receive ... low, medium, high" | At a low tier, postback 1 is coarse-only, and postbacks 2–3 return nothing. |
| 2271–2276 (V6) | "in tier zero you don't get any conversion values" | Tier 0 means install-only postbacks. |
| 2182–2195 (V6) | "values for coarse, which are low, medium, and high all map to specific fine" | If B/D keep SKAN, map trial → coarse "high" so a tier-1 postback 1 still carries it. |
| 3652 (insights) | context line: "SKAN conversion values 100% null" (Sep 24) | Today the SKAN trial value that B/D would protect is empty anyway. |
| 3656 (insights #2) | "no trial/subscribe values, no matter how good the schema is" | Our own conclusion from September. |

### Meta: AEM vs SKAN, what drives optimisation
| Line(s) | Quote | Bearing |
|---|---|---|
| 3127–3138 (V10) | "you will be getting both attribution types regardless of what you set up" | The SKAN-vs-AEM choice only changes delivery. Our install campaign runs on AEM. |
| 3146–3150 (V10) | "AEM works well, if you wanna zoom in to the campaigns you're running on Meta" | AEM is Meta's optimisation layer and SKAN is the cross-channel check, so the AEM signal matters more than the SKAN CV. |
| 3253–3258 (V10) | "you don't have to set up a SKAN model" (for AEM campaigns) | An AEM campaign does not need a SKAN CV for trials, which weakens the main argument for D. |
| 3255–3258, 3168–3177 (V10) | "have the Singular SDK integrated with the relevant events" | Singular's checklist assumes SDK events. This is how a vendor frames it, not a statement that S2S events are ineligible. |
| 3274–3278 (V10) | "make sure that your app is available for AEM ... map out the relevant events" | Eligibility plus event mapping in Events Manager. Unchanged by A/B/D. |
| 2595–2600 (V8) | "if your app is not AEM eligible ... you can only run the SKAN campaign" | Without StartTrial AEM eligibility, SKAN is the only trial-optimisation route. That is the case for keeping D available. |
| 3222–3227 (V10) | "value optimization ... you're gonna wanna have a specific volume" | At our volume: installs or event optimisation only. |
| 318–320 (V1) | "probabilistic and modeled conversions are the way to go for the day-to-day" | Optimise on modelled (AEM) signal. SKAN is for validation. |
| 1024–1027 (V1) | "implement model conversions ... then use SKAN, AAK for validation" | Same point. |

### Double counting and reading the data
| Line(s) | Quote | Bearing |
|---|---|---|
| 1203–1207 (V2) | "you can't add it up or you would have overlap since the data is not de-duplicated" | In D, StartTrial would arrive through two methods (SKAN from the client, AEM from S2S). Never sum them. |
| 2329–2338 (V6) | "because there's siloed measurement, we're seeing duplication ... inflated organic numbers" | During a migration, AppsFlyer, Meta and Adapty totals will diverge. |
| 2038–2057 (V5) | "you're gonna see more organic data" / SAN installs look lower | S2S events inherit the install's AppsFlyer attribution, so organic inflation stays the same under A. |
| 1109–1115 (V2) | "less than 10% chance of a two-sided ATT consent" | ATT drives user-level signal. Our rate is 16%, and the transport choice does not change it. |

### Mistakes to avoid (process)
| Line(s) | Quote | Bearing |
|---|---|---|
| 368–376 (V1) | "be deliberate with optimization actions, because the SKAN postback slow down the learning" | The next build changes onboarding, paywall, ATT placement, the ATT wait (60→180 s) **and** the event transport at once. A drop in Meta StartTrial will not be attributable to any single change. |
| 368–371 (V1) | "understand how the model is built ... based on assumptions and partial signals" | Know which path carries each event before reading Meta columns. |
| 950–958 (V1) | "give it time to be able to get the models to train" | After the cutover, don't judge Meta trial optimisation for a week or more. |
| 2486–2487 (V7) | "start simple, see what works, and then add complexity" | Argues against D now: D is the most complex option. |

---

## (b) Our prior research and memory: facts and open items

Facts (from `meta-aem-trial-optimization-2026-10.md` = "AEM doc", line numbers):
- Root cause of StartTrial AEM ineligibility (AEM doc L23): almost no StartTrial events carry IDFA/ATE=true, events without IDFA have no Install ID (`anon_id`), and volume is tiny (7 events in 28 days, mostly sandbox). **The transport (SDK vs S2S) was not identified as a cause.** Switching to A does not fix eligibility. A, B and D each fix sandbox pollution only.
- `anon_id` is generated by the Meta SDK. The AppsFlyer iOS SDK binary reads `com-facebook-sdk-PersistedAnonymousID.json`, so without the Meta SDK there is no anon_id on any path (L38, a hypothesis).
- AppsFlyer AEM troubleshooting step 3: S2S events must carry the device IP and IDFV (L28, L100). This is the condition A must meet.
- AppsFlyer → Meta integration: Advanced Data Sharing ON. Postbacks af_start_trial→StartTrial, af_subscribe→Subscribe and af_complete_registration→fb_mobile_complete_registration are all set to "All media sources, including organic", with values and revenue (memory Oct 7).
- Sandbox cannot be filtered without a build: AppsFlyer validation rules can't isolate it, postback conditions can't, test devices don't exclude postbacks, and Meta can't delete events it has received (AEM doc L60).
- Meta's SKAN schema in Events Manager: conversion_config, SKAN_V4, partner AppsFlyer, ranks StartTrial + Subscribe + af_attribution_flag over the 3 windows (memory Oct 7). The AppsFlyer-side SKAN/Conversion Studio config itself was never confirmed ("SKAN conversion schema not confirmed", memory Sep 11).
- SKAN trial optimisation was judged not viable at ~4 installs/day (CV null) (AEM doc L75). A "SKAN probe" was paused on Oct 8 (memory).
- Numbers: AppsFlyer, 30 days to Oct 7: af_start_trial was 2 Facebook Ads + 5 organic (mostly sandbox); af_subscribe was 2 Facebook Ads + **17 organic**. Meta dataset (26–28 days): StartTrial 7, Subscribe 18, CompleteRegistration 7. Hypothesis (unverified): 17 organic af_subscribe from the founder's testing alone is a lot. Either many direct sandbox purchases, or Adapty S2S sandbox renewals reaching AppsFlyer as af_subscribe (only possible if the Adapty→AppsFlyer Sandbox field is not empty, or if renewals are named af_subscribe). Check the raw data's event source.
- Meta CompleteRegistration (7) = StartTrial (7). In the acquisition flow, sign-in comes **after** the purchase (`save-plan.tsx` is the post-purchase gate), so client `af_complete_registration` already fires almost only after a purchase. It is sandbox-tainted the same way (TestFlight sign-ups).
- Adapty Attribution Sales campaign (web pixel 2857701897947614): Trial started→StartTrial and Subscription started/Trial converted→Subscribe, sent server-side by Adapty UA. Its sandbox handling is not documented (AEM doc L115). This is a separate dataset from the app dataset 1010386435299572. It was live on Oct 10; current status unknown.
- Decisions already written down: V3 implementation doc L155–157 chooses A ("one source, sandbox is cut off by the key"), with B as the fallback if on-device SKAN values are needed. Progress doc L100/L110 says client events were removed and "Nikita decides on Oct 17; enable in Adapty before release". Open: what happens to the install if the app is killed before ATT (L111, a device test).
- Release type is MANUAL: Nikita presses Release in App Store Connect. The cutover moment is therefore controllable.

Open items carried over: AppsFlyer ticket (anon_id in postbacks, share of ATE=true on af_start_trial, plugin issue #619 `advertiserIdEnabled=false` at att_status=3 on 6.15–6.17, not confirmed fixed in 6.18.0) and the Meta ticket with the dataset ID. Neither has an answer on record.

---

## (c) Event paths: 1.0.10 (live) vs onboarding-v3 (next build)

### Identifiers and timing (both builds unless noted)
- `bootstrapSdks()` (`mobile/src/analytics/bootstrap.ts` L33–54) runs on **every launch**:
  1. `initAttribution()` (5 s cap) → AppsFlyer `initSdk` with `timeToWaitForATTUserAuthorization` (60 s in 1.0.10, **180 s** on the branch, `attribution.ts` L65/L298)
  2. `getAppsFlyerId(5000)`
  3. `activateAdapty()`
  4. `setIntegrationIdentifier('appsflyer_id', uid)` on the **current** Adapty profile (L46–49). Before sign-in that profile is anonymous, and the purchase lands on it.
- Second chance: `handleConversionData` (`attribution.ts` L150–151) sets `appsflyer_id` again when install conversion data arrives. It runs once per process, after the install is sent (that is, after ATT is answered or the timer expires).
- After sign-in: the branch only (`state/auth.tsx` L91–95) re-sets `appsflyer_id` right after `identifyAdapty()`, because identify may switch profiles. In 1.0.10 the identified profile gets it only on the next launch's bootstrap.
- So the `appsflyer_id` **is set before the purchase** in the normal flow: bootstrap at launch, then the paywall (after the loader/ATT) minutes later. It is missing only if `getAppsFlyerUID` did not answer within 5 s **and** conversion data had not arrived by purchase time. Adapty silently can't send S2S events for a profile without it.
- AppsFlyer CUID (`setCustomerUserId`) is set only after sign-in, so it is post-purchase (`auth.tsx` L67).
- Adapty activate: `adaptyAttributionEnabled: true`, IDFA collection not disabled (`billing/adapty.ts` L90–97).

### SKAN / AAK configuration
- `app.json` (identical on main and branch apart from formatting) and the local `ios/YumYummy/Info.plist`:
  - `NSAdvertisingAttributionReportEndpoint` and `AdAttributionKit.AttributionCopyEndpoint` = `https://appsflyer-skadnetwork.com/`: postback copies go to AppsFlyer.
  - 11 `SKAdNetworkItems`, including Meta's `v9wttpbfk9` and `n38lu8286q`.
- The app never calls `updatePostbackConversionValue` and has no `disableSKAD` or SKAN code. **The AppsFlyer SDK 6.18.0 manages SKAN registration and CV updates by itself**, from its dashboard model.
- `react-native-appsflyer` plugin: `shouldUsePurchaseConnector: false`. AppsFlyer has no auto-IAP logging. `ios/` is not in git (local prebuild).
- Once client purchase events are gone (branch), the SDK sees on-device only:
  - install/first open
  - sessions
  - `af_complete_registration`, which fires after sign-in, i.e. after purchase, and only for new accounts.

  If the SKAN model encodes only StartTrial/Subscribe (+ af_attribution_flag), the CV can never carry a purchase from the next build, unless AppsFlyer can feed S2S events into the SKAN CV (vendor question). In practice CVs are null today.

### Path list, build 1.0.10 (live)
```
Purchase (paywall.tsx afterPurchaseSuccess, code / flow / flow-offer renderers; main L228-256)
├─ client → AppsFlyer SDK: af_start_trial (trial) | af_subscribe (direct, af_revenue)
│     ├─ prod AND sandbox/TestFlight (no env check; isAppsFlyerConfigured = key present, no QA guard)
│     ├─ → AppsFlyer → Meta app dataset 1010386435299572: StartTrial / Subscribe ("all incl. organic")
│     └─ → on-device SKAN CV via AppsFlyer model
├─ Adapty server (Apple receipt) → Adapty → AppsFlyer S2S: trial_converted, renewals, refunds,
│     expirations (per code comment; trial_started + initial purchase OFF — dashboard not verified)
├─ Adapty → PostHog (server, environment=Sandbox|Production)
├─ Adapty → our webhook /adapty (app/api/adapty_webhook.py): entitlement only; sandbox ignored (L159-168);
│     fires nothing to Meta/TikTok/AppsFlyer (app/billing/adapty.py docstring L10-12)
├─ Adapty UA (if Sales campaign live) → web pixel 2857701897947614: StartTrial / Subscribe
└─ client → PostHog: paywall_purchase_success
Sign-in that created an account → client af_complete_registration → Meta fb_mobile_complete_registration
```

### Path list, branch onboarding-v3 (next build)
```
Purchase (paywall.tsx L312-345): NO AppsFlyer call (comment L327-328); same 3 renderers + V3 + offer
├─ Adapty → AppsFlyer S2S: trial_started + subscription_started only once enabled in Adapty dashboard
│     (Sandbox field empty → sandbox/TestFlight/App Review not delivered) → AppsFlyer → Meta
├─ Adapty → AppsFlyer S2S: trial_converted, renewals, refunds, expirations (unchanged)
├─ Adapty → PostHog / our webhook / Adapty UA pixel: unchanged
└─ client → PostHog: paywall_purchase_success (+ qa_build tag)
Client AppsFlyer events left: af_complete_registration only (auth.tsx L76-78) + SDK install/sessions.
AppsFlyer off in QA builds (IS_QA_BUILD = __DEV__ || EXPO_PUBLIC_QA_BUILD=1, attribution.ts L74-76).
NOT off in TestFlight (production profile) or preview/ad-hoc (eas.json QA_BUILD "0"):
  those still send installs + af_complete_registration to AppsFlyer/Meta.
```

### Backend (repo root)
- `app/core/meta_capi_client.py` exists. It sends CompleteRegistration / StartTrial / Subscribe with `action_source="website"` to `settings.meta_pixel_id` (the browser/LP pixel).
- It is called only from the Telegram/LP funnel:
  - `app/api/billing.py` L109 (`/billing/trial/start`, the bot's)
  - `app/billing/service.py` L192 (`apply_subscription_payment`: Telegram Stars / Paddle / Gumroad / admin)
  - `app/main.py` L1786 (bot `/start`)
- The iOS app's `/billing/trial/start` (`app/api/app_api.py` L863, a dev fallback when Adapty is unconfigured) fires nothing.
- There is no AppsFlyer code anywhere in `app/` or `scripts/`. **The backend cannot create iOS app-dataset events.**

### Other app → AppsFlyer touches
- `setCustomerUserId` after sign-in.
- `onInstallConversionData` / `onDeepLink` listeners (read-only).
- `getAppsFlyerUID`.
- Nothing else logs AppsFlyer events (grep: only `auth.tsx` L77 on both branches; main also has `paywall.tsx` L246).

---

## (d) Risks per option for this app

### Shared, any option
- **Confounding.** Transport, ATT placement/timer, onboarding and paywall all change in one build (Singular L368–376). Plan to read the transport change from AppsFlyer/Adapty event counts, not from Meta CPA.
- **TestFlight/preview builds still send installs and registrations** to AppsFlyer → Meta (organic). `IS_QA_BUILD` does not cover them.
- **Dashboard-level switches are global.** Adapty integration toggles, AppsFlyer postback mappings and the SKAN model apply to 1.0.10 the moment they change.
- **Possible 3rd/4th path to Meta.** It is ambiguous whether Adapty → Facebook Ads (app events via Graph API) is ON: the old runbook L19 says "enable", while AEM doc §6 says "off". If it is ON, Meta gets purchase events twice ("multiple integrations for the same event", AEM doc L65). The Adapty UA web pixel is a separate dataset, so its StartTrial must not be summed with app-dataset StartTrial in reports.

### A: Adapty → AppsFlyer S2S only
- **Migration double count (main risk).** Turning on `trial_started` / `subscription_started` in Adapty affects 1.0.10 immediately. While 1.0.10 is still in use, every production purchase on 1.0.10 then gets client af_start_trial **and** S2S trial_started. If both map to StartTrial, that is 2 StartTrial per trial in Meta, and AppsFlyer does not dedupe SDK vs S2S (to verify). Flip too late and 1.0.11 trials reach nobody. Mitigations:
  - flip exactly at Release time (MANUAL release); residual doubles then come only from 1.0.10 users buying after the release, such as late or after-cancel purchases;
  - or give the S2S event a distinct name, map *that* name → StartTrial in AppsFlyer→Meta postbacks, and remove the `af_start_trial→StartTrial` mapping at the same moment. Meta then gets one event per production purchase from both builds. This also stops 1.0.10 sandbox pollution in Meta **without a build**, and 1.0.10's client event keeps feeding SKAN (D-like behaviour for free). The renaming must be supported on both sides (vendor check).
- **AEM signal quality could get worse silently.** If Adapty's S2S payload lacks device IP, IDFV or ATT/IDFA, Meta matching gets worse than the SDK route (AEM doc L28 step 3). This could push StartTrial further from eligibility while counts look right in AppsFlyer.
- **Missing `appsflyer_id`.** Events from profiles without it are dropped silently: the 5 s UID race plus conversion data that has not arrived. In 1.0.10, trial_converted/renewals on an identified profile that switched may be missing until the user reopens the app (the branch fixes this).
- **SKAN.** No purchase value on-device from 1.0.11. Today's cost is ~0 (CV null), but SKAN-optimised trial campaigns become impossible later unless AppsFlyer supports S2S→SKAN.
- **Latency/order.** S2S must reach AppsFlyer after the install is recorded. That holds in the V3 flow (ATT before the paywall), but the kill-before-ATT behaviour is untested (progress L111).
- **Good.** Sandbox, TestFlight and App Review are excluded by an empty Sandbox field. Coverage includes purchases the app never sees (Ask-to-Buy/`pending` results, interrupted purchases, app killed after StoreKit success). Classification (trial vs paid) is Apple's, not the client's. Adapty analytics are unaffected.

### B: client events + native sandbox check
- **Zero migration change.** Production events are identical in 1.0.10 and 1.0.11, and the Adapty toggles stay OFF. The only difference is that sandbox stops in 1.0.11; 1.0.10 testers still pollute until they upgrade.
- **Native work.** Needs a native module (precedent: `mobile/modules/widget-status`), so it is part of a full build. The check must work on iOS 15.1+:
  - StoreKit 2 environment is iOS 16+;
  - the `sandboxReceipt` receipt-URL fallback is deprecated;
  - TestFlight, ad-hoc preview and App Review must all read as sandbox.

  If the check fails open, pollution returns silently. If it fails closed, real trials are lost silently.
- **Coverage gaps the client can't see:** `pending` results (Ask-to-Buy), purchases finishing after the app was killed, and renewals/conversions (already S2S). The client trial/paid flag relies on Adapty's eligibility in `subscription.offer`.
- **Good.** SDK events carry the device's own IDFA/ATT/IDFV/IP, the path AppsFlyer documents for AEM. SKAN CV keeps receiving trial/subscribe on-device.
- **Risk of later drift:** if someone enables Adapty trial_started "to be safe", trials double.

### D: S2S postbacks + separately named client SKAN event
- **Most moving parts.** Adapty toggles ON, a new client event, an AppsFlyer SKAN model remap, a Meta SKAN schema update (Singular L2491–2499), and the new event kept **out** of Meta postbacks. If the event is accidentally mapped (or AppsFlyer has a "send all events" option), it becomes another StartTrial source.
- **Changes reach 1.0.10 too.** The SKAN model remap affects 1.0.10 at once (one live model, L2684–2689): 1.0.10's af_start_trial stops encoding trials unless both are mapped.
- **Two sources for the same Meta event name.** SKAN-from-client and AEM-from-S2S can't be summed (L1203–1207). How Meta treats "StartTrial" in a SKAN schema fed by event X while AEM StartTrial comes from event Y is unknown ("different integrations across event types", AEM doc L65).
- **Little benefit at current volume.** CVs are null at tier 0/1 (L2659–2671, L3656), and the campaigns are AEM (L3253–3258).
- **Sandbox is harmless for SKAN.** TestFlight installs have no ad touch, so no postback. But the client event still pollutes AppsFlyer reports unless B's check is added.
- Inherits A's S2S risks (payload identifiers, appsflyer_id, migration).

---

## (e) Open questions that need a device test or vendor support

Vendor (AppsFlyer / Adapty / Meta):
1. Adapty → AppsFlyer S2S payload: does it include device IP, IDFV, IDFA (when authorised) and ATT status, and does AppsFlyer forward ATE/IP/IDFV to Meta for S2S-sourced events? (Decides whether A is AEM-neutral.)
2. Can AppsFlyer use S2S in-app events in the SKAN/AAK conversion value, or only on-device SDK events? Which Conversion Studio model is live (AppsFlyer-managed or Meta-shared SKAN_V4 schema)?
3. Does AppsFlyer dedupe an SDK af_start_trial and an S2S event for the same purchase? If not, what is the recommended cutover?
4. Event names: can Adapty send custom names to AppsFlyer, and can AppsFlyer's Meta postbacks map a non-standard name (e.g. an S2S-only name) to StartTrial / Subscribe?
5. Current Adapty → AppsFlyer toggles, names and Sandbox field: is trial_started really OFF, is the Sandbox field empty, and what is trial_converted named (af_subscribe?)? Is Adapty → Facebook Ads (Graph API) OFF?
6. Meta: does a StartTrial arriving via AppsFlyer S2S count as the same MMP integration as the install, and does a SKAN-schema change pause or reset campaigns?
7. AppsFlyer → Meta: is there any "send all in-app events" option that would forward an unmapped D event?

No-build checks (dashboards/raw data, read-only):
8. AppsFlyer raw in-app events, 30 days: af_start_trial / af_subscribe split by event source (SDK vs S2S), by `att`, and by app version. This explains the 17 organic af_subscribe.
9. Three-way count for the same window: Adapty production trial_started vs AppsFlyer af_start_trial vs PostHog `paywall_purchase_success has_trial`. This measures how much the client misses or adds (sandbox) before choosing A or B.
10. Adapty event feed: integration delivery status for AppsFlyer events (failures because `appsflyer_id` is missing), plus the share of recent profiles that carry `appsflyer_id`.
11. Was any EAS Update (OTA) published to runtime 1.0.10? Note: an OTA that strips client events from 1.0.10 would not cover first-session purchases, because `fallbackToCacheTimeout: 0` means the update applies on the next launch, and most trials happen in the first session.

Device tests (TestFlight / AppsFlyer `isDebug`):
12. B: does the native check return sandbox on TestFlight, ad-hoc (preview profile), a sandbox account on a store build, and an iOS 15 device? Does it return production on a real App Store purchase?
13. A: TestFlight purchase → Adapty event feed shows sandbox and **no** AppsFlyer delivery. Production purchase → AppsFlyer raw data shows the S2S event with correct appsflyer_id, IP and IDFV, and Meta Events Manager shows StartTrial from the MMP within 2–3 days.
14. `getAppsFlyerUID` timing during the 180 s ATT wait: does the UID come back within bootstrap's 5 s, so `appsflyer_id` is on the anonymous profile before purchase?
15. Kill the app before the ATT prompt, relaunch, buy: is the install recorded before the S2S event arrives, and is the event attributed or dropped? (Already open, progress L111.)
16. D/B SKAN: with AAK developer mode (Singular L2982–2992) and AppsFlyer debug, does the CV update on-device after the client trial event, and to which value (fine and coarse)?
