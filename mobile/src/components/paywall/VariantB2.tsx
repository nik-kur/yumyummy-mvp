/**
 * Paywall Variant B2 — "Less than your morning coffee" with coffee-compare card.
 */
import { useCallback, useMemo, useState } from 'react';
import { View, Pressable, StyleSheet, ScrollView } from 'react-native';
import type { AdaptyPaywallProduct } from 'react-native-adapty';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { colors, radius, space } from '@/theme/tokens';
import type { PaywallRemoteConfig, PlaceholderValues } from '@/billing/paywallConfig';
import { fillPlaceholders, findProduct, perMonthPrice } from '@/billing/paywallConfig';

interface VariantB2Props {
  config: PaywallRemoteConfig;
  products: AdaptyPaywallProduct[];
  placeholders: PlaceholderValues;
  goal?: string | null;
  onPurchase: (product: AdaptyPaywallProduct) => void;
  onRestore: () => void;
  purchasing: boolean;
}

export function VariantB2({
  config, products, placeholders, goal, onPurchase, onRestore, purchasing,
}: VariantB2Props) {
  const fill = useCallback((t: string) => fillPlaceholders(t, placeholders), [placeholders]);
  const raw = config as any;
  const compare = raw.compare_card ?? { left: { emoji: '☕', label: 'A coffee', price: '$5.00' }, right: { emoji: '🍏', label: 'YumYummy / day', price: '$0.25' } };

  const [selected, setSelected] = useState(config.plans[0]?.product ?? 'ai.yumyummy.app.yearly');
  const selectedProduct = findProduct(products, selected);
  const isYearly = selected.includes('yearly');

  const ctaLabel = useMemo(() => {
    const key = selected.includes('yearly') ? 'yearly' : selected.includes('monthly') ? 'monthly' : 'weekly';
    return fill(config.cta[key] ?? 'Continue');
  }, [selected, config.cta, fill]);

  return (
    <View style={s.root}>
      <View style={s.topBar}>
        <View style={s.spacer} />
        <Pressable onPress={onRestore} hitSlop={12}>
          <AppText variant="caption" color={colors.inkFaint}>Restore</AppText>
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={s.scroll} showsVerticalScrollIndicator={false} bounces={false}>
        <AppText variant="h1" center style={s.headline}>{config.headline}</AppText>

        <View style={s.compareRow}>
          <View style={s.compareCard}>
            <AppText variant="display">{compare.left.emoji}</AppText>
            <AppText variant="bodyStrong">{compare.left.label}</AppText>
            <AppText variant="caption" color={colors.inkMuted}>{compare.left.price}</AppText>
          </View>
          <AppText variant="h2" color={colors.inkMuted}>vs</AppText>
          <View style={[s.compareCard, s.compareCardHighlight]}>
            <AppText variant="display">{compare.right.emoji}</AppText>
            <AppText variant="bodyStrong">{compare.right.label}</AppText>
            <AppText variant="caption" color={colors.terracottaText}>{compare.right.price}</AppText>
          </View>
        </View>

        <View style={s.plans}>
          {config.plans.map((plan) => {
            const prod = findProduct(products, plan.product);
            const active = selected === plan.product;
            const price = prod?.price;
            return (
              <Pressable
                key={plan.product}
                onPress={() => setSelected(plan.product)}
                style={[s.planCard, active && s.planActive]}
              >
                <View style={[s.radio, active && s.radioActive]}>
                  {active && <View style={s.radioDot} />}
                </View>
                <View style={s.planInfo}>
                  <AppText variant="bodyStrong">
                    {price ? `${price.currencySymbol ?? ''}${price.amount?.toFixed(2) ?? ''}` : plan.product}
                  </AppText>
                  {plan.sub && <AppText variant="caption" color={colors.inkMuted}>{fill(plan.sub)}</AppText>}
                </View>
                {plan.badge && active && (
                  <View style={s.badge}>
                    <AppText variant="overline" color={colors.white}>{plan.badge}</AppText>
                  </View>
                )}
              </Pressable>
            );
          })}
        </View>

        <AppText variant="caption" color={colors.success} center style={s.aboveCta}>
          {config.above_cta}
        </AppText>

        <Button
          label={purchasing ? 'Processing…' : ctaLabel}
          variant="brand"
          loading={purchasing}
          onPress={() => selectedProduct && onPurchase(selectedProduct)}
          disabled={!selectedProduct}
        />

        <AppText variant="caption" color={colors.inkFaint} center style={s.disclosure}>
          Subscription auto-renews unless cancelled. Manage in Apple Account settings.
        </AppText>
        <View style={s.legalRow}>
          <Pressable onPress={onRestore}><AppText variant="caption" color={colors.inkFaint}>Restore</AppText></Pressable>
          <AppText variant="caption" color={colors.inkFaint}> · Terms · Privacy</AppText>
        </View>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  topBar: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: space.lg, paddingTop: space.sm },
  spacer: { width: 50 },
  scroll: { paddingHorizontal: space.lg, paddingBottom: space.xxxl },
  headline: { marginTop: space.md, marginBottom: space.lg },
  compareRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.md, marginBottom: space.lg },
  compareCard: {
    flex: 1, backgroundColor: colors.surface, borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.hairline,
    padding: space.base, alignItems: 'center', gap: space.xs,
  },
  compareCardHighlight: { borderColor: colors.terracotta, borderWidth: 1.5 },
  plans: { gap: space.md, marginBottom: space.base },
  planCard: {
    flexDirection: 'row', alignItems: 'center', gap: space.md,
    backgroundColor: colors.surface, borderRadius: radius.lg,
    borderWidth: 1.5, borderColor: colors.hairline, padding: space.base,
  },
  planActive: { borderColor: colors.terracotta },
  radio: { width: 22, height: 22, borderRadius: radius.pill, borderWidth: 1.5, borderColor: colors.hairline, alignItems: 'center', justifyContent: 'center' },
  radioActive: { borderColor: colors.terracotta },
  radioDot: { width: 11, height: 11, borderRadius: radius.pill, backgroundColor: colors.terracotta },
  planInfo: { flex: 1 },
  badge: { backgroundColor: colors.terracotta, paddingHorizontal: space.sm, paddingVertical: 2, borderRadius: radius.sm },
  aboveCta: { marginBottom: space.md },
  disclosure: { marginTop: space.md, lineHeight: 16 },
  legalRow: { flexDirection: 'row', justifyContent: 'center', marginTop: space.base },
});
