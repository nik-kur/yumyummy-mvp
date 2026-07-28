/**
 * Paywall variant S ("hero timeline") — the single-plan layout.
 *
 * The multi-plan layout (`PaywallRenderer`) is built around comparing cards, so
 * with one plan its content collapses to the top of the screen and leaves the
 * CTA stranded mid-viewport. Here the trial timeline is the argument and takes
 * the centre of the screen, the plan is a single compact card stating what will
 * be charged, and the reassurance line plus CTA are pinned to the bottom where
 * a thumb expects them.
 *
 * Same iron rule as everywhere else: prices and trial eligibility come from
 * `products` (StoreKit), never from `config`.
 */
import { useCallback, useMemo } from 'react';
import { View, Pressable, StyleSheet, ScrollView, Linking } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Star, CircleCheck, type LucideIcon, LockOpen, Bell } from 'lucide-react-native';
import type { AdaptyPaywallProduct } from 'react-native-adapty';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { colors, radius, space } from '@/theme/tokens';
import type {
  PaywallRemoteConfig,
  PlaceholderValues,
  TimelineStep,
} from '@/billing/paywallConfig';
import {
  billingCadence,
  fillPlaceholders,
  findProduct,
  hasUnresolvedPlaceholders,
  periodPriceLabel,
  resolveCtaKey,
  trialLength,
  PAID_TIMELINE_STEPS,
} from '@/billing/paywallConfig';

const TERMS_URL = 'https://yumyummy.ai/terms.html';
const PRIVACY_URL = 'https://yumyummy.ai/privacy.html';
const DONE_GREEN = '#16A34A';

const TL_ICONS: Record<string, LucideIcon> = {
  '✓': CircleCheck,
  '🔓': LockOpen,
  '🔔': Bell,
  '★': Star,
};

interface VariantSHeroProps {
  config: PaywallRemoteConfig;
  products: AdaptyPaywallProduct[];
  placeholders: PlaceholderValues;
  goal?: string | null;
  onPurchase: (product: AdaptyPaywallProduct) => void;
  onRestore: () => void;
  onRetry?: () => void;
  purchasing: boolean;
}

/** A timeline row at hero scale — bigger dial, thicker rail, room to breathe. */
function HeroTimelineRow({
  step,
  last,
}: {
  step: TimelineStep;
  last: boolean;
}) {
  const Icon = TL_ICONS[step.icon] ?? Star;
  return (
    <View style={s.tlRow}>
      <View style={s.tlIconCol}>
        <View style={[s.tlIcon, step.done && s.tlIconDone]}>
          <Icon
            size={20}
            color={step.done ? colors.white : colors.terracotta}
            strokeWidth={step.done ? 2.5 : 1.75}
          />
        </View>
        {!last && <View style={s.tlLine} />}
      </View>
      <View style={s.tlContent}>
        <AppText variant="title">{step.t}</AppText>
        <AppText variant="small" color={colors.inkMuted} style={s.tlDesc}>
          {step.d}
        </AppText>
      </View>
    </View>
  );
}

export function VariantSHero({
  config,
  products,
  placeholders,
  goal,
  onPurchase,
  onRestore,
  onRetry,
  purchasing,
}: VariantSHeroProps) {
  const fill = useCallback(
    (t: string) => fillPlaceholders(t, placeholders),
    [placeholders],
  );

  const plan = config.plans[0];
  const product = findProduct(products, plan?.product ?? '');
  const trial = trialLength(product);
  const hasTrial = trial !== undefined;

  const ctaLabel = useMemo(() => {
    const key = resolveCtaKey(config, product, plan?.product ?? '');
    return fill(config.cta[key] ?? 'Continue');
  }, [config, product, plan?.product, fill]);

  // Never render a literal "{TARGET_WEIGHT}": prefer the goal line, fall back to
  // the maintenance line, and drop the row entirely rather than show a token.
  const heroLine = useMemo(() => {
    const goalLine = fill(config.hero.goal_line);
    const maintainLine = fill(config.hero.maintain_line);
    const preferGoal = goal === 'lose' || goal === 'gain';
    if (preferGoal && !hasUnresolvedPlaceholders(goalLine)) return goalLine;
    if (!hasUnresolvedPlaceholders(maintainLine)) return maintainLine;
    return null;
  }, [goal, config.hero, fill]);

  const timelineSteps = useMemo(
    () => (hasTrial && config.timeline ? config.timeline.steps : PAID_TIMELINE_STEPS),
    [hasTrial, config.timeline],
  );

  const priceText = periodPriceLabel(product);
  const cadence = billingCadence(product);

  const planMain = product ? priceText : (plan?.display_price ?? '—');
  const planSub = (() => {
    if (!product) return fill(plan?.display_sub ?? plan?.sub ?? '');
    if (trial) return `${trial} free, then ${cadence}`;
    return cadence || fill(plan?.sub ?? '');
  })();

  const aboveCtaText = hasTrial
    ? config.above_cta || '✓ No payment due now · Cancel anytime'
    : '✓ Cancel anytime';

  const productsAvailable = products.length > 0;

  const handlePurchase = useCallback(() => {
    if (product) onPurchase(product);
  }, [product, onPurchase]);

  return (
    <SafeAreaView style={s.root} edges={['top', 'bottom']}>
      <View style={s.topBar}>
        <View style={s.topBarSpacer} />
        <Pressable onPress={onRestore} hitSlop={12}>
          <AppText variant="caption" color={colors.inkFaint}>Restore</AppText>
        </Pressable>
      </View>

      {/* Header + timeline scroll if a small screen demands it; the footer below
          never moves, so the CTA is always where the thumb reaches. */}
      <ScrollView
        contentContainerStyle={s.scroll}
        showsVerticalScrollIndicator={false}
        bounces={false}
      >
        <AppText variant="h1" center style={s.headline}>
          {config.headline}
        </AppText>
        {heroLine && (
          <AppText variant="small" color={colors.inkMuted} center style={s.heroLine}>
            {heroLine}
          </AppText>
        )}

        <View style={s.timeline}>
          {timelineSteps.map((step, i) => (
            <HeroTimelineRow
              key={step.t}
              step={step}
              last={i === timelineSteps.length - 1}
            />
          ))}
        </View>
      </ScrollView>

      <View style={s.footer}>
        <View style={s.planCard}>
          <View style={s.planInfo}>
            <AppText variant="h2">{planMain}</AppText>
            {planSub ? (
              <AppText variant="caption" color={colors.inkMuted}>{planSub}</AppText>
            ) : null}
          </View>
          <CircleCheck size={24} color={colors.terracotta} strokeWidth={2} />
        </View>

        <AppText variant="caption" color={DONE_GREEN} center>
          {aboveCtaText}
        </AppText>

        <Button
          label={purchasing ? 'Processing…' : ctaLabel}
          variant="brand"
          loading={purchasing}
          onPress={handlePurchase}
          disabled={!product}
        />

        {!productsAvailable && (
          <View style={s.storeNotice}>
            <AppText variant="caption" color={colors.inkMuted} center>
              Prices shown for reference — the App Store connection isn’t available right now.
            </AppText>
            {onRetry && (
              <Button label="Retry" variant="secondary" size="md" onPress={onRetry} />
            )}
          </View>
        )}

        <AppText variant="caption" color={colors.inkFaint} center style={s.disclosure}>
          {hasTrial
            ? 'After the free trial, your subscription auto-renews at the price shown unless cancelled at least 24 hours before the end of the current period.'
            : 'Subscription auto-renews at the price shown unless cancelled at least 24 hours before the end of the current period.'}
        </AppText>
        <View style={s.legalRow}>
          <Pressable onPress={onRestore}>
            <AppText variant="caption" color={colors.inkFaint}>Restore</AppText>
          </Pressable>
          <AppText variant="caption" color={colors.inkFaint}> · </AppText>
          <Pressable onPress={() => Linking.openURL(TERMS_URL)}>
            <AppText variant="caption" color={colors.inkFaint}>Terms</AppText>
          </Pressable>
          <AppText variant="caption" color={colors.inkFaint}> · </AppText>
          <Pressable onPress={() => Linking.openURL(PRIVACY_URL)}>
            <AppText variant="caption" color={colors.inkFaint}>Privacy</AppText>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: space.lg,
    paddingVertical: space.xs,
  },
  // `justifyContent: center` on a grown container is what keeps the timeline
  // optically centred on tall screens instead of hugging the headline.
  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: space.lg,
    paddingBottom: space.base,
  },
  topBarSpacer: { width: 50 },
  headline: { marginBottom: space.sm },
  heroLine: { marginBottom: space.xl },

  // Timeline — the centrepiece, so everything about it is a size up from the
  // multi-plan layout: 40px dials, a 3px rail, body-sized descriptions.
  timeline: { paddingHorizontal: space.xs },
  tlRow: { flexDirection: 'row', gap: space.base },
  tlIconCol: { alignItems: 'center', width: 40 },
  tlIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.pill,
    backgroundColor: colors.terracottaSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tlIconDone: { backgroundColor: DONE_GREEN },
  tlLine: {
    width: 3,
    flex: 1,
    minHeight: 20,
    borderRadius: 2,
    backgroundColor: colors.terracottaSoft,
    marginVertical: space.xs,
  },
  tlContent: { flex: 1, paddingBottom: space.lg, gap: 2 },
  tlDesc: { lineHeight: 20 },

  // Footer — plan, reassurance, CTA and legal, pinned as one block.
  footer: { paddingHorizontal: space.lg, paddingBottom: space.sm, gap: space.md },
  planCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors.terracotta,
    paddingVertical: space.md,
    paddingHorizontal: space.base,
  },
  planInfo: { flex: 1, gap: 2 },
  storeNotice: { gap: space.md, alignItems: 'center' },
  disclosure: { lineHeight: 15 },
  legalRow: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center' },
});
