/**
 * Paywall screen.
 *
 * Two renderers, one contract:
 *   1. Builder flow (placement `pw_main`, Adapty Flow & Paywall Builder): the
 *      whole screen is designed in the dashboard and drawn natively by the
 *      SDK via `AdaptyFlowView`; purchases, restore and the StoreKit sheet
 *      are the SDK's. This is where paywall tests live from now on.
 *   2. Code-rendered (placement `main`, legacy remote config): our own
 *      `PaywallRenderer`/`Variant*` components, kept as the fallback for when
 *      the flow placement has nothing published or fails to load, and as the
 *      offline paywall (bundled `FALLBACK_CONFIG`, purchases disabled).
 *
 * Two audiences reach this screen:
 *   - Acquisition (signed OUT): intro quiz → plan reveal → here. The purchase
 *     lands on an anonymous Adapty profile; we record a pending-purchase marker
 *     and hand off to /save-plan, the sign-in gate that attaches the purchase to
 *     the freshly created account. Nothing here may call an authenticated API.
 *   - Existing account (signed IN): the launch router's hard gate for a lapsed
 *     subscription, or Profile ("Manage plan" / "See plans") with
 *     `?dismissable=1`. Purchase → /postbuy as before.
 *
 * Hard paywall by default: no close button, gesture-dismiss disabled — exits
 * only via successful purchase or restore. Only the Profile entry gets a close
 * button: an existing member must always be able to leave.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { View, Pressable, StyleSheet, ActivityIndicator, Alert } from 'react-native';
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

import { Screen } from '@/components/Screen';
import { PaywallRenderer } from '@/components/paywall/PaywallRenderer';
import { VariantB } from '@/components/paywall/VariantB';
import { VariantB2 } from '@/components/paywall/VariantB2';
import { VariantC } from '@/components/paywall/VariantC';
import { VariantSHero } from '@/components/paywall/VariantSHero';
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
  fetchAdaptyFlow,
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
import { scheduleTrialEndingReminder } from '@/notifications/scheduler';
import { track } from '@/analytics/posthog';
import { logAttributionEvent } from '@/analytics/attribution';
import { addBreadcrumb, captureException } from '@/analytics/sentry';
import { colors, radius, space } from '@/theme/tokens';
import * as api from '@/api/endpoints';

/**
 * `loading` → spinner; `flow` → builder flow; `ready` → code-rendered paywall
 * from remote config; `fallback` → bundled config, purchases disabled.
 */
type Phase = 'loading' | 'flow' | 'ready' | 'fallback';

/** Cap each fetch so a slow network shows the fallback instead of a blank screen. */
const PAYWALL_LOAD_TIMEOUT_MS = 5000;

/** How long to keep waiting for Apple Ads attribution before giving up on it. */
const APPLE_ADS_ATTRIBUTION_TIMEOUT_MS = 20000;

/** The after-cancel offer is prefetched in the background; never wait longer than this for it. */
const OFFER_LOAD_TIMEOUT_MS = 8000;

/**
 * Remote kill switch, same convention as the onboarding flow: a flow on
 * `pw_main` whose remote config carries `{"use_native": true}` sends the app to
 * the code-rendered paywall on the legacy `main` placement, where today's
 * remote-config A/B test keeps running untouched. Flip it in the dashboard
 * when the builder paywalls should take over; no release needed either way.
 */
function flowDisabledByRemoteConfig(flow: AdaptyFlow): boolean {
  return flow.remoteConfigs?.some((rc) => rc.data?.use_native === true) ?? false;
}

/** First remote config of a legacy paywall placement (one per language; we ship one). */
function legacyRemoteConfig(flow: AdaptyFlow): Record<string, unknown> | undefined {
  return flow.remoteConfigs?.[0]?.data;
}

export default function PaywallScreen() {
  const router = useRouter();
  const { status, profile, refreshProfile } = useAuth();
  const params = useLocalSearchParams<{ dismissable?: string }>();
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
    router.replace('/save-plan');
  }, [router]);

  const [phase, setPhase] = useState<Phase>('loading');
  const [purchasing, setPurchasing] = useState(false);
  // Legacy (code-rendered) path: the paywall placement's flow object.
  const paywallRef = useRef<AdaptyFlow | null>(null);
  const [products, setProducts] = useState<AdaptyPaywallProduct[]>([]);
  const configRef = useRef(FALLBACK_CONFIG);
  // Builder path: the flow the SDK renders.
  const [builderFlow, setBuilderFlow] = useState<AdaptyFlow | null>(null);
  // After-cancel offer: prefetched once the paywall is up, shown at most once
  // per visit, only when the App Store sheet was dismissed by the customer.
  const offerFlowRef = useRef<Promise<AdaptyFlow | null> | null>(null);
  const offerShownRef = useRef(false);
  const [offerFlow, setOfferFlow] = useState<AdaptyFlow | null>(null);
  // Guards for the Apple Ads paywall swap: do it at most once, and never while
  // a purchase is in flight.
  const upgradedRef = useRef(false);
  const purchasingRef = useRef(false);
  // Pre-auth users have no profile — plan numbers live in the intro draft.
  const [draft, setDraft] = useState<IntroDraft | null>(null);

  useEffect(() => {
    loadDraft().then(setDraft).catch(() => {});
  }, []);

  useEffect(() => {
    purchasingRef.current = purchasing;
  }, [purchasing]);

  const targetWeightKg = draft?.target_weight_kg ?? null;
  const targetWeeks = draft?.target_weeks ?? null;
  const dailyKcal = draft?.target_calories ?? profile?.target_calories ?? null;
  const goal = draft?.goal_type ?? profile?.goal_type ?? null;

  const targetDate = (() => {
    if (!targetWeeks) return undefined;
    const d = new Date();
    d.setDate(d.getDate() + targetWeeks * 7);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  })();

  const placeholders: PlaceholderValues = {
    TARGET_WEIGHT: targetWeightKg ? `${targetWeightKg} kg` : undefined,
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
    const target = targetWeightKg ? `${targetWeightKg} kg` : '';
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
        RATING: '4.9',
        USERS: '12,000',
      },
    };
  }, [targetWeightKg, targetDate, dailyKcal, goal]);

  const variantLabel = useCallback(
    () => (phase === 'flow'
      ? builderFlow?.variationName ?? builderFlow?.variationId ?? 'flow'
      : configRef.current.variant),
    [phase, builderFlow],
  );

  /** Everything that happens after StoreKit confirmed a purchase, either renderer. */
  const afterPurchaseSuccess = useCallback(async (
    product: AdaptyPaywallProduct,
    renderer: 'adapty_flow' | 'code',
  ) => {
    const hasTrial = freeTrialPhase(product) !== undefined;
    track('paywall_purchase_success', {
      product: product.vendorProductId,
      variant: variantLabel(),
      renderer,
      price: product.price?.amount,
      currency: product.price?.currencyCode,
      has_trial: hasTrial,
    });
    // AppsFlyer standard events, logged client-side: the SDK feeds them into
    // the SKAdNetwork conversion value on-device and forwards them to ad
    // networks (Meta maps af_start_trial → StartTrial, af_subscribe →
    // Subscribe). A trial carries no revenue yet — af_price is the price it
    // converts to; a direct subscription reports the charge as af_revenue.
    logAttributionEvent(hasTrial ? 'af_start_trial' : 'af_subscribe', {
      af_content_id: product.vendorProductId,
      ...(product.price?.currencyCode ? { af_currency: product.price.currencyCode } : {}),
      ...(product.price?.amount !== undefined
        ? hasTrial
          ? { af_price: product.price.amount }
          : { af_revenue: product.price.amount, af_price: product.price.amount }
        : {}),
    });
    addBreadcrumb('purchase', 'Purchase succeeded', { signed_in: signedInRef.current, renderer });
    await startJourney(); // journey Day 1 = purchase moment
    // A reminder is only honest when a trial is actually running: customers
    // who already used their one intro offer are charged immediately.
    if (hasTrial) {
      await scheduleTrialEndingReminder(new Date());
    }
    if (!signedInRef.current) {
      // Acquisition flow: the receipt is on an anonymous Adapty profile.
      // Create the account next; the gate attaches the purchase to it.
      await handOffToSignIn('purchase', product.vendorProductId);
      return;
    }
    await refreshProfile();
    router.replace('/postbuy');
  }, [handOffToSignIn, refreshProfile, router, variantLabel]);

  /** After a restore that found an active `premium` access level, either renderer. */
  const afterRestoreSuccess = useCallback(async () => {
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
    router.replace('/postbuy');
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
    if (!ok) {
      if (alive()) {
        setPhase('fallback');
        // The fallback paywall renders display prices with purchases disabled —
        // without its own event these sessions are invisible in the funnel
        // (paywall_shown only fires on a live Adapty paywall).
        track('paywall_fallback_shown', {
          placement: ADAPTY_PLACEMENT_MAIN,
          reason: 'adapty_unavailable',
        });
      }
      return;
    }

    // 1) The builder flow. Anything short of a renderable flow — nothing
    //    published on the placement, a timeout, an SDK error — drops to the
    //    code paywall, which is exactly what shipped before.
    try {
      const flow = await adapty.getFlow(ADAPTY_PLACEMENT_PAYWALL_FLOW, {
        loadTimeoutMs: PAYWALL_LOAD_TIMEOUT_MS,
      });
      if (!alive()) return;
      if (flowDisabledByRemoteConfig(flow)) {
        addBreadcrumb('paywall', 'Flow placement disabled by remote config → code paywall');
      } else if (flow.hasViewConfiguration) {
        setBuilderFlow(flow);
        setPhase('flow');
        addBreadcrumb('paywall', 'Builder flow loaded', {
          variation: flow.variationName ?? flow.variationId,
        });
        return;
      } else {
        addBreadcrumb('paywall', 'Flow placement has no view configuration → code paywall');
      }
    } catch (e) {
      addBreadcrumb('paywall', 'Flow placement unavailable → code paywall', {
        error: e instanceof Error ? e.message : String(e),
      });
    }

    // 2) Code-rendered paywall from the legacy placement.
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
  }, [loadCodePaywall]);

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
  // Code-rendered path only: the builder flow is a live native view and is not
  // swapped under the user; an Apple-Ads audience on `pw_main` takes effect
  // from the second launch.
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
  // can be answered instantly instead of with a spinner.
  useEffect(() => {
    if ((phase !== 'flow' && phase !== 'ready') || offerFlowRef.current || dismissable) return;
    offerFlowRef.current = fetchAdaptyFlow(ADAPTY_PLACEMENT_AFTER_CANCEL_FLOW, OFFER_LOAD_TIMEOUT_MS)
      .then((flow) => (flow && flow.hasViewConfiguration && !flowDisabledByRemoteConfig(flow) ? flow : null))
      .catch(() => null);
  }, [phase, dismissable]);

  /**
   * The customer dismissed the App Store sheet. Show the after-cancel offer if
   * the dashboard has one, once per visit. Returns whether it was shown.
   */
  const maybeShowOffer = useCallback(async (product: string | undefined, renderer: string) => {
    if (offerShownRef.current || dismissable) return false;
    const flow = await (offerFlowRef.current ?? Promise.resolve(null));
    if (!flow || purchasingRef.current) return false;
    offerShownRef.current = true;
    setOfferFlow(flow);
    track('paywall_offer_shown', {
      placement: ADAPTY_PLACEMENT_AFTER_CANCEL_FLOW,
      variant: flow.variationName ?? flow.variationId,
      after_product: product,
      after_renderer: renderer,
    });
    addBreadcrumb('paywall', 'After-cancel offer shown', { after_product: product });
    return true;
  }, [dismissable]);

  const handleRetry = useCallback(() => {
    track('paywall_retry_pressed');
    void loadPaywall();
  }, [loadPaywall]);

  const handlePurchase = useCallback(async (product: AdaptyPaywallProduct) => {
    setPurchasing(true);
    const variant = configRef.current.variant;
    addBreadcrumb('purchase', 'Purchase started', { product: product.vendorProductId });
    track('paywall_plan_selected', { product: product.vendorProductId, variant, renderer: 'code' });

    try {
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
        router.replace('/postbuy');
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
        await afterPurchaseSuccess(product, 'code');
      } else if (result.type === 'user_cancelled') {
        // User backed out of the StoreKit sheet — expected, not an error.
        track('paywall_purchase_cancelled', { product: product.vendorProductId });
        addBreadcrumb('purchase', 'Purchase cancelled by user');
        void maybeShowOffer(product.vendorProductId, 'code');
      } else if (result.type === 'pending') {
        // Ask-to-Buy / deferred: purchase may complete later out of band.
        track('paywall_purchase_pending', { product: product.vendorProductId });
        Alert.alert(
          'Purchase pending',
          "Your purchase needs approval and will activate once it's confirmed.",
        );
      }
    } catch (e) {
      track('paywall_purchase_failed', {
        product: product.vendorProductId,
        error: e instanceof Error ? e.message : String(e),
      });
      captureException(e);
      Alert.alert('Purchase failed', 'Something went wrong. Please try again.');
    } finally {
      setPurchasing(false);
    }
  }, [afterPurchaseSuccess, maybeShowOffer, refreshProfile, router, signedIn, handOffToSignIn]);

  const handleRestore = useCallback(async () => {
    setPurchasing(true);
    addBreadcrumb('purchase', 'Restore started');
    track('paywall_restore_started');

    try {
      if (!isAdaptyConfigured()) {
        if (!signedIn) {
          await handOffToSignIn('restore', null);
          return;
        }
        router.replace('/postbuy');
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
        track('paywall_purchase_cancelled', { product: product.vendorProductId, renderer: 'adapty_flow' });
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
    [afterPurchaseSuccess, maybeShowOffer],
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
        >
          <X size={20} color={colors.inkMuted} strokeWidth={2} />
        </Pressable>
      </View>
    );
  };

  // The after-cancel offer replaces whatever paywall is up; its close button
  // brings the paywall back (the gate itself stays hard).
  if (offerFlow) {
    const offerVariant = offerFlow.variationName ?? offerFlow.variationId;
    const closeOffer = (reason: string) => {
      track('paywall_offer_closed', { placement: ADAPTY_PLACEMENT_AFTER_CANCEL_FLOW, variant: offerVariant, reason });
      setOfferFlow(null);
    };
    return (
      <View style={s.fill}>
        <AdaptyFlowView
          flow={offerFlow}
          params={flowParams}
          style={s.fill}
          onProductSelected={(productId) => {
            track('paywall_plan_selected', { product: productId, variant: offerVariant, renderer: 'adapty_flow_offer' });
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
              void afterPurchaseSuccess(product, 'adapty_flow').catch(captureException);
            } else if (result.type === 'user_cancelled') {
              track('paywall_purchase_cancelled', { product: product.vendorProductId, renderer: 'adapty_flow_offer' });
            } else if (result.type === 'pending') {
              track('paywall_purchase_pending', { product: product.vendorProductId, renderer: 'adapty_flow_offer' });
            }
            return false;
          }}
          onPurchaseFailed={(error, product) => {
            purchasingRef.current = false;
            track('paywall_purchase_failed', { product: product?.vendorProductId, renderer: 'adapty_flow_offer', error: error?.message });
            captureException(error);
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
      </View>
    );
  }

  if (phase === 'loading') {
    return withClose(
      <Screen edges={['top', 'bottom', 'left', 'right']}>
        <View style={s.loading}>
          <ActivityIndicator color={colors.terracotta} />
        </View>
      </Screen>,
    );
  }

  if (phase === 'flow' && builderFlow) {
    return withClose(
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
            });
            captureException(error);
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
    );
  }

  const variant = resolveVariant(configRef.current.variant);
  const rendererProps = {
    config: configRef.current,
    products,
    placeholders,
    goal,
    onPurchase: handlePurchase,
    onRestore: handleRestore,
    onRetry: handleRetry,
    purchasing,
  };

  switch (variant) {
    case 'B':
      return withClose(<VariantB {...rendererProps} />);
    case 'B2':
      return withClose(<VariantB2 {...rendererProps} />);
    case 'C':
      return withClose(<VariantC {...rendererProps} />);
    case 'S':
      return withClose(<VariantSHero {...rendererProps} />);
    default:
      return withClose(<PaywallRenderer {...rendererProps} />);
  }
}

const s = StyleSheet.create({
  fill: { flex: 1, backgroundColor: colors.bg },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
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
