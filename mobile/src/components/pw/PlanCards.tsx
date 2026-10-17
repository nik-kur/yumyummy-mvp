/**
 * Plan cards, one per product on the arm's flow (1–3), shortest period first.
 * `dark` = on the B3 photo (white text on the photo's dark end);
 * `light` = P1 plans (paper cards, radio on the right).
 * The yearly card carries "SAVE N%" against the monthly one.
 *
 * Price emphasis (`price_emphasis`):
 *   billed — the billed amount is always the big number (default, App Review
 *            3.1.2(c));
 *   design — yearly shows the per-month figure big and the billed amount below
 *            on B3 (as drawn); P1 already leads with the billed amount;
 *   weekly — every plan shows its per-week figure big, the billed amount below.
 */
import { Pressable, StyleSheet, Text, View } from 'react-native';
import type { AdaptyPaywallProduct } from 'react-native-adapty';
import * as Haptics from 'expo-haptics';

import { billed, perMonth, perWeek, periodOf, planName, savePercent, unitWord } from '@/billing/v3Pricing';
import { C, F } from '@/onb/theme';

import { Check } from './PwParts';

interface Props {
  products: AdaptyPaywallProduct[];
  selectedId: string | null;
  onSelect: (p: AdaptyPaywallProduct) => void;
  tone: 'dark' | 'light';
  emphasis: 'design' | 'billed' | 'weekly';
}

function lines(p: AdaptyPaywallProduct, tone: 'dark' | 'light', emphasis: 'design' | 'billed' | 'weekly') {
  const per = periodOf(p);
  const pm = perMonth(p);
  const pw = perWeek(p);
  if (emphasis === 'weekly' && pw && per !== 'other') {
    if (per === 'week') return { big: `${billed(p)} /wk`, small: 'billed weekly' };
    return { big: `${pw} /wk`, small: `${billed(p)} per ${unitWord(p)}` };
  }
  if (tone === 'light') {
    if (per === 'year') return { big: billed(p), small: pm ? `${pm} / month` : 'per year' };
    if (per === 'month') return { big: billed(p), small: 'per month' };
    if (per === 'week') return { big: billed(p), small: 'per week' };
    return { big: billed(p), small: `per ${unitWord(p)}` };
  }
  if (per === 'year') {
    return emphasis === 'billed' || !pm
      ? { big: `${billed(p)} /yr`, small: pm ? `${pm} /mo` : 'per year' }
      : { big: `${pm} /mo`, small: `${billed(p)} per year` };
  }
  if (per === 'month') return { big: `${billed(p)} /mo`, small: 'billed monthly' };
  if (per === 'week') return { big: `${billed(p)} /wk`, small: 'billed weekly' };
  return { big: billed(p), small: `every ${unitWord(p)}` };
}

export function PlanCards({ products, selectedId, onSelect, tone, emphasis }: Props) {
  const save = savePercent(products);
  const narrow = products.length >= 3;
  // Three light cards side by side leave ~45 pt for the price: stack them.
  const stacked = tone === 'light' && narrow;
  return (
    <View style={stacked ? s.column : s.row}>
      {products.map((p) => {
        const on = p.vendorProductId === selectedId;
        const l = lines(p, tone, emphasis);
        const badge = save && periodOf(p) === 'year' ? `SAVE ${save}%` : null;
        const press = () => {
          void Haptics.selectionAsync().catch(() => {});
          onSelect(p);
        };
        if (tone === 'dark') {
          return (
            <Pressable
              key={p.vendorProductId}
              onPress={press}
              style={[s.card, s.darkCard, on ? s.darkOn : s.darkOff]}
              accessibilityRole="radio"
              accessibilityState={{ selected: on }}
            >
              {badge ? (
                <View style={s.badge}>
                  <Text style={s.badgeText}>{badge}</Text>
                </View>
              ) : null}
              <Text style={s.darkName}>{planName(p)}</Text>
              <Text style={[s.darkBig, narrow && s.bigNarrow]}>{l.big}</Text>
              <Text style={s.darkSmall}>{l.small}</Text>
            </Pressable>
          );
        }
        return (
          <Pressable
            key={p.vendorProductId}
            onPress={press}
            style={[stacked ? s.cardStacked : s.card, s.lightCard, on ? s.lightOn : s.lightOff]}
            accessibilityRole="radio"
            accessibilityState={{ selected: on }}
          >
            {badge ? (
              <View style={s.badge}>
                <Text style={s.badgeText}>{badge}</Text>
              </View>
            ) : null}
            <View style={s.lightText}>
              <Text style={s.lightName}>{planName(p)}</Text>
              <Text style={[s.lightBig, narrow && !stacked && s.bigNarrow]}>{l.big}</Text>
              <Text style={s.lightSmall}>{l.small}</Text>
            </View>
            {on ? (
              <View style={s.radioOn}>
                <Check color="#FFFFFF" size={14} width={3} />
              </View>
            ) : (
              <View style={s.radioOff} />
            )}
          </Pressable>
        );
      })}
    </View>
  );
}

const s = StyleSheet.create({
  row: { flexDirection: 'row', gap: 10 },
  column: { gap: 14 },
  card: { flex: 1 },
  cardStacked: { alignSelf: 'stretch' },
  darkCard: { borderRadius: 14, paddingVertical: 14, paddingHorizontal: 12, alignItems: 'center', gap: 2 },
  darkOn: { backgroundColor: 'rgba(255,255,255,0.12)', borderWidth: 2, borderColor: '#FFFFFF' },
  darkOff: { backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.25)' },
  darkName: { fontFamily: F.sans, fontSize: 14, lineHeight: 18, color: 'rgba(255,255,255,0.75)' },
  darkBig: { fontFamily: F.sansSemibold, fontSize: 20, lineHeight: 26, color: '#FFFFFF' },
  darkSmall: { fontFamily: F.sans, fontSize: 12, lineHeight: 16, color: 'rgba(255,255,255,0.6)' },
  bigNarrow: { fontSize: 17, lineHeight: 22 },
  lightCard: {
    borderRadius: 16,
    paddingTop: 14,
    paddingRight: 12,
    paddingBottom: 12,
    paddingLeft: 14,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: 1.5,
  },
  lightOn: { backgroundColor: C.terraSoft, borderColor: C.terra },
  lightOff: { backgroundColor: C.surface, borderColor: C.hair },
  lightText: { flex: 1, gap: 2 },
  lightName: { fontFamily: F.sans, fontSize: 14, lineHeight: 18, color: C.muted },
  lightBig: { fontFamily: F.sansSemibold, fontSize: 20, lineHeight: 26, color: C.ink },
  lightSmall: { fontFamily: F.sans, fontSize: 12, lineHeight: 16, color: C.muted },
  radioOn: { width: 24, height: 24, borderRadius: 12, backgroundColor: C.terra, alignItems: 'center', justifyContent: 'center' },
  radioOff: { width: 24, height: 24, borderRadius: 12, borderWidth: 1.5, borderColor: C.hair2 },
  badge: {
    position: 'absolute',
    top: -11,
    right: 10,
    zIndex: 1,
    backgroundColor: C.ok,
    borderRadius: 999,
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  badgeText: { fontFamily: F.sansSemibold, fontSize: 11, lineHeight: 14, letterSpacing: 0.44, color: '#FFFFFF' },
});
