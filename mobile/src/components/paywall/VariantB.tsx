/**
 * Paywall Variant B — "Design your trial" with primary selector
 * (trial vs weekly) and a "View all plans" expand.
 */
import { useCallback, useMemo, useState } from 'react';
import { View, Pressable, StyleSheet, ScrollView } from 'react-native';
import type { AdaptyPaywallProduct } from 'react-native-adapty';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { colors, radius, space } from '@/theme/tokens';
import type { PaywallRemoteConfig, PlaceholderValues } from '@/billing/paywallConfig';
import { fillPlaceholders, findProduct, perMonthPrice } from '@/billing/paywallConfig';

interface VariantBProps {
  config: PaywallRemoteConfig;
  products: AdaptyPaywallProduct[];
  placeholders: PlaceholderValues;
  goal?: string | null;
  onPurchase: (product: AdaptyPaywallProduct) => void;
  onRestore: () => void;
  purchasing: boolean;
}

export function VariantB({
  config,
  products,
  placeholders,
  goal,
  onPurchase,
  onRestore,
  purchasing,
}: VariantBProps) {
  const fill = useCallback((t: string) => fillPlaceholders(t, placeholders), [placeholders]);
  const raw = config as any;
  const primaryOptions = raw.primary_selector?.options ?? [];
  const [selectedKey, setSelectedKey] = useState<string>(primaryOptions[0]?.key ?? 'trial');
  const [showAll, setShowAll] = useState(false);

  const selectedOption = primaryOptions.find((o: any) => o.key === selectedKey);
  const selectedProduct = selectedOption
    ? findProduct(products, selectedOption.product)
    : undefined;

  const ctaLabel = useMemo(() => {
    const productId = selectedProduct?.vendorProductId ?? '';
    const key = productId.includes('yearly') ? 'yearly' : productId.includes('monthly') ? 'monthly' : 'weekly';
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

        <View style={s.heroCard}>
          <AppText variant="overline" color={colors.terracottaText}>{fill(config.hero.label)}</AppText>
          <AppText variant="h2" center>
            {goal === 'maintain' || goal === 'just_track'
              ? fill(config.hero.maintain_line)
              : fill(config.hero.goal_line)}
          </AppText>
        </View>

        <View style={s.selector}>
          {primaryOptions.map((opt: any) => {
            const active = selectedKey === opt.key;
            return (
              <Pressable
                key={opt.key}
                onPress={() => setSelectedKey(opt.key)}
                style={[s.selectorCard, active && s.selectorCardActive]}
              >
                <AppText variant="bodyStrong">{opt.label}</AppText>
                <AppText variant="caption" color={colors.inkMuted}>{opt.desc}</AppText>
              </Pressable>
            );
          })}
        </View>

        {!showAll && (
          <Pressable onPress={() => setShowAll(true)} style={s.viewAll}>
            <AppText variant="small" color={colors.terracottaText}>
              {raw.view_all_plans_label ?? 'View all plans'}
            </AppText>
          </Pressable>
        )}

        {showAll && (
          <View style={s.allPlans}>
            {config.plans.map((plan) => {
              const prod = findProduct(products, plan.product);
              const price = prod?.price;
              return (
                <Pressable
                  key={plan.product}
                  onPress={() => {
                    const opt = primaryOptions.find((o: any) => o.product === plan.product);
                    if (opt) setSelectedKey(opt.key);
                  }}
                  style={s.planRow}
                >
                  <AppText variant="body">{plan.product.replace('ai.yumyummy.app.', '').replace(/_/g, ' ')}</AppText>
                  <AppText variant="bodyStrong">
                    {price ? `${price.currencySymbol ?? ''}${price.amount?.toFixed(2) ?? ''}` : ''}
                  </AppText>
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
          onPress={() => selectedProduct && onPurchase(selectedProduct)}
          disabled={!selectedProduct}
        />

        <AppText variant="caption" color={colors.inkFaint} center style={s.disclosure}>
          Subscription auto-renews unless cancelled at least 24h before the end of the current period.
          Manage or cancel anytime in your Apple Account settings.
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
  heroCard: {
    backgroundColor: colors.surface, borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.hairline,
    padding: space.lg, alignItems: 'center', gap: space.xs, marginBottom: space.base,
  },
  selector: { gap: space.md, marginBottom: space.base },
  selectorCard: {
    backgroundColor: colors.surface, borderRadius: radius.lg,
    borderWidth: 1.5, borderColor: colors.hairline, padding: space.base, gap: 2,
  },
  selectorCardActive: { borderColor: colors.terracotta, backgroundColor: colors.surfaceAlt },
  viewAll: { alignItems: 'center', marginBottom: space.lg },
  allPlans: { gap: space.sm, marginBottom: space.lg },
  planRow: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: colors.surface, borderRadius: radius.md, padding: space.md,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.hairline,
  },
  aboveCta: { marginBottom: space.md },
  disclosure: { marginTop: space.md, lineHeight: 16 },
  legalRow: { flexDirection: 'row', justifyContent: 'center', marginTop: space.base },
});
