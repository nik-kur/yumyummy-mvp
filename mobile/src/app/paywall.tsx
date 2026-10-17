/**
 * Paywall screen.
 *
 * Adapty is the switchboard: each A/B arm on placement `pw_main` is a flow
 * whose remote config picks the renderer (`config/paywallArms.ts`):
 *   1. `native` — the V3 paywall in code (`components/pw`, screens 17–19):
 *      B1 → B2 → B3 photo plans, or the P1 demo clip → B2 → light plans. It
 *      buys the arm flow's own products (`getPaywallProducts(flow)`) and logs
 *      the show on that flow (`logShowFlow`), so code and builder arms compare
 *      inside one Adapty A/B test.
 *   2. `flow` — the arm's Flow & Paywall Builder screens, drawn by the SDK via
 *      `AdaptyFlowView`; purchases, restore and the StoreKit sheet are the SDK's.
 *   3. `legacy` — the pre-V3 code paywall from the `main` placement's remote
 *      config (`PaywallRenderer`/`Variant*`), kept as a switchable fallback.
 * With no answer from Adapty the code default (V3 `b3_joe`) shows, and its
 * plans step offers a retry instead of cards.
 *
 * After the customer cancels the App Store sheet, the `pw_after_cancel` arm
 * answers the same way: our offer screen (20) or the arm's builder flow.
 *
 * Two audiences reach this screen:
 *   - Acquisition (signed OUT): intro quiz → plan reveal → here. The purchase
 *     lands on an anonymous Adapty profile; we record a pending-purchase marker
 *     and hand off to /save-plan, the sign-in gate that attaches the purchase to
 *     the freshly created account. Nothing here may call an authenticated API.
 *   - Existing account (signed IN): the launch router's hard gate for a lapsed
 *     subscription, or Profile ("Manage plan" / "See plans") with
 *     `?dismissable=1`. Both go straight to the plans. Purchase → /success
 *     (22) → Today; a signed-out purchase → /success → /save-plan (23).
 *
 * Hard paywall by default: no close button, gesture-dismiss disabled — exits
 * only via successful purchase or restore. Only the Profile entry gets a close
 * button: an existing member must always be able to leave.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { View, Pressable, StyleSheet, Alert } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { X } from 'lucide-react-native';
import { adapty, AdaptyFlowView } from 'react-native-adapty';
import type {
  AdaptyFlow,
  AdaptyPaywallProduct,
  AdaptyProfile,
  AdaptyPurchaseResult,
  CreateFlowViewParamsInput,
} from 'react-native-adapty';

import { PaywallRenderer } from '@/components/paywall/PaywallRenderer';
import { VariantB } from '@/components/paywall/VariantB';
import { VariantB2 } from '@/components/paywall/VariantB2';
import { VariantC } from '@/components/paywall/VariantC';
import { VariantSHero } from '@/components/paywall/VariantSHero';
import { OfferScreen } from '@/components/pw/OfferScreen';
import { V3Paywall } from '@/components/pw/V3Paywall';
import { PwLoading } from '@/components/pw/V3Screens';
import { useAuth } from '@/state/auth';
import { loadDraft, type IntroDraft } from '@/state/introDraft';
import { startJourney } from '@/state/journey';
import { savePendingPurchase, type PendingPurchase } from '@/state/pendingPurchase';
import {
  activateAdapty,
  getAdaptyProfileId,
  hasActivePremium,
  isAdaptyConfigured,
  waitForAdaptyIdentify,
  waitForAppleAdsAttribution,
  ADAPTY_PLACEMENT_AFTER_CANCEL_FLOW,
  ADAPTY_PLACEMENT_MAIN,
  ADAPTY_PLACEMENT_PAYWALL_FLOW,
  PREMIUM_ACCESS_LEVEL,
} from '@/billing/adapty';
import { handleFlowPermissionRequest, trackFlowAnalytics } from '@/billing/flowBridge';
import {
  freeTrialPhase,
  parseRemoteConfig,
  resolveVariant,
  FALLBACK_CONFIG,
  type PlaceholderValues,
} from '@/billing/paywallConfig';
import { sortPlans, trialDays } from '@/billing/v3Pricing';
import { IS_QA_BUILD } from '@/config/buildFlags';
import { getOnboardingConfig, getOnboardingContent } from '@/config/onboardingConfig';
import { resolvePaywallArm, type ResolvedArm } from '@/config/paywallArms';
import { qaOverrides } from '@/config/qa';
import type { ConfigSource, PaywallArmConfig } from '@/config/types';
import { fmtKg, fmtStLb } from '@/onb/plan';
import { enableRemindersAfterPurchase, scheduleTrialEndingReminder } from '@/notifications/scheduler';
import { track } from '@/analytics/posthog';
import { addBreadcrumb, captureException } from '@/analytics/sentry';
import { colors, radius, space } from '@/theme/tokens';
import * as api from '@/api/endpoints';

/**
 * `loading` → spinner; `v3` → our V3 paywall; `flow` → builder flow; `ready` →
 * legacy code paywall from remote config; `fallback` → legacy bundled config,
 * purchases disabled.
 */
type Phase = 'loading' | 'v3' | 'flow' | 'ready' | 'fallback';

/** Who drew the screen a purchase came from — PostHog `renderer`. */
type Renderer = 'code' | 'v3' | 'v3_offer' | 'adapty_flow' | 'adapty_flow_offer';

/** Cap each fetch so a slow network shows the fallback instead of a blank screen. */
const PAYWALL_LOAD_TIMEOUT_MS = 5000;

/** How long to keep waiting for Apple Ads attribution before giving up on it. */
const APPLE_ADS_ATTRIBUTION_TIMEOUT_MS = 20000;

/**
 * What Sentry needs to tell a declined card from a store outage: Adapty wraps every
 * StoreKit failure as "#1006 productPurchaseFailed", and the original error only lives
 * in `detail` (seen live 2026-10-06: one event, no cause). Spread into the event context.
 */
function adaptyErrorContext(error: unknown, extra: Record<string, unknown> = {}): Record<string, unknown> {
  const e = error as { adaptyCode?: unknown; detail?: unknown; localizedDescription?: unknown; message?: unknown } | null;
  return {
    ...extra,
    adapty_code: e?.adaptyCode ?? null,
    adapty_detail: typeof e?.detail === 'string' ? e.detail.slice(0, 2000) : e?.detail ?? null,
    message: e?.localizedDescription ?? e?.message ?? String(error),
  };
}

/** The after-cancel offer is prefetched in the background; never wait longer than this for it. */
const OFFER_LOAD_TIMEOUT_MS = 8000;

/** The after-cancel offer, as its `pw_after_cancel` arm decided. */
type OfferState =
  | { kind: 'flow'; flow: AdaptyFlow }
  | {
      kind: 'native';
      flow: AdaptyFlow;
      config: PaywallArmConfig;
      product: AdaptyPaywallProduct;
      source: ConfigSource;
    };

function offerVariant(o: OfferState): string {
  return o.kind === 'native' ? o.config.variant : o.flow.variationName ?? o.flow.variationId;
}

/**
 * Resolve the offer arm and everything it needs, so a cancellation is answered
 * at once. Our screen (20) says "free", so it needs a product this customer can
 * still get a trial on; without one there is no honest offer to show.
 */
async function prefetchOffer(): Promise<OfferState | null> {
  const arm = await resolvePaywallArm(ADAPTY_PLACEMENT_AFTER_CANCEL_FLOW, 'offer', OFFER_LOAD_TIMEOUT_MS);
  if (!arm.flow) return null;
  const builder = arm.config.render !== 'native';
  if (builder && !arm.flow.hasViewConfiguration) return null;
  // Every offer we run is a free trial ("Try it FREE", "after 3 days free"),
  // builder ones included: someone who already used their trial gets none.
  const products = await adapty.getPaywallProducts(arm.flow);
  const product = products.find((p) => trialDays(p) > 0);
  if (!product) {
    addBreadcrumb('paywall', 'Offer skipped: no trial-eligible product', {
      variant: builder ? arm.flow.variationName ?? arm.flow.variationId : arm.config.variant,
    });
    return null;
  }
  if (builder) return { kind: 'flow', flow: arm.flow };
  return { kind: 'native', flow: arm.flow, config: arm.config, product, source: arm.source };
}

/** First remote config of a legacy paywall placement (one per language; we ship one). */
function legacyRemoteConfig(flow: AdaptyFlow): Record<string, unknown> | undefined {
  return flow.remoteConfigs?.[0]?.data;
}

export default function PaywallScreen() {
  const router = useRouter();
  const { status, profile, refreshProfile } = useAuth();
  const params = useLocalSearchParams<{ dismissable?: string; qa_offer?: string }>();
  const insets = useSafeAreaInsets();
  // Only Profile passes this — the acquisition/gate flows stay hard.
  const dismissable = params.dismissable === '1';
  // Acquisition flow: no account yet. Read through a ref inside the mount-time
  // effects below, which must not re-run when auth state changes.
  const signedIn = status === 'signedIn';
  const signedInRef = useRef(signedIn);
  useEffect(() => {
    signedInRef.current = signedIn;
  }, [signedIn]);

  /**
   * Hand a purchase made without an account to the sign-in gate. The marker
   * carries the anonymous Adapty profile id so `/billing/sync` can grant the
   * entitlement before `identify()` has propagated; it also lets a cold start
   * resume at the gate instead of restarting the intro.
   */
  const handOffToSignIn = useCallback(async (
    source: PendingPurchase['source'],
    product: string | null,
  ) => {
    await savePendingPurchase({
      adapty_profile_id: await getAdaptyProfileId(),
      product,
      source,
    });
    addBreadcrumb('purchase', 'Signed-out purchase → sign-in gate', { source });
    // A new purchase celebrates first (22), then the gate (23).
    router.replace(source === 'purchase' ? '/success' : '/save-plan');
  }, [router]);

  const [phase, setPhase] = useState<Phase>('loading');
  const [purchasing, setPurchasing] = useState(false);
  // V3 path: the `pw_main` arm and its flow's products. `loadKey` remounts the
  // step machine on a retry so it starts from the first step again.
  const [v3, setV3] = useState<{ arm: ResolvedArm; products: AdaptyPaywallProduct[] } | null>(null);
  const v3Ref = useRef(v3);
  v3Ref.current = v3;
  const [loadKey, setLoadKey] = useState(0);
  // Legacy (code-rendered) path: the paywall placement's flow object.
  const paywallRef = useRef<AdaptyFlow | null>(null);
  const [products, setProducts] = useState<AdaptyPaywallProduct[]>([]);
  const configRef = useRef(FALLBACK_CONFIG);
  // Builder path: the flow the SDK renders.
  const [builderFlow, setBuilderFlow] = useState<AdaptyFlow | null>(null);
  // After-cancel offer: prefetched once the paywall is up, shown at most once
  // per visit, only when the App Store sheet was dismissed by the customer.
  const offerRef = useRef<Promise<OfferState | null> | null>(null);
  const offerShownRef = useRef(false);
  const [offer, setOffer] = useState<OfferState | null>(null);
  // Set once a purchase or restore succeeded or the screen unmounted: a late
  // offer must not be shown (or counted as a view) after that.
  const leavingRef = useRef(false);
  useEffect(() => {
    leavingRef.current = false;
    return () => { leavingRef.current = true; };
  }, []);
  // Guards for the Apple Ads paywall swap: do it at most once, and never while
  // a purchase is in flight.
  const upgradedRef = useRef(false);
  const purchasingRef = useRef(false);
  // Pre-auth users have no profile — plan numbers live in the intro draft.
  const [draft, setDraft] = useState<IntroDraft | null>(null);
  const [draftLoaded, setDraftLoaded] = useState(false);

  useEffect(() => {
    loadDraft()
      .then(setDraft)
      .catch(() => {})
      .finally(() => setDraftLoaded(true));
  }, []);

  useEffect(() => {
    purchasingRef.current = purchasing;
  }, [purchasing]);

  const targetWeightKg = draft?.target_weight_kg ?? null;
  const targetWeeks = draft?.target_weeks ?? null;
  const dailyKcal = draft?.target_calories ?? profile?.target_calories ?? null;
  const goal = draft?.goal_type ?? profile?.goal_type ?? null;
  const imperial = draft?.units === 'imperial';
  const targetText = targetWeightKg ? (imperial ? fmtStLb(targetWeightKg) : `${fmtKg(targetWeightKg)} kg`) : undefined;

  const targetDate = (() => {
    let d: Date | null = null;
    if (draft?.target_date) d = new Date(`${draft.target_date}T12:00:00`);
    else if (targetWeeks) {
      d = new Date();
      d.setDate(d.getDate() + targetWeeks * 7);
    }
    return d ? d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' }) : undefined;
  })();

  const placeholders: PlaceholderValues = {
    TARGET_WEIGHT: targetText,
    TARGET_DATE: targetDate,
    DAILY_KCAL: dailyKcal ? String(dailyKcal) : undefined,
    PRICE_M: products.find((p) => p.vendorProductId?.includes('monthly'))
      ?.price?.localizedString ?? '$9.99',
    PRICE_W: products.find((p) => p.vendorProductId?.includes('weekly'))
      ?.price?.localizedString ?? '$4.99',
  };

  // The same numbers as `{TAG}` custom tags for the builder flow. Kept stable
  // so the native view is not rebuilt on every render. Prices are never
  // passed: the builder reads them from the store itself.
  const flowParams = useMemo<CreateFlowViewParamsInput>(() => {
    const target = targetText ?? '';
    const kcal = dailyKcal ? String(dailyKcal) : '';
    // The flow cannot branch on the goal, so the hero line is resolved here:
    // a target for lose/gain, the maintenance zone for everyone else.
    const heroLine = target && targetDate
      ? `${target} by ${targetDate}`
      : kcal
        ? `Your zone: ${kcal} kcal`
        : 'Your plan is ready';
    return {
      customTags: {
        HERO_LINE: heroLine,
        TARGET_WEIGHT: target,
        TARGET_DATE: targetDate ?? '',
        DAILY_KCAL: kcal,
        GOAL: goal ?? '',
        // Same number the code screens show (`onb_content.rating`), not a hard-coded one.
        RATING: getOnboardingContent().rating,
        USERS: '12,000',
      },
    };
  }, [targetText, targetDate, dailyKcal, goal]);

  const variantLabel = useCallback((renderer: Renderer): string => {
    if (renderer === 'v3') return v3Ref.current?.arm.config.variant ?? 'v3';
    if (renderer === 'adapty_flow') return builderFlow?.variationName ?? builderFlow?.variationId ?? 'flow';
    if (renderer === 'v3_offer' || renderer === 'adapty_flow_offer') return offer ? offerVariant(offer) : 'offer';
    return configRef.current.variant;
  }, [builderFlow, offer]);

  /** Everything that happens after StoreKit confirmed a purchase, any renderer. */
  const afterPurchaseSuccess = useCallback(async (
    product: AdaptyPaywallProduct,
    renderer: Renderer,
    extra: Record<string, unknown> = {},
  ) => {
    const hasTrial = freeTrialPhase(product) !== undefined;
    track('paywall_purchase_success', {
      product: product.vendorProductId,
      variant: variantLabel(renderer),
      renderer,
      price: product.price?.amount,
      currency: product.price?.currencyCode,
      has_trial: hasTrial,
      ...extra,
    });
    // No AppsFlyer event from here: trials and purchases reach AppsFlyer from
    // Adapty's server integration, which can tell sandbox from production.
    leavingRef.current = true;
    addBreadcrumb('purchase', 'Purchase succeeded', { signed_in: signedInRef.current, renderer });
    await startJourney(); // journey Day 1 = purchase moment
    // A reminder is only honest when a trial is actually running: customers
    // who already used their one intro offer are charged immediately.
    if (hasTrial) {
      await scheduleTrialEndingReminder(new Date(), trialDays(product));
    }
    if (!signedInRef.current) {
      // Acquisition flow: the receipt is on an anonymous Adapty profile.
      // Create the account next; the gate attaches the purchase to it.
      await handOffToSignIn('purchase', product.vendorProductId);
      return;
    }
    await enableRemindersAfterPurchase().catch(() => false);
    await refreshProfile();
    router.replace('/success?next=tabs');
  }, [handOffToSignIn, refreshProfile, router, variantLabel]);

  /** After a restore that found an active `premium` access level, any renderer. */
  const afterRestoreSuccess = useCallback(async () => {
    leavingRef.current = true;
    track('paywall_restore_success', { signed_in: signedInRef.current });
    // Idempotent — a reinstall gets the first-week ladder, an existing
    // journey is left where it is.
    await startJourney();
    if (!signedInRef.current) {
      // Returning customer on a fresh install: access is proven on the
      // anonymous Adapty profile; the gate signs them in and reconciles.
      await handOffToSignIn('restore', null);
      return;
    }
    await refreshProfile();
    router.replace('/(tabs)');
  }, [handOffToSignIn, refreshProfile, router]);

  /** Legacy path: remote config + our own renderer. */
  const loadCodePaywall = useCallback(async (alive: () => boolean) => {
    const pw = await adapty.getFlow(ADAPTY_PLACEMENT_MAIN, {
      loadTimeoutMs: PAYWALL_LOAD_TIMEOUT_MS,
    });
    if (!alive()) return;
    paywallRef.current = pw;

    const config = parseRemoteConfig(legacyRemoteConfig(pw));
    configRef.current = config;

    const prods = await adapty.getPaywallProducts(pw);
    if (!alive()) return;
    setProducts(prods);

    await adapty.logShowFlow(pw);
    track('paywall_shown', {
      placement: ADAPTY_PLACEMENT_MAIN,
      variant: config.variant,
      renderer: 'code',
      products_available: prods.length > 0,
    });
    addBreadcrumb('paywall', 'Paywall shown', { variant: config.variant, renderer: 'code' });

    setPhase('ready');
  }, []);

  const loadPaywall = useCallback(async (mountedRef?: { current: boolean }) => {
    const alive = () => mountedRef?.current !== false;
    setPhase('loading');
    const ok = await activateAdapty();

    // The arm decides the renderer. With Adapty down it is the code default.
    const arm = await resolvePaywallArm(ADAPTY_PLACEMENT_PAYWALL_FLOW, 'paywall', PAYWALL_LOAD_TIMEOUT_MS);
    if (!alive()) return;
    const armMeta = {
      placement: ADAPTY_PLACEMENT_PAYWALL_FLOW,
      config_source: arm.source,
      variation_id: arm.flow?.variationId,
      variation_name: arm.flow?.variationName,
      ab_test: arm.flow?.placement?.abTestName,
      audience: arm.flow?.placement?.audienceName,
    };

    if (arm.config.render === 'flow' && arm.flow?.hasViewConfiguration) {
      setBuilderFlow(arm.flow);
      setPhase('flow');
      addBreadcrumb('paywall', 'Builder flow loaded', { variation: arm.flow.variationName ?? arm.flow.variationId });
      return;
    }

    if (arm.config.render === 'legacy') {
      addBreadcrumb('paywall', 'Arm asks for the legacy code paywall', armMeta);
      try {
        await loadCodePaywall(alive);
      } catch (e) {
        captureException(e);
        if (alive()) {
          setPhase('fallback');
          track('paywall_fallback_shown', {
            placement: ADAPTY_PLACEMENT_MAIN,
            reason: 'load_failed',
            error: e instanceof Error ? e.message : String(e),
          });
        }
      }
      return;
    }

    // V3 in code, with the arm flow's own products.
    let prods: AdaptyPaywallProduct[] = [];
    if (ok && arm.flow) {
      try {
        prods = sortPlans(await adapty.getPaywallProducts(arm.flow));
      } catch (e) {
        captureException(e, adaptyErrorContext(e, { placement: ADAPTY_PLACEMENT_PAYWALL_FLOW, renderer: 'v3' }));
      }
    }
    if (!alive()) return;
    if (ok && arm.flow && prods.length === 0) {
      // A code arm whose flow carries no products (a dashboard mistake, or
      // StoreKit answered empty) would be a wall without a way through: show
      // the legacy paywall and its products instead.
      captureException(new Error('V3 paywall arm has no products'), { ...armMeta, variant: arm.config.variant });
      try {
        await loadCodePaywall(alive);
        return;
      } catch (e) {
        captureException(e);
      }
      if (!alive()) return;
    }
    setV3({ arm, products: prods });
    setLoadKey((k) => k + 1);
    setPhase('v3');
    if (arm.flow && prods.length > 0) {
      adapty.logShowFlow(arm.flow).catch((e) => captureException(e));
    }
    track('paywall_shown', {
      ...armMeta,
      variant: arm.config.variant,
      renderer: 'v3',
      price_emphasis: arm.config.price_emphasis,
      products_available: prods.length > 0,
      products: prods.map((p) => p.vendorProductId).join(','),
      plans_only: dismissable || signedInRef.current,
    });
    addBreadcrumb('paywall', 'Paywall shown', { variant: arm.config.variant, renderer: 'v3' });
    if (prods.length === 0) {
      track('paywall_fallback_shown', {
        placement: ADAPTY_PLACEMENT_PAYWALL_FLOW,
        renderer: 'v3',
        reason: !ok ? 'adapty_unavailable' : arm.flow ? 'no_products' : 'no_flow',
      });
    }
  }, [dismissable, loadCodePaywall]);

  useEffect(() => {
    const mountedRef = { current: true };
    void loadPaywall(mountedRef);
    return () => { mountedRef.current = false; };
  }, [loadPaywall]);

  // Web purchases (Adapty Mail → FunnelFox → Paddle) grant `premium` on the
  // identified Adapty profile with no StoreKit transaction, so the launch
  // router can race ahead of /billing/sync and land a paying customer on this
  // hard gate. Check the Adapty profile once and let them straight through.
  //
  // Deliberately fail-safe: runs in parallel with the paywall load (never
  // delays first paint), and on any error or timeout simply leaves the paywall
  // on screen — exactly today's behavior. Skipped for the Profile entry
  // (`dismissable`), where a member opens this screen on purpose.
  useEffect(() => {
    if (dismissable) return;
    let cancelled = false;

    void (async () => {
      try {
        await waitForAdaptyIdentify();
        if (cancelled || !(await hasActivePremium())) return;
        // Never yank the screen while a StoreKit sheet may be up.
        if (cancelled || purchasingRef.current) return;

        track('paywall_skipped_already_premium', {
          placement: ADAPTY_PLACEMENT_MAIN,
          source: 'paywall_mount',
          signed_in: signedInRef.current,
        });
        addBreadcrumb('paywall', 'Active premium found on mount — skipping gate');
        await startJourney(); // idempotent — journey Day 1 = purchase moment

        // Signed out (acquisition flow): the access sits on an anonymous Adapty
        // profile — e.g. Adapty restored an existing App Store subscription on
        // a reinstall. There is no account to sync to yet, so route to the
        // sign-in gate, which reconciles the backend after sign-in.
        if (!signedInRef.current) {
          if (!cancelled && !purchasingRef.current) {
            await handOffToSignIn('existing_access', null);
          }
          return;
        }

        // Reconcile the backend so the launch router doesn't bounce the user
        // back here on the next cold start. Best-effort: access is already
        // proven by the Adapty profile, so failures must not keep the wall up.
        try {
          await api.syncBilling(await getAdaptyProfileId());
        } catch {
          // backend catches up via the webhook or the next sign-in sync
        }
        await refreshProfile().catch(() => {});

        if (!cancelled && !purchasingRef.current) router.replace('/(tabs)');
      } catch (e) {
        // Any failure keeps the paywall — never break the purchase path.
        captureException(e);
      }
    })();

    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // NEVER reload the app from this screen. 1.0.3 shipped an Updates.reloadAsync()
  // call here (fired while an OTA update was pending) to swap in a fresh bundle
  // during the loading spinner. In production the reload killed the JS context
  // and the new bundle never booted: every ad-driven first session froze on this
  // spinner the moment the user tapped "Start my plan" (Jul 30 – Aug 4: 10 of 12
  // users lost, zero trials). Paywall freshness comes from Adapty remote config,
  // which is fetched live above; OTA bundles apply on the next natural launch.

  // Apple Ads attribution lands asynchronously after launch, so the fetch above
  // usually resolves against the default audience and an Apple Ads user would
  // never see their targeted paywall. Rather than delay the first paint, swap
  // the paywall out once attribution arrives. No-op for everyone else, and from
  // the second launch on the first fetch is already targeted.
  //
  // Legacy code path only: the V3 steps and the builder flow are not swapped
  // under the user; an Apple-Ads audience on `pw_main` takes effect from the
  // second launch.
  useEffect(() => {
    if (phase !== 'ready' || upgradedRef.current) return;
    const mountedRef = { current: true };

    void (async () => {
      const applied = await waitForAppleAdsAttribution(APPLE_ADS_ATTRIBUTION_TIMEOUT_MS);
      if (!applied || !mountedRef.current || upgradedRef.current) return;
      // Never pull the paywall out from under an in-flight StoreKit sheet.
      if (purchasingRef.current) return;

      try {
        const targeted = await adapty.getFlow(ADAPTY_PLACEMENT_MAIN, {
          loadTimeoutMs: PAYWALL_LOAD_TIMEOUT_MS,
        });
        if (!mountedRef.current || purchasingRef.current) return;
        if (targeted.variationId === paywallRef.current?.variationId) return;

        const targetedProducts = await adapty.getPaywallProducts(targeted);
        if (!mountedRef.current || purchasingRef.current) return;

        const previousVariant = configRef.current.variant;
        upgradedRef.current = true;
        paywallRef.current = targeted;
        configRef.current = parseRemoteConfig(legacyRemoteConfig(targeted));
        setProducts(targetedProducts);

        await adapty.logShowFlow(targeted);
        track('paywall_variant_swapped', {
          placement: ADAPTY_PLACEMENT_MAIN,
          from_variant: previousVariant,
          to_variant: configRef.current.variant,
          reason: 'apple_search_ads',
        });
      } catch (e) {
        // Keep the paywall already on screen; it's a valid one.
        captureException(e);
      }
    })();

    return () => { mountedRef.current = false; };
  }, [phase]);

  // Prefetch the offer as soon as the paywall is on screen, so a cancellation
  // can be answered instantly instead of with a spinner. Test C5 can switch
  // the offer off (`after_cancel_offer: false` on `onb_main`).
  useEffect(() => {
    if (phase !== 'flow' && phase !== 'ready' && phase !== 'v3') return;
    if (offerRef.current || dismissable || !getOnboardingConfig().after_cancel_offer) return;
    offerRef.current = prefetchOffer().catch((e) => {
      addBreadcrumb('paywall', 'Offer prefetch failed', { error: e instanceof Error ? e.message : String(e) });
      return null;
    });
  }, [phase, dismissable]);

  /**
   * The customer dismissed the App Store sheet. Show the after-cancel offer if
   * the arm has one, once per visit. Returns whether it was shown.
   */
  const maybeShowOffer = useCallback(async (product: string | undefined, renderer: Renderer) => {
    if (offerShownRef.current || dismissable) return false;
    const next = await (offerRef.current ?? Promise.resolve(null));
    if (!next || purchasingRef.current || offerShownRef.current || leavingRef.current) return false;
    offerShownRef.current = true;
    setOffer(next);
    if (next.kind === 'native') {
      adapty.logShowFlow(next.flow).catch((e) => captureException(e));
    }
    track('paywall_offer_shown', {
      placement: ADAPTY_PLACEMENT_AFTER_CANCEL_FLOW,
      variant: offerVariant(next),
      renderer: next.kind === 'native' ? 'v3' : 'adapty_flow',
      config_source: next.kind === 'native' ? next.source : 'adapty',
      variation_id: next.flow.variationId,
      ab_test: next.flow.placement?.abTestName,
      offer_product: next.kind === 'native' ? next.product.vendorProductId : undefined,
      after_product: product,
      after_renderer: renderer,
    });
    addBreadcrumb('paywall', 'After-cancel offer shown', { after_product: product, kind: next.kind });
    return true;
  }, [dismissable]);

  // QA builds: `/paywall?qa_offer=1` opens the after-cancel offer straight
  // away, so it can be checked in the simulator without a StoreKit cancel.
  const qaOfferRef = useRef(false);
  useEffect(() => {
    if (!IS_QA_BUILD || params.qa_offer !== '1' || qaOfferRef.current) return;
    if (phase !== 'v3' && phase !== 'flow' && phase !== 'ready') return;
    qaOfferRef.current = true;
    void maybeShowOffer('qa_preview', 'v3');
  }, [phase, params.qa_offer, maybeShowOffer]);

  const handleRetry = useCallback(() => {
    track('paywall_retry_pressed');
    // A prefetch made while Adapty was unreachable resolved to "no offer";
    // fetch it again with the paywall.
    if (!offerShownRef.current) offerRef.current = null;
    void loadPaywall();
  }, [loadPaywall]);

  const handlePurchase = useCallback(async (product: AdaptyPaywallProduct, renderer: Renderer = 'code') => {
    if (purchasingRef.current) return;
    purchasingRef.current = true;
    setPurchasing(true);
    const variant = variantLabel(renderer);
    addBreadcrumb('purchase', 'Purchase started', { product: product.vendorProductId, renderer });
    if (renderer === 'code') {
      track('paywall_plan_selected', { product: product.vendorProductId, variant, renderer });
    } else {
      track('paywall_purchase_started', {
        product: product.vendorProductId,
        variant,
        renderer,
        has_trial: trialDays(product) > 0,
      });
    }

    try {
      // QA builds only: skip StoreKit so the post-purchase screens can be
      // walked in the simulator.
      if (IS_QA_BUILD && qaOverrides().mock_purchase) {
        addBreadcrumb('purchase', 'QA mock purchase', { product: product.vendorProductId });
        await afterPurchaseSuccess(product, renderer, { mode: 'qa_mock' });
        return;
      }

      if (!isAdaptyConfigured()) {
        track('paywall_purchase_success', {
          product: product.vendorProductId,
          variant,
          mode: 'dev_trial',
        });
        await startJourney(); // journey Day 1 = purchase moment
        if (!signedIn) {
          // No account to start a trial on yet — /save-plan does it after sign-in.
          await handOffToSignIn('purchase', product.vendorProductId);
          return;
        }
        await api.startTrial(3);
        await refreshProfile();
        router.replace('/success?next=tabs');
        return;
      }

      // Signed-in entry (lapsed member / Profile): sign-in identifies the Adapty
      // profile in the background. Buying before that lands means the receipt
      // arrives at our webhook with no customer_user_id and the entitlement has
      // to be reconciled after the fact — so give identify() its moment first.
      // Resolves at once in the acquisition flow, where nothing is in flight.
      await waitForAdaptyIdentify();

      const result = await adapty.makePurchase(product);
      if (result.type === 'success') {
        await afterPurchaseSuccess(product, renderer);
      } else if (result.type === 'user_cancelled') {
        // User backed out of the StoreKit sheet — expected, not an error.
        track('paywall_purchase_cancelled', { product: product.vendorProductId, variant, renderer });
        addBreadcrumb('purchase', 'Purchase cancelled by user');
        // `purchasingRef` mirrors the `purchasing` state through an effect, so at this
        // point it still reads true and `maybeShowOffer` would bail out: the after-cancel
        // offer never showed on the code paywall (seen live 2026-10-06). Clear it first.
        purchasingRef.current = false;
        if (renderer !== 'v3_offer') void maybeShowOffer(product.vendorProductId, renderer);
      } else if (result.type === 'pending') {
        // Ask-to-Buy / deferred: purchase may complete later out of band.
        track('paywall_purchase_pending', { product: product.vendorProductId, variant, renderer });
        Alert.alert(
          'Purchase pending',
          "Your purchase needs approval and will activate once it's confirmed.",
        );
      }
    } catch (e) {
      track('paywall_purchase_failed', {
        product: product.vendorProductId,
        variant,
        renderer,
        error: e instanceof Error ? e.message : String(e),
        adapty_detail: adaptyErrorContext(e).adapty_detail,
      });
      captureException(e, adaptyErrorContext(e, { product: product.vendorProductId, renderer }));
      Alert.alert('Purchase failed', 'Something went wrong. Please try again.');
    } finally {
      purchasingRef.current = false;
      setPurchasing(false);
    }
  }, [afterPurchaseSuccess, maybeShowOffer, refreshProfile, router, signedIn, handOffToSignIn, variantLabel]);

  const handleRestore = useCallback(async () => {
    if (purchasingRef.current) return;
    purchasingRef.current = true;
    setPurchasing(true);
    addBreadcrumb('purchase', 'Restore started');
    track('paywall_restore_started');

    try {
      if (!isAdaptyConfigured()) {
        if (!signedIn) {
          await handOffToSignIn('restore', null);
          return;
        }
        router.replace('/(tabs)');
        return;
      }
      const adaptyProfile = await adapty.restorePurchases();
      if (adaptyProfile.accessLevels?.[PREMIUM_ACCESS_LEVEL]?.isActive) {
        await afterRestoreSuccess();
      } else {
        Alert.alert('No subscription found', 'We couldn\'t find an active subscription for this Apple ID.');
        track('paywall_restore_empty');
      }
    } catch (e) {
      Alert.alert('Restore failed', 'Please try again.');
      captureException(e);
      track('paywall_restore_failed');
    } finally {
      purchasingRef.current = false;
      setPurchasing(false);
    }
  }, [afterRestoreSuccess, router, signedIn, handOffToSignIn]);

  const handleClose = useCallback(() => {
    track('paywall_closed', { dismissable: true });
    if (router.canGoBack()) router.back();
    else router.replace('/(tabs)');
  }, [router]);

  // --- Builder-flow event handlers -----------------------------------------
  // The SDK owns the StoreKit sheet; these mirror what handlePurchase /
  // handleRestore do after the fact. Handlers must return synchronously
  // (`false` keeps the view; navigation unmounts it anyway).

  const flowContext = useMemo(() => ({
    placement: ADAPTY_PLACEMENT_PAYWALL_FLOW,
    variation: builderFlow?.variationId,
    variationName: builderFlow?.variationName,
  }), [builderFlow]);

  const onFlowPurchaseCompleted = useCallback(
    (result: AdaptyPurchaseResult, product: AdaptyPaywallProduct) => {
      purchasingRef.current = false;
      if (result.type === 'success') {
        void afterPurchaseSuccess(product, 'adapty_flow').catch(captureException);
      } else if (result.type === 'user_cancelled') {
        track('paywall_purchase_cancelled', {
          product: product.vendorProductId,
          variant: variantLabel('adapty_flow'),
          renderer: 'adapty_flow',
        });
        addBreadcrumb('purchase', 'Purchase cancelled by user');
        void maybeShowOffer(product.vendorProductId, 'adapty_flow');
      } else if (result.type === 'pending') {
        track('paywall_purchase_pending', { product: product.vendorProductId, renderer: 'adapty_flow' });
        Alert.alert(
          'Purchase pending',
          "Your purchase needs approval and will activate once it's confirmed.",
        );
      }
      return false;
    },
    [afterPurchaseSuccess, maybeShowOffer, variantLabel],
  );

  const onFlowRestoreCompleted = useCallback((adaptyProfile: AdaptyProfile) => {
    purchasingRef.current = false;
    if (adaptyProfile.accessLevels?.[PREMIUM_ACCESS_LEVEL]?.isActive) {
      void afterRestoreSuccess().catch(captureException);
    } else {
      track('paywall_restore_empty', { renderer: 'adapty_flow' });
      Alert.alert('No subscription found', 'We couldn\'t find an active subscription for this Apple ID.');
    }
    return false;
  }, [afterRestoreSuccess]);

  // Overlays a close button (Profile entry only) on any paywall content.
  const withClose = (node: ReactNode) => {
    if (!dismissable) return <>{node}</>;
    return (
      <View style={s.fill}>
        {node}
        <Pressable
          onPress={handleClose}
          style={[s.closeBtn, { top: insets.top + space.xs }]}
          hitSlop={8}
          accessibilityRole="button"
          accessibilityLabel="Close"
        >
          <X size={20} color={colors.inkMuted} strokeWidth={2} />
        </Pressable>
      </View>
    );
  };

  // The after-cancel offer is drawn over the paywall, which stays mounted
  // underneath: closing it brings the customer back to the same step (the
  // plans), not to the start. The gate itself stays hard. From stage 6 the
  // close leads to preview mode instead.
  let offerNode: ReactNode = null;
  if (offer) {
    const variant = offerVariant(offer);
    const closeOffer = (reason: string) => {
      track('paywall_offer_closed', {
        placement: ADAPTY_PLACEMENT_AFTER_CANCEL_FLOW,
        variant,
        renderer: offer.kind === 'native' ? 'v3' : 'adapty_flow',
        reason,
      });
      setOffer(null);
    };

    if (offer.kind === 'native') {
      offerNode = (
        <OfferScreen
          config={offer.config}
          product={offer.product}
          purchasing={purchasing}
          onBuy={() => void handlePurchase(offer.product, 'v3_offer')}
          onClose={() => closeOffer('close')}
          onRestore={() => void handleRestore()}
        />
      );
    } else {
      const offerFlow = offer.flow;
      offerNode = (
        <AdaptyFlowView
          flow={offerFlow}
          params={flowParams}
          style={s.fill}
          onProductSelected={(productId) => {
            track('paywall_plan_selected', { product: productId, variant, renderer: 'adapty_flow_offer' });
            return false;
          }}
          onPurchaseStarted={(product) => {
            purchasingRef.current = true;
            addBreadcrumb('purchase', 'Offer purchase started', { product: product.vendorProductId });
            return false;
          }}
          onPurchaseCompleted={(result, product) => {
            purchasingRef.current = false;
            if (result.type === 'success') {
              void afterPurchaseSuccess(product, 'adapty_flow_offer').catch(captureException);
            } else if (result.type === 'user_cancelled') {
              track('paywall_purchase_cancelled', { product: product.vendorProductId, variant, renderer: 'adapty_flow_offer' });
            } else if (result.type === 'pending') {
              track('paywall_purchase_pending', { product: product.vendorProductId, renderer: 'adapty_flow_offer' });
            }
            return false;
          }}
          onPurchaseFailed={(error, product) => {
            purchasingRef.current = false;
            track('paywall_purchase_failed', { product: product?.vendorProductId, renderer: 'adapty_flow_offer', error: error?.message, adapty_detail: adaptyErrorContext(error).adapty_detail });
            captureException(error, adaptyErrorContext(error, { product: product?.vendorProductId, renderer: 'adapty_flow_offer' }));
            return false;
          }}
          onRestoreStarted={() => {
            purchasingRef.current = true;
            return false;
          }}
          onRestoreCompleted={onFlowRestoreCompleted}
          onRestoreFailed={(error) => {
            purchasingRef.current = false;
            captureException(error);
            return false;
          }}
          onCloseButtonPress={() => {
            closeOffer('close');
            return false;
          }}
          onCustomAction={(actionId) => {
            // Any custom action on the offer ("no thanks") returns to the paywall.
            closeOffer(actionId);
            return false;
          }}
          onError={(error) => {
            captureException(error, { placement: ADAPTY_PLACEMENT_AFTER_CANCEL_FLOW });
            closeOffer('render_error');
            return false;
          }}
          onAnalytics={(name, eventParams) => {
            trackFlowAnalytics(
              { placement: ADAPTY_PLACEMENT_AFTER_CANCEL_FLOW, variation: offerFlow.variationId, variationName: offerFlow.variationName },
              name,
              eventParams,
            );
            return false;
          }}
          onRequestPermission={handleFlowPermissionRequest}
        />
      );
    }
  }
  const withOffer = (node: ReactNode) =>
    offerNode ? (
      <View style={s.fill}>
        {node}
        <View style={StyleSheet.absoluteFill}>{offerNode}</View>
      </View>
    ) : (
      node
    );

  if (phase === 'loading' || (phase === 'v3' && !draftLoaded)) {
    return withClose(<PwLoading />);
  }

  if (phase === 'v3' && v3) {
    return withOffer(withClose(
      <V3Paywall
        key={loadKey}
        config={v3.arm.config}
        products={v3.products}
        draft={signedIn ? null : draft}
        plansOnly={dismissable || signedIn}
        purchasing={purchasing}
        onPurchase={(p) => void handlePurchase(p, 'v3')}
        onRestore={() => void handleRestore()}
        onRetry={handleRetry}
      />,
    ));
  }

  if (phase === 'flow' && builderFlow) {
    return withOffer(withClose(
      <View style={s.fill}>
        <AdaptyFlowView
          flow={builderFlow}
          params={flowParams}
          style={s.fill}
          onAppeared={() => {
            track('paywall_shown', {
              placement: ADAPTY_PLACEMENT_PAYWALL_FLOW,
              variant: builderFlow.variationName ?? builderFlow.variationId,
              renderer: 'adapty_flow',
              ab_test: builderFlow.placement?.abTestName,
              audience: builderFlow.placement?.audienceName,
            });
            addBreadcrumb('paywall', 'Paywall shown', {
              variant: builderFlow.variationName ?? builderFlow.variationId,
              renderer: 'adapty_flow',
            });
            return false;
          }}
          onProductSelected={(productId) => {
            track('paywall_plan_selected', {
              product: productId,
              variant: builderFlow.variationName ?? builderFlow.variationId,
              renderer: 'adapty_flow',
            });
            return false;
          }}
          onPurchaseStarted={(product) => {
            purchasingRef.current = true;
            addBreadcrumb('purchase', 'Purchase started', {
              product: product.vendorProductId,
              renderer: 'adapty_flow',
            });
            return false;
          }}
          onPurchaseCompleted={onFlowPurchaseCompleted}
          onPurchaseFailed={(error, product) => {
            purchasingRef.current = false;
            track('paywall_purchase_failed', {
              product: product?.vendorProductId,
              renderer: 'adapty_flow',
              error: error?.message ?? String(error),
              adapty_detail: adaptyErrorContext(error).adapty_detail,
            });
            captureException(error, adaptyErrorContext(error, { product: product?.vendorProductId, renderer: 'adapty_flow' }));
            return false;
          }}
          onRestoreStarted={() => {
            purchasingRef.current = true;
            addBreadcrumb('purchase', 'Restore started', { renderer: 'adapty_flow' });
            track('paywall_restore_started', { renderer: 'adapty_flow' });
            return false;
          }}
          onRestoreCompleted={onFlowRestoreCompleted}
          onRestoreFailed={(error) => {
            purchasingRef.current = false;
            track('paywall_restore_failed', { renderer: 'adapty_flow' });
            captureException(error);
            return false;
          }}
          onCloseButtonPress={() => {
            // Hard paywall: a close action in the flow only works for the
            // Profile entry, where the overlay button already exists.
            if (dismissable) handleClose();
            return false;
          }}
          onLoadingProductsFailed={(error) => {
            track('paywall_products_failed', { renderer: 'adapty_flow', error: error?.message });
            captureException(error);
            return false;
          }}
          onError={(error) => {
            // A flow that cannot render is not a wall: drop to the code paywall.
            captureException(error, { placement: ADAPTY_PLACEMENT_PAYWALL_FLOW });
            track('paywall_flow_render_failed', { error: error?.message });
            setBuilderFlow(null);
            void loadCodePaywall(() => true).catch((e) => {
              captureException(e);
              setPhase('fallback');
              track('paywall_fallback_shown', {
                placement: ADAPTY_PLACEMENT_MAIN,
                reason: 'load_failed',
                error: e instanceof Error ? e.message : String(e),
              });
            });
            return false;
          }}
          onAnalytics={(name, eventParams) => {
            trackFlowAnalytics(flowContext, name, eventParams);
            return false;
          }}
          onCustomAction={(actionId) => {
            track('adapty_flow_custom_action', { ...flowContext, action_id: actionId });
            return false;
          }}
          onRequestPermission={handleFlowPermissionRequest}
        />
      </View>,
    ));
  }

  const variant = resolveVariant(configRef.current.variant);
  const rendererProps = {
    config: configRef.current,
    products,
    placeholders,
    goal,
    onPurchase: (p: AdaptyPaywallProduct) => handlePurchase(p, 'code'),
    onRestore: handleRestore,
    onRetry: handleRetry,
    purchasing,
  };

  switch (variant) {
    case 'B':
      return withOffer(withClose(<VariantB {...rendererProps} />));
    case 'B2':
      return withOffer(withClose(<VariantB2 {...rendererProps} />));
    case 'C':
      return withOffer(withClose(<VariantC {...rendererProps} />));
    case 'S':
      return withOffer(withClose(<VariantSHero {...rendererProps} />));
    default:
      return withOffer(withClose(<PaywallRenderer {...rendererProps} />));
  }
}

const s = StyleSheet.create({
  fill: { flex: 1, backgroundColor: colors.bg },
  closeBtn: {
    position: 'absolute',
    left: space.lg,
    width: 34,
    height: 34,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
