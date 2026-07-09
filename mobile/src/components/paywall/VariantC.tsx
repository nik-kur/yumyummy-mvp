/**
 * Paywall Variant C — "Your result is ready" with a single result card
 * and "Show more plans" expand.
 */
import { useCallback, useMemo, useState } from 'react';
import { View, Pressable, StyleSheet, ScrollView } from 'react-native';
import type { AdaptyPaywallProduct } from 'react-native-adapty';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { colors, radius, space } from '@/theme/tokens';
import type { PaywallRemoteConfig, PlaceholderValues } from '@/billing/paywallConfig';
import { fillPlaceholders, findProduct, perMonthPrice } from '@/billing/paywallConfig';

interface VariantCProps {
  config: PaywallRemoteConfig;
  products: AdaptyPaywallProduct[];
  placeholders: PlaceholderValues;
  goal?: string | null;
  onPurchase: (product: AdaptyPaywallProduct) => void;
  onRestore: () => void;
  purchasing: boolean;
}

export function VariantC({
  config, products, placeholders, goal, onPurchase, onRestore, purchasing,
}: VariantCProps) {
  const fill = useCallback((t: string) => fillPlaceholders(t, placeholders), [placeholders]);
  const raw = config as any;
  const resultCard = raw.result_card ?? { title: 'Your plan snapshot', lines: [] };

  const [selectedProduct, setSelectedProduct] = useState(config.plans[0]?.product ?? 'ai.yumyummy.app.yearly');
  const [showMore, setShowMore] = useState(false);
  const adaptyProduct = findProduct(products, selectedProduct);

  const ctaLabel = useMemo(() => {
    const key = selectedProduct.includes('yearly') ? 'yearly' : selectedProduct.includes('monthly') ? 'monthly' : 'weekly';
    return fill(config.cta[key] ?? 'Continue');
  }, [selectedProduct, config.cta, fill]);

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

        <Card style={s.resultCard}>
          <AppText variant="title" center>{resultCard.title}</AppText>
          <View style={s.resultLines}>
            {resultCard.lines.map((line: any, i: number) => (
              <View key={i} style={s.resultRow}>
                <AppText variant="body" color={colors.inkMuted}>{line.label}</AppText>
                <AppText variant="bodyStrong">{fill(line.value)}</AppText>
              </View>
            ))}
          </View>
        </Card>

        {/* Primary CTA for yearly */}
        {!showMore && (
          <>
            <View style={s.primaryPlan}>
              {config.plans[0]?.badge && (
                <View style={s.badge}>
                  <AppText variant="overline" color={colors.white}>{config.plans[0].badge}</AppText>
                </View>
              )}
              <AppText variant="title">
                {perMonthPrice(findProduct(products, config.plans[0]?.product ?? '') as any) ?? ''}/mo
              </AppText>
              <AppText variant="caption" color={colors.inkMuted}>
                {adaptyProduct?.price ? `${adaptyProduct.price.currencySymbol ?? ''}${adaptyProduct.price.amount?.toFixed(2) ?? ''}/yr` : ''}
              </AppText>
            </View>

            <Pressable onPress={() => setShowMore(true)} style={s.showMore}>
              <AppText variant="small" color={colors.terracottaText}>
                {raw.show_more_plans_label ?? 'Show more plans'}
              </AppText>
            </Pressable>
          </>
        )}

        {showMore && (
          <View style={s.allPlans}>
            {config.plans.map((plan) => {
              const prod = findProduct(products, plan.product);
              const active = selectedProduct === plan.product;
              const price = prod?.price;
              return (
                <Pressable
                  key={plan.product}
                  onPress={() => setSelectedProduct(plan.product)}
                  style={[s.planCard, active && s.planActive]}
                >
                  <View style={[s.radio, active && s.radioActive]}>
                    {active && <View style={s.radioDot} />}
                  </View>
                  <View style={s.planInfo}>
                    <AppText variant="bodyStrong">
                      {price ? `${price.currencySymbol ?? ''}${price.amount?.toFixed(2) ?? ''}` : ''}
                    </AppText>
                    {plan.sub && <AppText variant="caption" color={colors.inkMuted}>{fill(plan.sub)}</AppText>}
                  </View>
                </Pressable>
              );
            })}
          </View>
        )}

        <AppText variant="caption" color={colors.success} center style={s.aboveCta}>
          {config.above_cta}
        </AppText>

        <Button
          label={purchasing ? 'Processing…' : ctaLabel}
          variant="brand"
          loading={purchasing}
          onPress={() => adaptyProduct && onPurchase(adaptyProduct)}
          disabled={!adaptyProduct}
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
  resultCard: { marginBottom: space.lg },
  resultLines: { gap: space.md, marginTop: space.md },
  resultRow: { flexDirection: 'row', justifyContent: 'space-between' },
  primaryPlan: {
    backgroundColor: colors.surface, borderRadius: radius.lg,
    borderWidth: 1.5, borderColor: colors.terracotta,
    padding: space.base, alignItems: 'center', gap: space.xs, marginBottom: space.md,
  },
  badge: { backgroundColor: colors.terracotta, paddingHorizontal: space.sm, paddingVertical: 2, borderRadius: radius.sm },
  showMore: { alignItems: 'center', marginBottom: space.lg },
  allPlans: { gap: space.md, marginBottom: space.base },
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
  aboveCta: { marginBottom: space.md },
  disclosure: { marginTop: space.md, lineHeight: 16 },
  legalRow: { flexDirection: 'row', justifyContent: 'center', marginTop: space.base },
});
