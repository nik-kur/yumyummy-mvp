/**
 * Code-rendered paywall — variant A ("clean v3").
 *
 * Prices and intro-offer eligibility come ONLY from `products` (localised
 * StoreKit data), never from `config`. The config drives copy, layout flags,
 * and placeholder values.
 *
 * No close button: the screen is exited only via purchase or Restore.
 */
import { useCallback, useMemo, useState } from 'react';
import {
  View,
  Pressable,
  StyleSheet,
  ScrollView,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Star, CircleCheck, type LucideIcon, LockOpen, Bell } from 'lucide-react-native';
import type { AdaptyPaywallProduct } from 'react-native-adapty';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { colors, radius, space } from '@/theme/tokens';
import type {
  PaywallRemoteConfig,
  PlaceholderValues,
  PlanConfig,
} from '@/billing/paywallConfig';
import {
  fillPlaceholders,
  findProduct,
  hasUnresolvedPlaceholders,
  perMonthPrice,
} from '@/billing/paywallConfig';

const TERMS_URL = 'https://yumyummy.ai/terms.html';
const PRIVACY_URL = 'https://yumyummy.ai/privacy.html';
const DONE_GREEN = '#16A34A';

const PAID_TIMELINE_STEPS = [
  { icon: '✓', t: 'Done', d: 'Your personal plan — built', done: true },
  { icon: '🔓', t: 'Today', d: 'Full access unlocked' },
  {
    icon: '🔔',
    t: 'Day 2',
    d: "You'll set up your full tracking system and see how simple it is",
  },
  {
    icon: '★',
    t: 'Day 3',
    d: "You'll start noticing changes in your routine and eating trends",
  },
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PaywallRendererProps {
  config: PaywallRemoteConfig;
  products: AdaptyPaywallProduct[];
  placeholders: PlaceholderValues;
  goal?: string | null;
  onPurchase: (product: AdaptyPaywallProduct) => void;
  onRestore: () => void;
  /** Re-fetch paywall + products (shown when the store returned no products). */
  onRetry?: () => void;
  purchasing: boolean;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Laurels({ items }: { items: string[] }) {
  return (
    <View style={s.laurels}>
      {items.map((l) => (
        <View key={l} style={s.laurel}>
          <AppText variant="caption" color={colors.inkMuted}>{l}</AppText>
        </View>
      ))}
    </View>
  );
}

const TL_ICONS: Record<string, LucideIcon> = {
  '✓': CircleCheck,
  '🔓': LockOpen,
  '🔔': Bell,
  '★': Star,
};

function TimelineRow({
  icon,
  title,
  desc,
  done,
  last,
}: {
  icon: string;
  title: string;
  desc: string;
  done?: boolean;
  last?: boolean;
}) {
  const Icon = TL_ICONS[icon] ?? Star;
  return (
    <View style={s.tlRow}>
      <View style={s.tlIconCol}>
        <View style={[s.tlIcon, done && s.tlIconDone]}>
          <Icon
            size={14}
            color={done ? colors.white : colors.terracotta}
            strokeWidth={done ? 2.5 : 1.5}
          />
        </View>
        {!last && <View style={s.tlLine} />}
      </View>
      <View style={s.tlContent}>
        <AppText variant="bodyStrong">{title}</AppText>
        <AppText variant="caption" color={colors.inkMuted}>{desc}</AppText>
      </View>
    </View>
  );
}

function PlanCard({
  plan,
  product,
  selected,
  goal,
  onSelect,
  fill,
}: {
  plan: PlanConfig;
  product: AdaptyPaywallProduct | undefined;
  selected: boolean;
  goal?: string | null;
  onSelect: () => void;
  fill: (t: string) => string;
}) {
  const priceLabel = product?.price
    ? `${product.price.currencySymbol ?? ''}${product.price.amount?.toFixed(2) ?? ''}`
    : '';
  const monthlyLabel = product ? perMonthPrice(product) : undefined;
  const isYearly = plan.product.includes('yearly');
  const isMonthly = plan.product.includes('monthly');
  const isWeekly = plan.product.includes('weekly');
  const recTag = plan.rec_tag_by_goal?.[goal ?? 'default'] ?? plan.rec_tag_by_goal?.default;
  const hasIntroOffer = (product?.subscription?.offer?.phases ?? []).some(
    (ph) => ph.paymentMode === 'free_trial',
  );

  const mainLabel = (() => {
    if (!product) return plan.display_price ?? '—';
    if (isYearly) return '3 days free trial';
    if (isMonthly) return `${priceLabel}/mo`;
    if (isWeekly) return `${priceLabel}/wk`;
    return priceLabel;
  })();

  const subLabel = (() => {
    if (!product) return fill(plan.display_sub ?? plan.sub ?? '');
    if (isYearly && monthlyLabel) {
      return `No payment due now. Then ${monthlyLabel}/mo billed annually at ${priceLabel}.`;
    }
    if (isMonthly) return 'billed monthly';
    if (isWeekly) return 'billed weekly';
    return fill(plan.sub ?? '');
  })();

  return (
    <Pressable onPress={onSelect} style={[s.planCard, selected && s.planCardActive]}>
      {plan.badge && (
        <View style={s.planBadge}>
          <AppText variant="overline" color={colors.white}>
            {isYearly && product && !hasIntroOffer
              ? plan.badge.replace(/\s*·\s*3 DAYS FREE/, '')
              : plan.badge}
          </AppText>
        </View>
      )}
      <View style={s.planRow}>
        <View style={[s.radio, selected && s.radioActive]}>
          {selected && <View style={s.radioDot} />}
        </View>
        <View style={s.planInfo}>
          <AppText variant="title">{mainLabel}</AppText>
          {subLabel ? (
            <AppText variant="caption" color={colors.inkMuted}>{subLabel}</AppText>
          ) : null}
        </View>
      </View>
      {recTag && selected && (
        <AppText variant="caption" color={colors.protein} style={s.recTag}>
          {recTag}
        </AppText>
      )}
    </Pressable>
  );
}

// ---------------------------------------------------------------------------
// Main renderer
// ---------------------------------------------------------------------------

export function PaywallRenderer({
  config,
  products,
  placeholders,
  goal,
  onPurchase,
  onRestore,
  onRetry,
  purchasing,
}: PaywallRendererProps) {
  const fill = useCallback(
    (t: string) => fillPlaceholders(t, placeholders),
    [placeholders],
  );

  const [selectedProduct, setSelectedProduct] = useState<string>(
    config.plans[0]?.product ?? 'ai.yumyummy.app.yearly',
  );

  const selectedAdaptyProduct = findProduct(products, selectedProduct);
  const isYearly = selectedProduct.includes('yearly');

  const ctaLabel = useMemo(() => {
    const key = selectedProduct.includes('yearly')
      ? 'yearly'
      : selectedProduct.includes('monthly')
        ? 'monthly'
        : 'weekly';
    const template = config.cta[key] ?? 'Continue';
    return fill(template);
  }, [selectedProduct, config.cta, fill]);

  // Never render a literal "{TARGET_WEIGHT}": fall back goal_line →
  // maintain_line → hide the hero card entirely.
  const heroLine = useMemo(() => {
    const goalLine = fill(config.hero.goal_line);
    const maintainLine = fill(config.hero.maintain_line);
    const preferGoal = goal === 'lose' || goal === 'gain';
    if (preferGoal && !hasUnresolvedPlaceholders(goalLine)) return goalLine;
    if (!hasUnresolvedPlaceholders(maintainLine)) return maintainLine;
    return null;
  }, [goal, config.hero, fill]);

  const timelineSteps = useMemo(
    () => (isYearly && config.timeline ? config.timeline.steps : PAID_TIMELINE_STEPS),
    [isYearly, config.timeline],
  );

  const aboveCtaText = isYearly
    ? '✓ No payment due now · Cancel anytime'
    : '✓ Cancel anytime';

  const socialLaurelsResolved = useMemo(
    () => config.social.laurels.map(fill),
    [config.social.laurels, fill],
  );

  const productsAvailable = products.length > 0;

  const handlePurchase = useCallback(() => {
    if (!selectedAdaptyProduct) return;
    onPurchase(selectedAdaptyProduct);
  }, [selectedAdaptyProduct, onPurchase]);

  return (
    <SafeAreaView style={s.root} edges={['top', 'bottom']}>
      {/* Restore — top right */}
      <View style={s.topBar}>
        <View style={s.topBarSpacer} />
        <Pressable onPress={onRestore} hitSlop={12}>
          <AppText variant="caption" color={colors.inkFaint}>Restore</AppText>
        </Pressable>
      </View>

      {/* Single scroll surface. Everything through the CTA is compacted to fit
          the first viewport; only the legal disclaimers live below the fold. */}
      <ScrollView
        contentContainerStyle={s.scroll}
        showsVerticalScrollIndicator={false}
        bounces={false}
      >
        <AppText variant="h1" center style={s.headline}>
          {config.headline}
        </AppText>

        {heroLine && (
          <View style={s.heroCard}>
            <AppText variant="overline" color={colors.terracottaText}>
              {fill(config.hero.label)}
            </AppText>
            <AppText variant="h2" style={s.heroLine}>
              {heroLine}
            </AppText>
          </View>
        )}

        <Laurels items={socialLaurelsResolved} />

        <View style={s.timeline}>
          {timelineSteps.map((step, i) => (
            <TimelineRow
              key={step.t}
              icon={step.icon}
              title={step.t}
              desc={step.d}
              done={step.done}
              last={i === timelineSteps.length - 1}
            />
          ))}
        </View>

        <View style={s.plans}>
          {config.plans.map((plan) => (
            <PlanCard
              key={plan.product}
              plan={plan}
              product={findProduct(products, plan.product)}
              selected={selectedProduct === plan.product}
              goal={goal}
              onSelect={() => setSelectedProduct(plan.product)}
              fill={fill}
            />
          ))}
        </View>

        <AppText variant="caption" color={DONE_GREEN} center style={s.aboveCta}>
          {aboveCtaText}
        </AppText>

        <Button
          label={purchasing ? 'Processing…' : ctaLabel}
          variant="brand"
          loading={purchasing}
          onPress={handlePurchase}
          disabled={!selectedAdaptyProduct}
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

        {/* Below the fold — legal disclaimers */}
        <AppText variant="caption" color={colors.inkFaint} center style={s.disclosure}>
          {isYearly
            ? 'After the free trial, your subscription auto-renews at the price shown unless cancelled at least 24 hours before the end of the current period.'
            : 'Subscription auto-renews at the price shown unless cancelled at least 24 hours before the end of the current period.'}{' '}
          Manage or cancel anytime in your Apple Account settings.
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
      </ScrollView>
    </SafeAreaView>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: space.lg,
    paddingTop: space.xs,
    paddingBottom: space.xs,
  },
  topBarSpacer: { width: 50 },
  scroll: { paddingHorizontal: space.lg, paddingBottom: space.lg },
  headline: { marginTop: space.xs, marginBottom: space.sm },

  // Hero
  heroCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
    paddingVertical: space.md,
    paddingHorizontal: space.base,
    alignItems: 'center',
    gap: 2,
    marginBottom: space.sm,
  },
  heroLine: { textAlign: 'center' },

  // Social proof
  laurels: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: space.sm,
    marginBottom: space.sm,
  },
  laurel: {
    backgroundColor: colors.surfaceAlt,
    paddingHorizontal: space.md,
    paddingVertical: space.xs,
    borderRadius: radius.pill,
  },
  // Timeline
  timeline: { marginBottom: space.sm },
  tlRow: { flexDirection: 'row', gap: space.md },
  tlIconCol: { alignItems: 'center', width: 26 },
  tlIcon: {
    width: 26,
    height: 26,
    borderRadius: radius.pill,
    backgroundColor: colors.terracottaSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tlIconDone: { backgroundColor: DONE_GREEN },
  tlLine: {
    width: 2,
    flex: 1,
    minHeight: 8,
    backgroundColor: colors.hairline,
    marginVertical: 2,
  },
  tlContent: { flex: 1, paddingBottom: space.sm, gap: 1 },

  // Plans
  plans: { gap: space.sm, marginBottom: space.md },
  planCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors.hairline,
    paddingVertical: space.md,
    paddingHorizontal: space.base,
  },
  planCardActive: { borderColor: colors.terracotta },
  planBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.terracotta,
    paddingHorizontal: space.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
    marginBottom: space.xs,
  },
  planRow: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  radio: {
    width: 22,
    height: 22,
    borderRadius: radius.pill,
    borderWidth: 1.5,
    borderColor: colors.hairline,
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioActive: { borderColor: colors.terracotta },
  radioDot: {
    width: 11,
    height: 11,
    borderRadius: radius.pill,
    backgroundColor: colors.terracotta,
  },
  planInfo: { flex: 1 },
  recTag: { marginTop: space.xs },

  // CTA area
  aboveCta: { marginBottom: space.sm },
  storeNotice: { marginTop: space.base, gap: space.md, alignItems: 'center' },
  disclosure: { marginTop: space.lg, lineHeight: 16 },
  legalRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: space.base,
  },
});
