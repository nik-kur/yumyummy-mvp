import { useState } from 'react';
import { View, StyleSheet, Pressable, Switch, Linking, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { X, CircleCheck, LockOpen, Bell, Star, Users, type LucideIcon } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import * as api from '@/api/endpoints';
import { colors, radius, space } from '@/theme/tokens';

/**
 * Remote-config-shaped paywall. In production every field below is driven by an
 * Adapty paywall + A/B test (headline, benefits, price block, trial length,
 * social-proof + trial-timeline toggles). Here it's local so the founder can
 * preview variants; see TODO(adapty).
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
  trialDays: number; // A/B: 3 vs 7, set by Adapty cohort
  showTrialTimeline: boolean;
  showSocialProof: boolean;
  socialProof: string;
  prices: PriceOption[];
}

// TODO(adapty): replace this static config with the Adapty paywall payload, and
// match `prices` to the same products/pricing as the Telegram bot.
const DEFAULT_PAYWALL: PaywallConfig = {
  headline: 'Know exactly what you eat',
  subhead: 'Accurate, source‑checked nutrition — by text, voice or photo.',
  benefits: [
    'Unlimited AI meal logging',
    'Source‑checked calories & macros',
    'Personal AI nutrition advisor',
    'Synced across app & Telegram',
  ],
  trialDays: 3,
  showTrialTimeline: true,
  showSocialProof: true,
  socialProof: 'Trusted by 12,000+ people logging smarter',
  prices: [
    { id: 'yearly', title: 'Yearly', price: '$39.99 / yr', perDay: '≈ $0.11 / day', badge: 'Best value' },
    { id: 'monthly', title: 'Monthly', price: '$4.99 / mo', perDay: '≈ $0.16 / day' },
  ],
};

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
  const config = DEFAULT_PAYWALL;

  const [selected, setSelected] = useState<PriceOption['id']>('yearly');
  const [showTimeline, setShowTimeline] = useState(config.showTrialTimeline);
  const [showSocial, setShowSocial] = useState(config.showSocialProof);
  const [busy, setBusy] = useState(false);

  const onStart = async () => {
    setBusy(true);
    try {
      // TODO(adapty): present Adapty paywall / make the StoreKit purchase here.
      // For now we start the backend trial so the rest of the app unlocks.
      await api.startTrial(config.trialDays);
    } catch {
      // ignore in scaffold
    } finally {
      setBusy(false);
      router.back();
    }
  };

  return (
    <Screen scroll edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.topBar}>
        <View style={{ width: 26 }} />
        <Pressable onPress={() => router.back()} hitSlop={10}>
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

      {showTimeline ? (
        <View style={styles.timeline}>
          <TimelineStep icon={LockOpen} title="Today" subtitle="Full access unlocks instantly" />
          <TimelineStep
            icon={Bell}
            title={`Day ${Math.max(1, config.trialDays - 1)}`}
            subtitle="We’ll remind you before the trial ends"
          />
          <TimelineStep
            icon={Star}
            title={`Day ${config.trialDays}`}
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

      {showSocial ? (
        <View style={styles.social}>
          <Users size={16} color={colors.inkMuted} strokeWidth={1.5} />
          <AppText variant="caption" color={colors.inkMuted}>
            {config.socialProof}
          </AppText>
        </View>
      ) : null}

      <Button
        label={busy ? 'Starting…' : `Start ${config.trialDays}‑day free trial`}
        variant="brand"
        loading={busy}
        onPress={onStart}
        style={styles.cta}
      />

      <View style={styles.footer}>
        <Pressable onPress={() => router.back()}>
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

      <View style={styles.devBox}>
        <AppText variant="overline" color={colors.inkFaint}>
          Preview controls (Adapty drives these live)
        </AppText>
        <View style={styles.devRow}>
          <AppText variant="caption" color={colors.inkMuted}>
            Trial timeline
          </AppText>
          <Switch value={showTimeline} onValueChange={setShowTimeline} />
        </View>
        <View style={styles.devRow}>
          <AppText variant="caption" color={colors.inkMuted}>
            Social proof
          </AppText>
          <Switch value={showSocial} onValueChange={setShowSocial} />
        </View>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
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
  social: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.sm, marginBottom: space.base },
  cta: { marginTop: space.sm },
  footer: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: space.sm, marginTop: space.base },
  devBox: {
    marginTop: space.xl,
    padding: space.base,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
    borderStyle: 'dashed',
    gap: space.sm,
  },
  devRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
});
