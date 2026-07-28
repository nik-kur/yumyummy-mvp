/**
 * Paywall variant S ("hero timeline") — the single-plan layout.
 *
 * The multi-plan layout (`PaywallRenderer`) is built around comparing cards, so
 * with one plan its content collapses to the top of the screen and leaves the
 * CTA stranded mid-viewport. Here the trial timeline is the argument and takes
 * the centre of the screen, and the reassurance line plus CTA are pinned to the
 * bottom where a thumb expects them.
 *
 * With one plan there is nothing to compare, so there is no price card either:
 * the decision is "start the trial or don't", and a card would only invite the
 * customer to weigh a number instead. The price lives in the terms line under
 * the CTA, which is where Apple requires it and where it stops competing with
 * the button.
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
  fillPlaceholders,
  findProduct,
  hasUnresolvedPlaceholders,
  resolveCtaKey,
  subscriptionTerms,
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
      <View style={[s.tlContent, last && s.tlContentLast]}>
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

  const laurels = useMemo(
    () => config.social.laurels.map(fill).filter((l) => !hasUnresolvedPlaceholders(l)),
    [config.social.laurels, fill],
  );

  // Store data when we have it; the config's display copy is the offline
  // stand-in, since without a price this line would say nothing at all.
  const terms = product
    ? subscriptionTerms(product)
    : fill(plan?.display_sub ?? plan?.sub ?? '');

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
        {laurels.length > 0 && (
          <View style={s.laurels}>
            {laurels.map((l) => (
              <View key={l} style={s.laurel}>
                <AppText variant="caption" color={colors.inkMuted}>{l}</AppText>
              </View>
            ))}
          </View>
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
          {terms}
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
  scroll: { flexGrow: 1, paddingHorizontal: space.lg, paddingBottom: space.base },
  topBarSpacer: { width: 50 },
  // Dropped off the top bar rather than pinned to it: with only the timeline
  // below, a headline flush against "Restore" leaves the whole screen
  // top-heavy.
  headline: { marginTop: space.xl, marginBottom: space.sm },
  heroLine: { marginBottom: space.sm },
  laurels: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: space.sm,
  },
  laurel: {
    backgroundColor: colors.surfaceAlt,
    paddingHorizontal: space.md,
    paddingVertical: space.xs,
    borderRadius: radius.pill,
  },

  // Timeline — the centrepiece, so everything about it is a size up from the
  // multi-plan layout: 40px dials, a 3px rail, body-sized descriptions.
  // `flexGrow` (not `flex`) claims the space between header and footer without
  // letting the rows shrink when a small screen can't spare it.
  timeline: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: space.xs,
    paddingVertical: space.lg,
  },
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
  tlContentLast: { paddingBottom: 0 },
  tlDesc: { lineHeight: 20 },

  // Footer — reassurance, CTA, terms and legal, pinned as one block.
  footer: { paddingHorizontal: space.lg, paddingBottom: space.sm, gap: space.md },
  storeNotice: { gap: space.md, alignItems: 'center' },
  disclosure: { lineHeight: 15 },
  legalRow: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center' },
});
