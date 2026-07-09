/**
 * Paywall screen — code-rendered via PaywallRenderer.
 *
 * Flow: fetch placement 'main' from Adapty → parse remote config →
 * logShowPaywall → render → purchase/restore → post-purchase.
 *
 * Hard paywall: no close button, gesture-dismiss disabled. Exits only via
 * successful purchase or restore.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { View, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { adapty } from 'react-native-adapty';
import type { AdaptyPaywall, AdaptyPaywallProduct } from 'react-native-adapty';

import { Screen } from '@/components/Screen';
import { PaywallRenderer } from '@/components/paywall/PaywallRenderer';
import { VariantB } from '@/components/paywall/VariantB';
import { VariantB2 } from '@/components/paywall/VariantB2';
import { VariantC } from '@/components/paywall/VariantC';
import { useAuth } from '@/state/auth';
import { loadDraft, type IntroDraft } from '@/state/introDraft';
import {
  activateAdapty,
  isAdaptyConfigured,
  ADAPTY_PLACEMENT_MAIN,
  PREMIUM_ACCESS_LEVEL,
} from '@/billing/adapty';
import {
  parseRemoteConfig,
  resolveVariant,
  FALLBACK_CONFIG,
  type PlaceholderValues,
} from '@/billing/paywallConfig';
import { track } from '@/analytics/posthog';
import { addBreadcrumb, captureException } from '@/analytics/sentry';
import { colors } from '@/theme/tokens';
import * as api from '@/api/endpoints';
import { USE_MOCKS } from '@/api/client';

type Phase = 'loading' | 'ready' | 'fallback';

export default function PaywallScreen() {
  const router = useRouter();
  const { profile, refreshProfile } = useAuth();

  const [phase, setPhase] = useState<Phase>('loading');
  const [purchasing, setPurchasing] = useState(false);
  const paywallRef = useRef<AdaptyPaywall | null>(null);
  const [products, setProducts] = useState<AdaptyPaywallProduct[]>([]);
  const configRef = useRef(FALLBACK_CONFIG);
  // Pre-auth users have no profile — plan numbers live in the intro draft.
  const [draft, setDraft] = useState<IntroDraft | null>(null);

  useEffect(() => {
    loadDraft().then(setDraft).catch(() => {});
  }, []);

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
      if (alive()) setPhase('fallback');
      return;
    }
    try {
      const pw = await adapty.getPaywall(ADAPTY_PLACEMENT_MAIN);
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
      if (alive()) setPhase('fallback');
    }
  }, []);

  useEffect(() => {
    const mountedRef = { current: true };
    void loadPaywall(mountedRef);
    return () => { mountedRef.current = false; };
  }, [loadPaywall]);

  const handleRetry = useCallback(() => {
    track('paywall_retry_pressed');
    void loadPaywall();
  }, [loadPaywall]);

  const handlePurchase = useCallback(async (product: AdaptyPaywallProduct) => {
    setPurchasing(true);
    addBreadcrumb('purchase', 'Purchase started', { product: product.vendorProductId });
    track('paywall_plan_selected', { product: product.vendorProductId });

    try {
      if (!isAdaptyConfigured()) {
        await api.startTrial(3);
        await refreshProfile();
        track('paywall_purchase_success', { product: product.vendorProductId, mode: 'dev_trial' });
        router.replace('/post-purchase');
        return;
      }

      const result = await adapty.makePurchase(product);
      if (result.type === 'success') {
        track('paywall_purchase_success', { product: product.vendorProductId });
        addBreadcrumb('purchase', 'Purchase succeeded');
        await refreshProfile();
        router.replace('/post-purchase');
      }
    } catch (e) {
      track('paywall_purchase_failed', { product: product.vendorProductId });
      captureException(e);
    } finally {
      setPurchasing(false);
    }
  }, [refreshProfile, router]);

  const handleRestore = useCallback(async () => {
    setPurchasing(true);
    addBreadcrumb('purchase', 'Restore started');
    track('paywall_restore_started');

    try {
      if (!isAdaptyConfigured()) {
        router.replace('/post-purchase');
        return;
      }
      const adaptyProfile = await adapty.restorePurchases();
      if (adaptyProfile.accessLevels?.[PREMIUM_ACCESS_LEVEL]?.isActive) {
        track('paywall_restore_success');
        await refreshProfile();
        router.replace('/post-purchase');
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
  }, [refreshProfile, router]);

  if (phase === 'loading') {
    return (
      <Screen edges={['top', 'bottom', 'left', 'right']}>
        <View style={s.loading}>
          <ActivityIndicator color={colors.terracotta} />
        </View>
      </Screen>
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
      return <VariantB {...rendererProps} />;
    case 'B2':
      return <VariantB2 {...rendererProps} />;
    case 'C':
      return <VariantC {...rendererProps} />;
    default:
      return <PaywallRenderer {...rendererProps} />;
  }
}

const s = StyleSheet.create({
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
