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

function Quote({ text, author }: { text: string; author: string }) {
  return (
    <View style={s.quoteBox}>
      <AppText variant="small" color={colors.inkMuted} style={s.quoteText}>
        “{text}”
      </AppText>
      <AppText variant="caption" color={colors.inkFaint}>— {author}</AppText>
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
            color={done ? colors.success : colors.terracotta}
            strokeWidth={1.5}
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
  const recTag = plan.rec_tag_by_goal?.[goal ?? 'default'] ?? plan.rec_tag_by_goal?.default;
  const hasIntroOffer = (product?.subscription?.offer?.phases ?? []).some(
    (ph) => ph.paymentMode === 'free_trial',
  );

  // StoreKit unavailable (e.g. subscriptions pending Apple review) —
  // show reference prices from the config so cards never render empty.
  if (!product) {
    return (
      <Pressable onPress={onSelect} style={[s.planCard, selected && s.planCardActive]}>
        {plan.badge && (
          <View style={s.planBadge}>
            <AppText variant="overline" color={colors.white}>{plan.badge}</AppText>
          </View>
        )}
        <View style={s.planRow}>
          <View style={[s.radio, selected && s.radioActive]}>
            {selected && <View style={s.radioDot} />}
          </View>
          <View style={s.planInfo}>
            <AppText variant="bodyStrong">{plan.display_price ?? '—'}</AppText>
            {(plan.display_sub ?? plan.sub) && (
              <AppText variant="caption" color={colors.inkMuted}>
                {fill(plan.display_sub ?? plan.sub ?? '')}
              </AppText>
            )}
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

  return (
    <Pressable
      onPress={onSelect}
      style={[s.planCard, selected && s.planCardActive]}
    >
      {plan.badge && (
        <View style={s.planBadge}>
          <AppText variant="overline" color={colors.white}>
            {hasIntroOffer ? plan.badge : plan.badge.replace(/\s*·\s*3 DAYS FREE/, '')}
          </AppText>
        </View>
      )}
      <View style={s.planRow}>
        <View style={[s.radio, selected && s.radioActive]}>
          {selected && <View style={s.radioDot} />}
        </View>
        <View style={s.planInfo}>
          {isYearly && plan.price_style === 'per_month_big' && monthlyLabel ? (
            <>
              <AppText variant="title">{monthlyLabel}/mo</AppText>
              <AppText variant="caption" color={colors.inkMuted}>
                {hasIntroOffer ? '3 days free, then ' : ''}{priceLabel}/yr
              </AppText>
            </>
          ) : (
            <>
              <AppText variant="bodyStrong">{priceLabel}</AppText>
              {plan.sub && (
                <AppText variant="caption" color={colors.inkMuted}>
                  {fill(plan.sub)}
                </AppText>
              )}
            </>
          )}
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

  const selectedPlan = config.plans.find((p) => p.product === selectedProduct);
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

  const showTimeline = isYearly && config.timeline;
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

      <ScrollView
        contentContainerStyle={s.scroll}
        showsVerticalScrollIndicator={false}
        bounces={false}
      >
        {/* Headline */}
        <AppText variant="h1" center style={s.headline}>
          {config.headline}
        </AppText>

        {/* Goal hero — hidden when placeholder data is missing */}
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

        {/* Social proof */}
        <Laurels items={socialLaurelsResolved} />
        <Quote text={config.social.quote.text} author={config.social.quote.author} />

        {/* Timeline */}
        {showTimeline && config.timeline && (
          <View style={s.timeline}>
            {config.timeline.steps.map((step, i) => (
              <TimelineRow
                key={step.t}
                icon={step.icon}
                title={step.t}
                desc={step.d}
                done={step.done}
                last={i === config.timeline!.steps.length - 1}
              />
            ))}
          </View>
        )}

        {/* Plan selector */}
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

        {/* Above CTA reassurance */}
        <AppText variant="caption" color={colors.success} center style={s.aboveCta}>
          {config.above_cta}
        </AppText>

        {/* CTA */}
        <Button
          label={purchasing ? 'Processing…' : ctaLabel}
          variant="brand"
          loading={purchasing}
          onPress={handlePurchase}
          disabled={!selectedAdaptyProduct}
        />

        {/* Store unavailable — reference prices shown, offer a reload */}
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

        {/* Legal footer */}
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
    paddingTop: space.sm,
    paddingBottom: space.xs,
  },
  topBarSpacer: { width: 50 },
  scroll: { paddingHorizontal: space.lg, paddingBottom: space.xxxl },
  headline: { marginTop: space.md, marginBottom: space.lg },

  // Hero
  heroCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
    padding: space.lg,
    alignItems: 'center',
    gap: space.xs,
    marginBottom: space.base,
  },
  heroLine: { textAlign: 'center' },

  // Social proof
  laurels: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: space.sm,
    marginBottom: space.md,
  },
  laurel: {
    backgroundColor: colors.surfaceAlt,
    paddingHorizontal: space.md,
    paddingVertical: space.xs,
    borderRadius: radius.pill,
  },
  quoteBox: {
    alignItems: 'center',
    marginBottom: space.lg,
    paddingHorizontal: space.base,
    paddingVertical: space.md,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
  },
  quoteText: { fontStyle: 'italic', textAlign: 'center', marginBottom: space.xs },

  // Timeline
  timeline: { marginBottom: space.lg },
  tlRow: { flexDirection: 'row', gap: space.md },
  tlIconCol: { alignItems: 'center', width: 28 },
  tlIcon: {
    width: 28,
    height: 28,
    borderRadius: radius.pill,
    backgroundColor: colors.terracottaSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tlIconDone: { backgroundColor: colors.successSoft },
  tlLine: {
    width: 2,
    flex: 1,
    minHeight: 14,
    backgroundColor: colors.hairline,
    marginVertical: 2,
  },
  tlContent: { flex: 1, paddingBottom: space.md, gap: 2 },

  // Plans
  plans: { gap: space.md, marginBottom: space.base },
  planCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors.hairline,
    padding: space.base,
  },
  planCardActive: { borderColor: colors.terracotta },
  planBadge: {
    alignSelf: 'flex-start',
    backgroundColor: colors.terracotta,
    paddingHorizontal: space.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
    marginBottom: space.sm,
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
  recTag: { marginTop: space.sm },

  // CTA area
  aboveCta: { marginBottom: space.md },
  storeNotice: { marginTop: space.base, gap: space.md, alignItems: 'center' },
  disclosure: { marginTop: space.md, lineHeight: 16 },
  legalRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    marginTop: space.base,
  },
});
