import { useCallback, useEffect, useRef, useState } from 'react';
import { View, StyleSheet, Pressable, Linking, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { X, CircleCheck, LockOpen, Bell, Star, type LucideIcon } from 'lucide-react-native';
import { adapty, AdaptyPaywallView } from 'react-native-adapty';
import type { AdaptyPaywall, EventHandlers } from 'react-native-adapty';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import * as api from '@/api/endpoints';
import { useAuth } from '@/state/auth';
import {
  activateAdapty,
  isAdaptyConfigured,
  ADAPTY_PLACEMENT_MAIN,
  PREMIUM_ACCESS_LEVEL,
} from '@/billing/adapty';
import { colors, radius, space } from '@/theme/tokens';

/**
 * Paywall screen.
 *
 * Primary path: fetch the `main` placement from Adapty and, when it carries a
 * Paywall Builder view configuration, render it with `AdaptyPaywallView`. Adapty
 * handles the StoreKit purchase, the App Store free-trial intro offer, receipt
 * validation and restore; we just react to events and refresh our account.
 *
 * Fallback path (Expo Go / no SDK key / offline / no view config): the static
 * marketing UI below keeps the screen usable. In dev (no key) its CTA starts the
 * backend trial so the rest of the app stays testable; when Adapty is configured
 * it attempts a direct product purchase.
 */
interface PriceOption {
  id: 'yearly' | 'monthly';
  title: string;
  price: string;
  perDay: string;
  badge?: string;
}
interface PaywallConfig {
  headline: string;
  subhead: string;
  benefits: string[];
  showTrialTimeline: boolean;
  prices: PriceOption[];
}

// Fallback-only copy. The live paywall (design, prices, trial length, A/B) is
// driven by Adapty; StoreKit supplies localized prices there. These values just
// mirror the current pricing decision for the degraded/offline view.
const DEFAULT_PAYWALL: PaywallConfig = {
  headline: 'Know exactly what you eat',
  subhead: 'Accurate, source‑checked nutrition — by text, voice or photo.',
  benefits: [
    'AI meal logging by text, voice & photo',
    'Source‑checked calories & macros',
    'Personal AI nutrition advisor',
    'Synced across app & Telegram',
  ],
  showTrialTimeline: true,
  prices: [
    { id: 'yearly', title: 'Yearly', price: '$89.99 / yr', perDay: '≈ $0.25 / day', badge: 'Best value' },
    { id: 'monthly', title: 'Monthly', price: '$9.99 / mo', perDay: '≈ $0.33 / day' },
  ],
};

/** Free-trial length per plan, mirroring the App Store Connect intro offers
 *  (yearly = 7 days, monthly = 3 days). The live Adapty paywall uses the real
 *  StoreKit offer; this only feeds the degraded/offline fallback copy. */
const TRIAL_DAYS: Record<PriceOption['id'], number> = { yearly: 7, monthly: 3 };

type Phase = 'loading' | 'adapty' | 'fallback';

function TimelineStep({ icon: Icon, title, subtitle, last }: { icon: LucideIcon; title: string; subtitle: string; last?: boolean }) {
  return (
    <View style={styles.tlStep}>
      <View style={styles.tlIconCol}>
        <View style={styles.tlIcon}>
          <Icon size={16} color={colors.terracotta} strokeWidth={1.5} />
        </View>
        {!last ? <View style={styles.tlLine} /> : null}
      </View>
      <View style={styles.tlText}>
        <AppText variant="bodyStrong">{title}</AppText>
        <AppText variant="caption" color={colors.inkMuted}>
          {subtitle}
        </AppText>
      </View>
    </View>
  );
}

export default function PaywallScreen() {
  const router = useRouter();
  const { refreshProfile } = useAuth();
  const config = DEFAULT_PAYWALL;

  const [phase, setPhase] = useState<Phase>('loading');
  const paywallRef = useRef<AdaptyPaywall | null>(null);

  const [selected, setSelected] = useState<PriceOption['id']>('yearly');
  const [busy, setBusy] = useState(false);
  const trialDays = TRIAL_DAYS[selected];

  const close = useCallback(() => router.back(), [router]);

  // Fetch the Adapty paywall for the `main` placement on mount.
  useEffect(() => {
    let mounted = true;
    (async () => {
      const ok = await activateAdapty();
      if (!ok) {
        if (mounted) setPhase('fallback');
        return;
      }
      try {
        const pw = await adapty.getPaywall(ADAPTY_PLACEMENT_MAIN);
        if (!mounted) return;
        paywallRef.current = pw;
        setPhase(pw.hasViewConfiguration ? 'adapty' : 'fallback');
      } catch {
        if (mounted) setPhase('fallback');
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  // ---- Adapty Paywall Builder event handlers ----
  const onPurchaseCompleted = useCallback<EventHandlers['onPurchaseCompleted']>(
    (purchaseResult) => {
      if (purchaseResult.type === 'success') {
        void refreshProfile();
        router.back();
      }
      // 'user_cancelled' / 'pending': keep the paywall open
    },
    [refreshProfile, router],
  );

  const onRestoreCompleted = useCallback<EventHandlers['onRestoreCompleted']>(
    (profile) => {
      if (profile.accessLevels?.[PREMIUM_ACCESS_LEVEL]?.isActive) {
        void refreshProfile();
        router.back();
      }
    },
    [refreshProfile, router],
  );

  const onUrlPress = useCallback<EventHandlers['onUrlPress']>((url) => {
    Linking.openURL(url).catch(() => {});
  }, []);

  const onRenderingFailed = useCallback<EventHandlers['onRenderingFailed']>(() => {
    setPhase('fallback');
  }, []);

  // ---- Fallback purchase paths ----
  const manualPurchase = useCallback(async (planId: PriceOption['id']) => {
    const pw = paywallRef.current ?? (await adapty.getPaywall(ADAPTY_PLACEMENT_MAIN));
    const products = await adapty.getPaywallProducts(pw);
    if (!products.length) return;
    const needle = planId === 'yearly' ? 'year' : 'month';
    const product =
      products.find((p) => (p.vendorProductId ?? '').toLowerCase().includes(needle)) ?? products[0];
    const res = await adapty.makePurchase(product);
    if (res.type === 'success') void refreshProfile();
  }, [refreshProfile]);

  const onStart = useCallback(async () => {
    setBusy(true);
    try {
      if (!isAdaptyConfigured()) {
        // Dev / Expo Go: no native Adapty — start the backend trial so the rest
        // of the app unlocks for testing.
        await api.startTrial(trialDays);
        await refreshProfile();
      } else {
        await manualPurchase(selected);
      }
    } catch {
      // silent — user can retry
    } finally {
      setBusy(false);
      router.back();
    }
  }, [trialDays, manualPurchase, refreshProfile, router, selected]);

  const onRestore = useCallback(async () => {
    if (!isAdaptyConfigured()) {
      router.back();
      return;
    }
    setBusy(true);
    try {
      const profile = await adapty.restorePurchases();
      if (profile.accessLevels?.[PREMIUM_ACCESS_LEVEL]?.isActive) await refreshProfile();
    } catch {
      // ignore
    } finally {
      setBusy(false);
      router.back();
    }
  }, [refreshProfile, router]);

  // ---- Render: Paywall Builder ----
  if (phase === 'adapty' && paywallRef.current) {
    return (
      <View style={styles.fill}>
        <AdaptyPaywallView
          paywall={paywallRef.current}
          style={styles.fill}
          onCloseButtonPress={close}
          onPurchaseCompleted={onPurchaseCompleted}
          onRestoreCompleted={onRestoreCompleted}
          onUrlPress={onUrlPress}
          onRenderingFailed={onRenderingFailed}
        />
      </View>
    );
  }

  // ---- Render: loading ----
  if (phase === 'loading') {
    return (
      <Screen edges={['top', 'bottom', 'left', 'right']}>
        <View style={styles.topBar}>
          <View style={{ width: 26 }} />
          <Pressable onPress={close} hitSlop={10}>
            <X size={26} color={colors.inkMuted} strokeWidth={1.5} />
          </Pressable>
        </View>
        <View style={styles.loading}>
          <ActivityIndicator color={colors.terracotta} />
        </View>
      </Screen>
    );
  }

  // ---- Render: static fallback ----
  return (
    <Screen scroll edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.topBar}>
        <View style={{ width: 26 }} />
        <Pressable onPress={close} hitSlop={10}>
          <X size={26} color={colors.inkMuted} strokeWidth={1.5} />
        </Pressable>
      </View>

      <AppText variant="overline" color={colors.terracottaText}>
        YumYummy Premium
      </AppText>
      <AppText variant="display" style={styles.headline}>
        {config.headline}
      </AppText>
      <AppText variant="body" color={colors.inkMuted} style={styles.subhead}>
        {config.subhead}
      </AppText>

      <View style={styles.benefits}>
        {config.benefits.map((b) => (
          <View key={b} style={styles.benefitRow}>
            <CircleCheck size={20} color={colors.success} strokeWidth={1.5} />
            <AppText variant="body" style={styles.benefitText}>
              {b}
            </AppText>
          </View>
        ))}
      </View>

      {config.showTrialTimeline ? (
        <View style={styles.timeline}>
          <TimelineStep icon={LockOpen} title="Today" subtitle="Full access unlocks instantly" />
          <TimelineStep
            icon={Bell}
            title={`Day ${Math.max(1, trialDays - 1)}`}
            subtitle="We’ll remind you before the trial ends"
          />
          <TimelineStep
            icon={Star}
            title={`Day ${trialDays}`}
            subtitle="Trial ends — cancel anytime before"
            last
          />
        </View>
      ) : null}

      <View style={styles.prices}>
        {config.prices.map((p) => {
          const active = selected === p.id;
          return (
            <Pressable
              key={p.id}
              onPress={() => setSelected(p.id)}
              style={[styles.price, active && styles.priceActive]}
            >
              <View style={styles.priceLeft}>
                <View style={[styles.radio, active && styles.radioActive]}>
                  {active ? <View style={styles.radioDot} /> : null}
                </View>
                <View>
                  <AppText variant="bodyStrong">{p.title}</AppText>
                  <AppText variant="caption" color={colors.inkMuted}>
                    {p.perDay}
                  </AppText>
                </View>
              </View>
              <View style={styles.priceRight}>
                {p.badge ? (
                  <View style={styles.badge}>
                    <AppText variant="overline" color={colors.white}>
                      {p.badge}
                    </AppText>
                  </View>
                ) : null}
                <AppText variant="bodyStrong">{p.price}</AppText>
              </View>
            </Pressable>
          );
        })}
      </View>

      <Button
        label={busy ? 'Starting…' : `Start ${trialDays}‑day free trial`}
        variant="brand"
        loading={busy}
        onPress={onStart}
        style={styles.cta}
      />

      <AppText variant="caption" color={colors.inkMuted} style={styles.disclosure}>
        {selected === 'yearly'
          ? '7‑day free trial, then $89.99/year'
          : '3‑day free trial, then $9.99/month'}. Subscription auto‑renews until
        cancelled — manage or cancel anytime in your Apple Account settings.
      </AppText>

      <View style={styles.footer}>
        <Pressable onPress={onRestore}>
          <AppText variant="caption" color={colors.inkFaint}>
            Restore
          </AppText>
        </Pressable>
        <AppText variant="caption" color={colors.inkFaint}>·</AppText>
        <Pressable onPress={() => Linking.openURL('https://yumyummy.ai/terms.html')}>
          <AppText variant="caption" color={colors.inkFaint}>
            Terms
          </AppText>
        </Pressable>
        <AppText variant="caption" color={colors.inkFaint}>·</AppText>
        <Pressable onPress={() => Linking.openURL('https://yumyummy.ai/privacy.html')}>
          <AppText variant="caption" color={colors.inkFaint}>
            Privacy
          </AppText>
        </Pressable>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: colors.bg },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: space.sm, marginBottom: space.md },
  headline: { marginTop: space.xs },
  subhead: { marginTop: space.sm, marginBottom: space.lg },
  benefits: { gap: space.md, marginBottom: space.lg },
  benefitRow: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  benefitText: { flex: 1 },
  timeline: { marginBottom: space.lg, gap: 0 },
  tlStep: { flexDirection: 'row', gap: space.md },
  tlIconCol: { alignItems: 'center', width: 32 },
  tlIcon: {
    width: 32,
    height: 32,
    borderRadius: radius.pill,
    backgroundColor: colors.terracottaSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tlLine: { width: 2, flex: 1, minHeight: 18, backgroundColor: colors.terracottaSoft, marginVertical: 2 },
  tlText: { flex: 1, paddingBottom: space.base, gap: 2 },
  prices: { gap: space.md, marginBottom: space.base },
  price: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors.hairline,
    padding: space.base,
  },
  priceActive: { borderColor: colors.terracotta },
  priceLeft: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  radio: { width: 22, height: 22, borderRadius: radius.pill, borderWidth: 1.5, borderColor: colors.hairline, alignItems: 'center', justifyContent: 'center' },
  radioActive: { borderColor: colors.terracotta },
  radioDot: { width: 11, height: 11, borderRadius: radius.pill, backgroundColor: colors.terracotta },
  priceRight: { alignItems: 'flex-end', gap: 4 },
  badge: { backgroundColor: colors.terracotta, paddingHorizontal: space.sm, paddingVertical: 2, borderRadius: radius.sm },
  cta: { marginTop: space.sm },
  disclosure: { marginTop: space.md, textAlign: 'center', lineHeight: 18 },
  footer: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: space.sm, marginTop: space.base },
});
