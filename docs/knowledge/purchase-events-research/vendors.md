# Purchase events → AppsFlyer → Meta: what the vendor docs say (research, 17 Oct 2026)

Scope: options A–E for getting StartTrial / Subscribe to Meta without sandbox pollution, for YumYummy iOS (Adapty SDK v4 / react-native-adapty 4.2.1, react-native-appsflyer 6.18.0, no Meta SDK, UK, ~20 installs/day, ATT opt-in ≈16%).

How it was done: read-only. Adapty docs were fetched as `.md`. AppsFlyer KB pages were read in the built-in browser, because WebFetch returns 403. Meta Business Help came through the Meta Ads MCP `ads_get_help_article` (read-only). Apple docs came from the developer.apple.com JSON. Local SDK typings and app code were also read. Nothing was changed in Adapty, AppsFlyer or Meta.

Notation: every claim gives its source and a short quote of 15 words or fewer. **HYPOTHESIS** marks anything a source does not state directly.

---

## 1. AppsFlyer S2S in-app events (API 3, `api3.appsflyer.com/inappevent`)

**Attribution.** S2S events inherit the install's attribution through `appsflyer_id`, the same way SDK events do.
- [AF KB 207034486](https://support.appsflyer.com/hc/en-us/articles/207034486): `appsflyer_id` is used "to attribute the event to the original device and attributed media source."
- [AF KB 207034486](https://support.appsflyer.com/hc/en-us/articles/207034486): AppsFlyer populates S2S events with "install attribution values like, install time and media source."
- The event is attributed to the install. Lookback windows apply to the install, not to the event. Postbacks are limited by the per-partner **in-app event postback window**, which defaults to six months: "the default window is automatically set to six months" ([AF KB 208439256](https://support.appsflyer.com/hc/en-us/articles/208439256)).
- Organic trap: if S2S events arrive before the install is processed, which "generally takes 20-30 seconds or more, they may be marked as unattributed organic" ([207034486](https://support.appsflyer.com/hc/en-us/articles/207034486)). Adapty repeats this: "Expect first-launch purchases to report as organic" ([adapty appsflyer](https://adapty.io/docs/appsflyer)).

**Forwarded to Meta and other partners.** S2S events go out as in-app event postbacks, the same way SDK events do.
- Meta event mapping: an AppsFlyer event is the name "as received by AppsFlyer either from the SDK… or from server-to-server events." It also says "To add an SDK or server-to-server event to the list, click Add event" ([AF KB 207033826](https://support.appsflyer.com/hc/en-us/articles/207033826)).
- General postback config: the mapping list shows "events already reported by the SDK or from server-to-server events" ([208439256](https://support.appsflyer.com/hc/en-us/articles/208439256)).
- An S2S event is blocked from partners only if the sender sets `sharing_filter`: it "blocks the sharing of S2S events via postbacks/API with integrated partners" ([API ref](https://dev.appsflyer.com/hc/reference/s2s-events-api3-post)). Adapty's payload doesn't include it ([adapty appsflyer](https://adapty.io/docs/appsflyer), payload example).

**Differences from SDK events**

| Topic | What the docs say |
|---|---|
| Meta AEM requirements | `ip`: "Required to send event postbacks to Meta Aggregated Event Measurement (AEM)." The `idfv` field carries the same note ([API ref](https://dev.appsflyer.com/hc/reference/s2s-events-api3-post)). Same in [AF AEM 19228737402129](https://support.appsflyer.com/hc/en-us/articles/19228737402129): "Without these identifiers, the event won't be eligible for Meta Ads attribution in AEM." |
| ATT | `att`: "We recommend that you populate `att`… as it impacts which identifiers" are shared with partners ([API ref](https://dev.appsflyer.com/hc/reference/s2s-events-api3-post)). SDK events get this automatically; S2S events get only what the sender puts in. |
| IDFA | "Where available populate with the device IDFA" ([API ref](https://dev.appsflyer.com/hc/reference/s2s-events-api3-post)). Without a device ID: "The media source will receive the postback but without a device identifier." |
| Advanced Data Sharing | Applies to all events: "All events include installs, app opens, and in-app events." Meta may receive "IP addresses, anon_ids (if available), vendor_id, and user agents" ([19228737402129](https://support.appsflyer.com/hc/en-us/articles/19228737402129)). Adapty's S2S payload has no user agent or anon_id. **HYPOTHESIS:** this is no worse than today, because without a Meta SDK there is no anon_id for SDK events either (see `docs/knowledge/meta-aem-trial-optimization-2026-10.md` §1.2.5). |
| Device fields | Raw data fields are "populated exclusively with the values sent in the S2S call." App Version, Device Model, Language and others stay empty ([207034486](https://support.appsflyer.com/hc/en-us/articles/207034486)). This matters for validation rules (see §6). |
| Timestamps | to keep their eventTime, events must be "reported either on the day of the event, or the following day until 02:00 UTC"; anything older "is stamped with the arrival time" ([207034486](https://support.appsflyer.com/hc/en-us/articles/207034486)). Adapty itself "replaces `eventTime` with the current time for any event older than 26 hours" ([adapty appsflyer](https://adapty.io/docs/appsflyer)). Old events are re-dated, not dropped. |
| 200 OK | "you can get an OK response even though the event may not completely record" ([API ref](https://dev.appsflyer.com/hc/reference/s2s-events-api3-post)). Adapty adds that AppsFlyer "discards events whose `appsflyer_id` matches no real install." |
| Dedup | "S2S in-app events don't get deduplicated" ([AF KB 115005544169](https://support.appsflyer.com/hc/en-us/articles/115005544169)). See §6. |
| Plan | Adapty: AppsFlyer's "Zero package doesn't" accept S2S, and returns 403 ([adapty appsflyer](https://adapty.io/docs/appsflyer)). Our trial_converted and renewals already flow, so the plan accepts S2S (inference). |

## 2. Meta AEM via an MMP: does SDK-vs-S2S inside AppsFlyer matter?

- Meta lists integration channels as Facebook SDK, MMP or Conversions API: "ensure an event is only sent through one channel (either fb , mmp or capi)" ([Meta 251324098890446](https://www.facebook.com/business/help/251324098890446)).
- The two Meta errors are defined in terms of integrations, not of how the MMP received the event:
  - "Different integrations across multiple event types": the event "is sent through a different integration than your install event." The example given is Facebook SDK for installs and MMP SDK for purchases ([Meta 716239976391518](https://www.facebook.com/business/help/716239976391518)).
  - "Multiple integrations for the same event": "the app event is set up on multiple integrations." Fix: "select which integration you want to use" ([716239976391518](https://www.facebook.com/business/help/716239976391518), [3215014965459549](https://www.facebook.com/business/help/3215014965459549)).
- Both SDK-originated and S2S-originated AppsFlyer events reach Meta through the same AppsFlyer → Meta postback integration ([207033826](https://support.appsflyer.com/hc/en-us/articles/207033826), quoted in §1). **HYPOTHESIS (strong):** moving StartTrial from SDK to S2S inside AppsFlyer is invisible to Meta as an integration change. It triggers neither error, because install and StartTrial both still come from "MMP: AppsFlyer". No Meta doc mentions the SDK-vs-S2S origin inside an MMP.
- What changes for Meta is the **content** of each event: IP, IDFV, IDFA and ATT now come from Adapty's payload instead of the AppsFlyer SDK.
- **AppsFlyer "Meta Ads — AEM for iOS" (19228737402129)** ([link](https://support.appsflyer.com/hc/en-us/articles/19228737402129)):
  - In the AEM data-sharing section: for S2S events "Meta Ads requires both the IP address and the Identifier for Vendors (IDFV)."
  - Troubleshooting **Step 3**: "Every S2S event must include: IP address, IDFV (Identifier for Vendors)."
  - Other steps: Step 1 Advanced Data Sharing on. Step 2 "Events with masked IPs aren't eligible for AEM." Step 4 "Meta accepts a limited volume of events with missing or zeroed-out IDFAs." Step 5 postbacks set to "Send all (including organic)." Then "Set MMP traffic as the preferred connection method." Changes take "up to 2–3 days."
  - Meta lists one more cause: "ip data version isn't optimal… inconsistently sending ip addresses" ([716239976391518](https://www.facebook.com/business/help/716239976391518)).
- **Adapty's payload meets Step 3.** It sends `ip`, `idfv`, `idfa` and `att` on iOS ([adapty appsflyer](https://adapty.io/docs/appsflyer), parameter table).
- **Risk found in our code (affects A).** Adapty: "`att`… Adapty sends `0` when it has no value" ([adapty appsflyer](https://adapty.io/docs/appsflyer)). Adapty's ATT guide says the app "should send the authorization status to Adapty" with `updateProfile({ appTrackingTransparencyStatus })`, and adds "send this value as early as possible when it changes" ([adapty RN ATT](https://adapty.io/docs/react-native-deal-with-att)).
  - `mobile/src/analytics/attribution.ts` (`requestTrackingConsent`) never calls this; the only `updateProfile` calls set email and custom attributes.
  - **HYPOTHESIS:** under option A, every S2S StartTrial would carry `att=0`, losing the ~16% ATT-authorized share that SDK events carry today. Step 4's "ATE volume out of range" is exactly about that share. The fix is a one-line build change.

## 3. SKAN / AdAttributionKit conversion values

**S2S events can update the on-device CV.** Contrary to the usual assumption, AppsFlyer does this.
- [AF SKAN Conversion Studio 4403727223185](https://support.appsflyer.com/hc/en-us/articles/4403727223185):
  - "SKAN 4 and Custom: S2S is always on."
  - "Decode: S2S isn't suited to decode mode and isn't available."
  - "[Legacy] Revenue, conversion, and engagement modes: You must turn on S2S event recording." The toggle is "Record in-app events sent by server-to-server API." Fixed modes are "unavailable for new apps starting from 23/06/2024."
  - Mechanism: "AppsFlyer calculates the updated conversion value", then "the SDK is notified of the updated value." If the app is closed, "the server waits until the app is opened"; this "must occur before the expiry of the Activity Window." Otherwise: "If notification fails, the event is disregarded."
  - SDK: "Adopt the latest SDK version… No additional action is required by the developer."
  - Limitation: with user anonymization "you can't send events by S2S for that user."
- The SKAN solution guide says the same thing in its troubleshooting: "verify that Record in-app events sent by server-to-server API is on." It also asks for SDK 6.2.6+ ([360011420698](https://support.appsflyer.com/hc/en-us/articles/360011420698)). The two pages disagree on whether the toggle is always on in Decode mode (the guide says "Custom and Decode… always on", Conversion Studio says not available in Decode); irrelevant for SKAN 4.
- AppsFlyer's own server-generated purchase events (Receipt validation / ROI360) are documented as "Supported in SKAN Conversion Studio" ([42138855425297](https://support.appsflyer.com/hc/en-us/articles/42138855425297)). That is the same S2S path.

**What could still be lost with S2S events in SKAN**
- An S2S event that arrives while the app is closed counts only if the user reopens the app within the window ([4403727223185](https://support.appsflyer.com/hc/en-us/articles/4403727223185)).
- **HYPOTHESIS:** for our trial start this barely matters. The purchase happens in-app, mid-onboarding, and Adapty's S2S event arrives seconds later while the app is still open. Indirect evidence: Adapty and AppsFlyer both warn about the 20–30 s organic race, which implies near-real-time delivery.
- **HYPOTHESIS:** the notification latency (SDK poll interval) is not documented.

**Meta SKAN needs the event mapped in Meta postbacks** ([AF 360017095198](https://support.appsflyer.com/hc/en-us/articles/360017095198)):
- "If you don't map the events, Meta ads can't optimize and will only count installs."
- the event must be mapped in the in-app event postbacks: "Otherwise, the CV won't be updated on Meta ads."
- So a "SKAN-only, unmapped" client event (option D) would not reach Meta's SKAN decoding.

**Crowd anonymity and our volume**
- Apple: "the device may limit the data that SKAdNetwork sends in postbacks." Tier 1 gets only a "coarse value"; Tier 0 gets just "the hierarchical source identifier, with two digits". The tier depends on crowd size of source app, advertised app, country and source ID. Apple publishes no numeric thresholds ([Apple, multiple conversion windows](https://developer.apple.com/documentation/storekit/receiving-postbacks-in-multiple-conversion-windows)).
- AppsFlyer on Meta: "You need a minimum number of installs per campaign per day." Installs below it "show up with null Conversion Values", and "This threshold is not revealed by Meta" ([360017095198](https://support.appsflyer.com/hc/en-us/articles/360017095198)).
- **HYPOTHESIS:** at ~20 installs/day in total (the Meta share is lower), most Meta SKAN postbacks are Tier 0/1, with null or coarse CV. Singular's estimate (not an Apple source) is ~15 installs/day per SKAN campaign ID (`ref-singular-ios-learning`). So SKAN CV fidelity is mostly moot now, and the SDK-vs-S2S choice barely changes SKAN today. At 10× the fine CV in postback 1 becomes reachable.
- Postback delays: 24–48 h for the first postback, "24–144 hours for the second and third postbacks" ([Apple](https://developer.apple.com/documentation/storekit/receiving-postbacks-in-multiple-conversion-windows)).

## 4. Adapty → AppsFlyer integration (source: [adapty.io/docs/appsflyer](https://adapty.io/docs/appsflyer) unless noted)

**Payload and identifiers**
- One POST per event to `https://api3.appsflyer.com/inappevent/{app_id}`, "with the S2S token in the `authentication` header."
- Fields: `appsflyer_id`, `eventName`, `eventTime`, `eventValue` (stringified, with `af_content_id`, `af_order_id` = "The original transaction ID", `store_country`, `profile_country`, `af_revenue`, `af_currency`, `af_quantity`), `os`, `bundleIdentifier`, `customer_user_id`, `eventCurrency`, `ip`, `idfa`, `idfv`, `att` ("Adapty sends `0` when it has no value").
- No `app_version_name` and no user agent. Device Model, Category, Language, Operator, WIFI, App Version and App Name "have no S2S parameter."

**Event mapping**

| Adapty event | AppsFlyer name |
|---|---|
| Subscription started | `af_subscribe` |
| Subscription renewed | `af_subscribe` |
| Trial converted | `af_subscribe` |
| Trial started | `af_start_trial` |
| Non-subscription purchase | `af_purchase` |
| Everything else | Keeps its own name (e.g. `subscription_refunded`); any event can be renamed or turned off |

- **HYPOTHESIS, worth checking in raw data:** because renewals and trial conversions are already on and share `af_subscribe`, Meta's "Subscribe" already mixes first paid starts with conversions and renewals. That could explain 18 Subscribe vs 7 StartTrial in the dataset.

**Sandbox**
- "real purchases to the app whose token is in **Production**, test purchases" to **Sandbox**.
- "App Store review and TestFlight purchases are sandbox transactions", even on a production build.
- With the Sandbox field empty, troubleshooting lists "The purchase is a sandbox transaction and the Sandbox key is empty" as a cause of "Events don't reach AppsFlyer."
- **Confirmed:** with an empty Sandbox field, sandbox events are not delivered. The Event Feed shows them as failed; that is cosmetic noise.
- To report everything in one AppsFlyer app instead, "paste the same token into both fields."
- Adapty webhook events carry `environment`: "Possible values are `Sandbox` or `Production`" ([webhook fields](https://adapty.io/docs/webhook-event-types-and-fields)).

**Latency and timing**
- Store events come "through App Store Server Notifications" ([adapty events](https://adapty.io/docs/events)). If ASSN show **Delayed**, "Apple queues its notifications."
- Apple sends renewals and conversions in advance. Adapty forwards them "with the future `eventTime` unchanged" unless **Delay events with a future datetime** is on.
- S2S events take "about an hour" to show in the Activity dashboard; Live Events is sooner.
- **HYPOTHESIS:** `trial_started` fires as soon as the SDK reports the purchase to Adapty (seconds). No doc gives a figure; the 20–30 s organic warning is the indirect evidence.

**Qualified-trial-like options**
- Adapty → AppsFlyer has no "Qualified trial"; that feature is Adapty Attribution → Meta only, 1–24 h ([ua-facebook](https://adapty.io/docs/ua-facebook)).
- The AppsFlyer integration can instead receive the synthetic **Trial still active** (`trial_active`, timer 1 h – 90 days). It is sent only if the trial is still running and auto-renew is on ([adapty events](https://adapty.io/docs/events)).

**Revenue on trials**
- "Trial starts carry no revenue by default." **Send trial price** with a **Trial price percentage** adds a placeholder value.

**Refunds**
- "Refunds travel the same way, and AppsFlyer deducts them from campaign revenue." `af_revenue` is "Negative on refunds." The event name stays `subscription_refunded` unless renamed.

**Missing or changed `appsflyer_id`**
- "A profile without `appsflyer_id` produces no event." The Event Feed flags such profiles.
- "Await `Adapty.identify()`… An `appsflyer_id` set during that switch doesn't always survive it." From the call-order guide: initialize the MMP and "wait for their UID callbacks before calling `adapty.activate`" ([RN call order](https://adapty.io/docs/react-native-sdk-call-order)).
- Our flow (purchase on the anonymous profile, then `identify()`): "Transactional events… Appear only on the **parent profile** that made the purchase" ([how profiles work](https://adapty.io/docs/how-profiles-work)). **HYPOTHESIS:** later conversions and renewals keep the anonymous profile's `appsflyer_id`, as long as `setIntegrationIdentifier` ran before the purchase.

**Duplicates with SDK-logged events**
- "turn third-party event forwarding capabilities **off**" ([attribution-integration](https://adapty.io/docs/attribution-integration)).
- For migrations: "Running both simultaneously will produce duplicate events." Also "Pause large acquisition campaigns on migration day" ([migrate integrations](https://adapty.io/docs/migrate-integrations-to-adapty)).
- RevenueCat says the same: "Make sure to remove all client-side tracking of revenue" ([RevenueCat AppsFlyer](https://www.revenuecat.com/docs/integrations/attribution/appsflyer)).

## 5. Adapty Attribution (UA) → Meta web pixel

- **Sandbox filtering: not documented.** The pages read ([ua-facebook](https://adapty.io/docs/ua-facebook), [meta-create-campaign](https://adapty.io/docs/meta-create-campaign), [user-acquisition](https://adapty.io/docs/user-acquisition), [ua-metrics](https://adapty.io/docs/ua-metrics)) never mention sandbox.
- By default "Adapty only reports the events of users who came from one of your Meta campaigns." **Send all events** is "not recommended" ([ua-facebook](https://adapty.io/docs/ua-facebook)).
- **HYPOTHESIS:** sandbox and TestFlight testers are almost never probabilistically matched to a Meta click, so their events rarely reach the pixel. A tester who taps our own ad and then buys in TestFlight could leak one. Avoid sandbox purchases right after clicking our ads, and keep **Send all events** off.
- **Duplicate warning:** if an MMP also forwards `trial_started` or `trial_active`, "Meta receives the same trial more than once" ([ua-facebook](https://adapty.io/docs/ua-facebook)). In our setup the two streams go to different Meta datasets (app dataset 1010386435299572 vs web pixel 2857701897947614). So there is no "multiple integrations" flag on the app dataset, but trials are double-counted across campaigns and reports. Read the Sales campaign from Adapty and the app campaign from AppsFlyer, never summed.

## 6. AppsFlyer de-duplication and Validation Rules for the migration

**No cross-channel dedup**
- Dedup removes an identical event "from the same appsflyer_id less than 10 seconds beforehand." Then: "S2S in-app events don't get deduplicated" ([AF 115005544169](https://support.appsflyer.com/hc/en-us/articles/115005544169)).
- So SDK `af_start_trial` plus S2S `af_start_trial` count as two events in AppsFlyer, and as two postbacks to Meta.
- Partner-side dedup through `af_customer_event_id` is documented only "for metaweb_int, tiktokweb_int, snapweb_int, pinterest_int" ([115005544169](https://support.appsflyer.com/hc/en-us/articles/115005544169)). Those are web integrations, not the Meta app integration.
- AppsFlyer on SDK+SDK: "Meta ads doesn't de-duplicate in-app events that are reported from both SDKs" ([4410481130641](https://support.appsflyer.com/hc/en-us/articles/4410481130641)).

**Validation Rules** ([AF 115004703926](https://support.appsflyer.com/hc/en-us/articles/115004703926))
- Without Protect360, in-app event rules can use **Event name** and **App version** ("App version must only contain numbers").
- **Event source (SDK / Server-to-server)** is a Protect360-only condition: "Protect360 customers have additional condition options… Event source… Select either SDK or Server-to-server."
- In-app event actions: "Block attribution, but show in Protect360 data" or "Remove from AppsFlyer. Events will not show in the AppsFlyer platform at all."
- Tagged mode lets you test: AppsFlyer "flags matching installs and in-app events… but attribution isn't affected."

**Migration idea**
- A rule on Event name in (`af_start_trial`, `af_subscribe`) and App version ≤ 1.0.10, action Remove, would drop SDK events from old builds. Adapty S2S events have an empty App Version (§1), so they would likely survive.
- **HYPOTHESIS:** whether the rule reads the event's own (empty) app version and whether "≤" matches empty values is not documented. Run it in Tagged mode for a week first. Organic installs are null for some fields, and the doc warns that "Is empty" logic behaves unexpectedly on them.
- The cheaper alternative, per Adapty, is to accept a "negligible" overlap ([migrate integrations](https://adapty.io/docs/migrate-integrations-to-adapty)). New installs come from the App Store as 1.0.11, so only 1.0.10 users who buy later would duplicate.

## 7. Option C: AppsFlyer Receipt validation / ROI360 / Purchase Connector

**Two products**
- **Receipt validation** "is free of charge to all account plans" ([About Receipt validation](https://support.appsflyer.com/hc/en-us/articles/42136725767569)).
- **ROI360 store revenue** "is available only to customers on the ROI360 premium plan" ([42138855425297](https://support.appsflyer.com/hc/en-us/articles/42138855425297)). It adds renewals, refunds and net revenue, and needs ASSN plus the Purchase Connector or `validateAndLog`.

**Receipt validation events**
- Production: `af_ars_trial_started`, `af_ars_subscriptions_started`, `af_purchase`.
- Sandbox: `af_ars_sandbox_sdk` / `af_purchase_sandbox_sdk`, "Sandbox events have a revenue of 0" ([42137474889489](https://support.appsflyer.com/hc/en-us/articles/42137474889489)).
- They "are processed as S2S events", "can be sent via postbacks to partners", and "can be used in SKAN Conversion Studio" ([42136725767569](https://support.appsflyer.com/hc/en-us/articles/42136725767569)).
- Only initial purchases are covered. Renewals and conversions would still come from Adapty S2S.

**SDK and API**
- "Available from Android v6.17.5, iOS v6.17.8, and plugins v6.17.8 onward." The legacy method "will be shut down on September 7, 2026" ([42137474889489](https://support.appsflyer.com/hc/en-us/articles/42137474889489)).
- Our RN plugin 6.18.0 exposes `validateAndLogInAppPurchaseV2({ purchaseType, transactionId, productId })` and `setUseReceiptValidationSandbox()` (`mobile/node_modules/react-native-appsflyer/index.d.ts:105–113, 373–402`).
- Setup needs an App Store Connect In-App Purchase key (.p8, Key ID, Issuer ID) uploaded to AppsFlyer.

**Sandbox handling relies on a developer flag**
- `useReceiptValidationSandbox = true`, and "This code must be removed from your production builds" ([dev doc](https://dev.appsflyer.com/hc/docs/validate-and-log-purchase-ios)). Release checklist: "Your developers have all sandbox flags set to false" ([42137474889489](https://support.appsflyer.com/hc/en-us/articles/42137474889489)).
- Purchase Connector: a production purchase sent in sandbox mode means "your event will not be validated properly!" ([RN purchase connector](https://dev.appsflyer.com/hc/docs/rn_purchaseconnector)).
- **HYPOTHESIS:** what happens to TestFlight and App Review purchases on a production build (flag false) is undocumented. Either AppsFlyer reads `af_environment` from the store, or validation fails ("af_validated = false", blocked).

**Works with Adapty owning StoreKit?**
- `validateAndLog` only needs a transaction ID and product ID. Adapty exposes `vendorTransactionId` on the profile's subscription, so it is feasible (**HYPOTHESIS**, not documented by either vendor).
- The Purchase Connector auto-observes transactions ("activates a listener that automatically observes new billing transactions") and is ROI360-only: "The Purchase Connector is not supported in Receipt Validation" ([42136725767569](https://support.appsflyer.com/hc/en-us/articles/42136725767569)). Neither vendor documents coexistence with Adapty's observer, so avoid it.
- Duplicates: "do not send in-app purchase events, as this will result in duplicate revenue reporting" ([42138855425297](https://support.appsflyer.com/hc/en-us/articles/42138855425297)). With C, Adapty `trial_started` and `subscription_started` must stay off, and Meta must be mapped to the `af_ars_*` names.

## 8. Option B: detecting sandbox on device

**Apple APIs**
- `Transaction.environment` is iOS 16.0+: "The server environment that generates and signs the transaction." Values are `.production`, `.sandbox`, `.xcode` ([Apple](https://developer.apple.com/documentation/storekit/transaction/environment), [AppStore.Environment](https://developer.apple.com/documentation/storekit/appstore/environment)).
- iOS 15 has `environmentStringRepresentation` (iOS 15.0, deprecated in 16.0, back-deployed): "Use [environment] instead" ([Apple](https://developer.apple.com/documentation/storekit/transaction/environmentstringrepresentation)).
- `AppTransaction.shared` / `.environment` are iOS 16.0+: "The server environment that signs the app transaction." It "may require network connectivity" and throws if the user "isn't authenticated with the App Store" ([environment](https://developer.apple.com/documentation/storekit/apptransaction/environment), [shared](https://developer.apple.com/documentation/storekit/apptransaction/shared)).
- `Bundle.appStoreReceiptURL` is deprecated in iOS 18.0 / macOS 15.0: "Use AppTransaction.shared and Transaction.all from StoreKit.framework instead" ([Apple](https://developer.apple.com/documentation/foundation/bundle/appstorereceipturl)).
  - Apple never documented the `sandboxReceipt` filename check; it is folklore, so don't rely on it.
  - In sandbox "Receipts aren't initially present" until the first purchase.

**TestFlight and App Review**
- TestFlight: "Apps that you download from TestFlight always run in the sandbox environment" ([Apple sandbox testing](https://developer.apple.com/documentation/storekit/testing-in-app-purchases-with-sandbox)). "TestFlight also uses the sandbox environment to send notifications" ([ASSN environment](https://developer.apple.com/documentation/appstoreservernotifications/environment)).
- App Review: "The App Review team reviews apps in the sandbox" ([TN2413](https://developer.apple.com/library/archive/technotes/tn2413/_index.html); this is an archived note). Adapty confirms it for both (§4).

**No native code needed in our stack**
- `@adapty/core` (bundled with react-native-adapty 4.2.1) defines `AdaptySubscription.isSandbox`: "Flag indicating whether the subscription was purchased in a sandbox environment" (`mobile/node_modules/@adapty/core/dist/index.d.mts:997–1001`; also on non-subscriptions, line 905–908).
- So B is a JS guard: `profile.subscriptions[productId].isSandbox` from `makePurchase`'s result.
- **HYPOTHESIS:** the flag comes from Adapty's server-side validation of the same transaction, so it should agree with `Transaction.environment`. Verify once on TestFlight.

## 9. Do the vendors recommend an approach for "subscription platform + AppsFlyer"?

**Adapty: server-side, explicitly**
- renewals and conversions are "store events, with no app session for AppsFlyer's client-side SDK to report" ([adapty appsflyer](https://adapty.io/docs/appsflyer)).
- Turn other event forwarding off; one source per event ([attribution-integration](https://adapty.io/docs/attribution-integration)).

**AppsFlyer: no subscription-platform guidance**
- It frames S2S as being "for events that take place outside the app" ([207034486](https://support.appsflyer.com/hc/en-us/articles/207034486)).
- Its own subscription products are server-processed (S2S) events that it says work for postbacks and SKAN ([42136725767569](https://support.appsflyer.com/hc/en-us/articles/42136725767569), [42138855425297](https://support.appsflyer.com/hc/en-us/articles/42138855425297)).
- Its Meta AEM article documents S2S as supported, with IP and IDFV ([19228737402129](https://support.appsflyer.com/hc/en-us/articles/19228737402129)).
- No AppsFlyer page found recommends client-side events for SKAN. Conversion Studio documents S2S → CV with the "app must reopen within the window" caveat.

**RevenueCat (a peer, for comparison)**
- "remove all client-side tracking of revenue." Its sandbox key field is "required if you want the integration to trigger for sandbox purchases" ([RevenueCat AppsFlyer](https://www.revenuecat.com/docs/integrations/attribution/appsflyer)). This mirrors Adapty's empty-field behaviour.

**Meta**
- One channel per event; send "all media sources, including organic" ([251324098890446](https://www.facebook.com/business/help/251324098890446)).

---

## Options A–E compared

| Option | Sandbox filtered? | Meta AEM | Meta postbacks | SKAN CV | Duplicate risk | Needs app build? | Effort |
|---|---|---|---|---|---|---|---|
| **A** Adapty S2S `trial_started` → `af_start_trial`, `subscription_started` → `af_subscribe`, Sandbox token empty | **Yes, by Adapty**, incl. TestFlight and App Review (§4) | Same MMP integration (HYP §2). IP + IDFV sent. **`att=0` unless app sends ATT to Adapty** | Yes, same mapping, "Send all" | Yes in SKAN 4 / Custom; event lost if app not reopened within window (§3) | Only during migration from 1.0.10 users (no S2S dedup); mitigate via app-version rule (HYP) or accept | Events: no. **But add `updateProfile({appTrackingTransparencyStatus})` in 1.0.11** | Low: 2 Adapty toggles + 1 line of code |
| **B** Keep client SDK events, skip sandbox via `isSandbox` / `Transaction.environment` | Yes, if guard is right (Adapty flag or StoreKit 2, iOS 16+) | Same as today (SDK carries ATT and IDFA automatically) | Yes | Yes, immediate | None if Adapty `trial_started` / `subscription_started` stay off | Yes (re-add logging with guard) | Low–medium; client loses events if app is killed between purchase and log (HYP, rare) |
| **C** AppsFlyer Receipt validation `validateAndLogInAppPurchaseV2` | Only via a dev flag; TestFlight / App Review on prod builds undocumented (HYP) | Server-processed events; AEM IP/IDFV behaviour undocumented (HYP) | Yes (`af_ars_*`, re-map Meta) | Yes ("used in SKAN Conversion Studio") | High unless Adapty starts stay off; renewals still from Adapty | Yes, plus an ASC In-App Purchase key | Medium; ROI360 / Purchase Connector would be paid |
| **D** S2S for postbacks + separate client event only for SKAN, unmapped | Partly (client SKAN event still fires in sandbox, harmless for SKAN) | As A | As A | **Breaks Meta SKAN:** an unmapped event means Meta "will only count installs" (§3). Mapping it duplicates postbacks | High or broken | Yes | Medium; **unnecessary**, since S2S already updates CV |
| **E** Status quo (client events, no filter) | **No**: AppsFlyer can't tell; Meta can't delete received events | Same MMP integration; sandbox purchases inflate ATE=false volume | Yes | Yes | None now | Needs reverting the 1.0.11 removal | Zero, but keeps polluting StartTrial |

## Recommendation (evidence-based)

### Now (~20 installs/day)

**Option A**, shipped together with 1.0.11. The trial and paid starts already happen in the app and Adapty already validates them, so A adds no new code path for the events. It filters sandbox, TestFlight and App Review by Adapty's documented environment routing. It keeps one Meta integration (MMP) and keeps SKAN CV updates (SKAN 4 mode, S2S always on).

Steps:
1. **In 1.0.11 code** (needed for A, otherwise S2S events carry `att=0`): call `adapty.updateProfile({ appTrackingTransparencyStatus })` right after the ATT prompt resolves, and on launch whenever the status differs. **HYPOTHESIS:** this also lets Adapty refresh the IDFA. Verify it in the Event Feed payload (`att`, `idfa`, `idfv`, `ip`) on the first real purchase.
2. **In Adapty → AppsFlyer, on 1.0.11 release day:** enable `trial_started` (→ `af_start_trial`) and `subscription_started` (→ `af_subscribe`). Keep the Sandbox fields empty. Keep Send trial price off for now. Do not enable these toggles while 1.0.10 is the only live build; every purchase would double.
3. **In AppsFlyer:**
   - Confirm SKAN Conversion Studio mode is SKAN 4 or Custom (S2S always on). If it is a legacy fixed mode, turn on "Record in-app events sent by server-to-server API".
   - Keep the Meta mapping on `af_start_trial` / `af_subscribe` with "Send all (including organic)".
   - Optionally add a Validation Rule in **Tagged** mode: Event name in (`af_start_trial`, `af_subscribe`) and App version ≤ 1.0.10. Switch it to "Remove" only if the tags hit SDK events alone.
4. **Testing:** no sandbox purchases on 1.0.10 builds. TestFlight on 1.0.11 is safe once its client events are gone.
5. **Fallback:** if step 1's payload check shows `att` or `idfa` wrong and it can't be fixed quickly, use **Option B** (JS guard on `isSandbox`; Adapty starts stay off). It is the only other option that is clean on all columns.
6. Watch Meta Events Manager eligibility 2–3 days (AppsFlyer) to 7 days (Meta) after the switch.

### At 10× (~200 installs/day)

A still holds. Every documented constraint it has (window reopen, migration duplicates) shrinks relative to volume, and Adapty also owns conversions, renewals and refunds.

Add:
- Rename renewals away from `af_subscribe` (Adapty **Events names**) so Meta "Subscribe" means a first paid start. This matters before any value optimization (HYP §4).
- Consider `trial_active` (e.g. 24–48 h) as a separate, quality-trial event for Meta once StartTrial volume supports a second event (**HYPOTHESIS**; AEM doesn't support custom-event optimization for some objectives, so check per campaign type).
- Revisit SKAN once Meta installs per campaign clear the (unpublished) crowd-anonymity tiers; that is when fine CV starts paying off.
- Keep Adapty Attribution's pixel on a separate dataset and never sum it with AppsFlyer.

C (Receipt validation) offers nothing at either scale that A lacks, and its sandbox story is weaker. D is redundant. E keeps the pollution.

### Open items to confirm with vendor support (cheap)
1. AppsFlyer: how ATE is derived for S2S postbacks to Meta (from `att`? from `idfa` presence?).
2. AppsFlyer: whether validation rules on App version match S2S events whose app version is empty.
3. AppsFlyer: the SKAN S2S → SDK notification latency.
4. Adapty: whether the SDK refreshes IDFA after ATT without `updateProfile`.
