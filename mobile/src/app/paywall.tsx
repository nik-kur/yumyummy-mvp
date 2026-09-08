/**
 * Paywall screen — code-rendered via PaywallRenderer.
 *
 * Flow: fetch placement 'main' from Adapty → parse remote config →
 * logShowPaywall → render → purchase/restore → next screen.
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
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { View, Pressable, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { X } from 'lucide-react-native';
import { adapty } from 'react-native-adapty';
import type { AdaptyPaywall, AdaptyPaywallProduct } from 'react-native-adapty';

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
  ADAPTY_PLACEMENT_MAIN,
  PREMIUM_ACCESS_LEVEL,
} from '@/billing/adapty';
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
import { USE_MOCKS } from '@/api/client';

type Phase = 'loading' | 'ready' | 'fallback';

/** Cap the fetch so a slow network shows the fallback instead of a blank screen. */
const PAYWALL_LOAD_TIMEOUT_MS = 5000;

/** How long to keep waiting for Apple Ads attribution before giving up on it. */
const APPLE_ADS_ATTRIBUTION_TIMEOUT_MS = 20000;

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
  const paywallRef = useRef<AdaptyPaywall | null>(null);
  const [products, setProducts] = useState<AdaptyPaywallProduct[]>([]);
  const configRef = useRef(FALLBACK_CONFIG);
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
    try {
      const pw = await adapty.getPaywall(ADAPTY_PLACEMENT_MAIN, undefined, {
        loadTimeoutMs: PAYWALL_LOAD_TIMEOUT_MS,
      });
      if (!alive()) return;
      paywallRef.current = pw;

      const config = parseRemoteConfig(pw.remoteConfig?.dataString);
      configRef.current = config;

      const prods = await adapty.getPaywallProducts(pw);
      if (!alive()) return;
      setProducts(prods);

      await adapty.logShowPaywall(pw);
      track('paywall_shown', {
        placement: ADAPTY_PLACEMENT_MAIN,
        variant: config.variant,
        products_available: prods.length > 0,
      });
      addBreadcrumb('paywall', 'Paywall shown', { variant: config.variant });

      setPhase('ready');
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
  }, []);

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
  useEffect(() => {
    if (phase !== 'ready' || upgradedRef.current) return;
    const mountedRef = { current: true };

    void (async () => {
      const applied = await waitForAppleAdsAttribution(APPLE_ADS_ATTRIBUTION_TIMEOUT_MS);
      if (!applied || !mountedRef.current || upgradedRef.current) return;
      // Never pull the paywall out from under an in-flight StoreKit sheet.
      if (purchasingRef.current) return;

      try {
        const targeted = await adapty.getPaywall(ADAPTY_PLACEMENT_MAIN, undefined, {
          loadTimeoutMs: PAYWALL_LOAD_TIMEOUT_MS,
        });
        if (!mountedRef.current || purchasingRef.current) return;
        if (targeted.variationId === paywallRef.current?.variationId) return;

        const targetedProducts = await adapty.getPaywallProducts(targeted);
        if (!mountedRef.current || purchasingRef.current) return;

        const previousVariant = configRef.current.variant;
        upgradedRef.current = true;
        paywallRef.current = targeted;
        configRef.current = parseRemoteConfig(targeted.remoteConfig?.dataString);
        setProducts(targetedProducts);

        await adapty.logShowPaywall(targeted);
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

  const handleRetry = useCallback(() => {
    track('paywall_retry_pressed');
    void loadPaywall();
  }, [loadPaywall]);

  const handlePurchase = useCallback(async (product: AdaptyPaywallProduct) => {
    setPurchasing(true);
    const variant = configRef.current.variant;
    addBreadcrumb('purchase', 'Purchase started', { product: product.vendorProductId });
    track('paywall_plan_selected', { product: product.vendorProductId, variant });

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
        const hasTrial = freeTrialPhase(product) !== undefined;
        track('paywall_purchase_success', {
          product: product.vendorProductId,
          variant,
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
        addBreadcrumb('purchase', 'Purchase succeeded', { signed_in: signedIn });
        await startJourney(); // journey Day 1 = purchase moment
        // A reminder is only honest when a trial is actually running: customers
        // who already used their one intro offer are charged immediately.
        if (hasTrial) {
          await scheduleTrialEndingReminder(new Date());
        }
        if (!signedIn) {
          // Acquisition flow: the receipt is on an anonymous Adapty profile.
          // Create the account next; the gate attaches the purchase to it.
          await handOffToSignIn('purchase', product.vendorProductId);
          return;
        }
        await refreshProfile();
        router.replace('/postbuy');
      } else if (result.type === 'user_cancelled') {
        // User backed out of the StoreKit sheet — expected, not an error.
        track('paywall_purchase_cancelled', { product: product.vendorProductId });
        addBreadcrumb('purchase', 'Purchase cancelled by user');
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
  }, [refreshProfile, router, signedIn, handOffToSignIn]);

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
        track('paywall_restore_success', { signed_in: signedIn });
        // Idempotent — a reinstall gets the first-week ladder, an existing
        // journey is left where it is.
        await startJourney();
        if (!signedIn) {
          // Returning customer on a fresh install: access is proven on the
          // anonymous Adapty profile; the gate signs them in and reconciles.
          await handOffToSignIn('restore', null);
          return;
        }
        await refreshProfile();
        router.replace('/postbuy');
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
  }, [refreshProfile, router, signedIn, handOffToSignIn]);

  const handleClose = useCallback(() => {
    track('paywall_closed', { dismissable: true });
    if (router.canGoBack()) router.back();
    else router.replace('/(tabs)');
  }, [router]);

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

  if (phase === 'loading') {
    return withClose(
      <Screen edges={['top', 'bottom', 'left', 'right']}>
        <View style={s.loading}>
          <ActivityIndicator color={colors.terracotta} />
        </View>
      </Screen>,
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
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  fill: { flex: 1 },
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
