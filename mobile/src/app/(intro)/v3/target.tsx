/**
 * V3 screen 7 — Target weight on a ruler (0.2 kg steps; 1 lb with stones in
 * imperial). Asked for every goal (Miro "Логика цели"): the target sets the
 * plan, the goal from screen 2 only sets the tone.
 *
 * The BMI card updates live: inside the healthy range → green "A healthy goal
 * for your height"; below BMI 18.5 → amber "Below a healthy weight", and the
 * next screen proposes the healthy floor instead (TargetWeight_low).
 */
import { useCallback, useMemo, useState } from 'react';
import { StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { OnbButton } from '@/components/onb/OnbButton';
import { OnbLayout } from '@/components/onb/OnbLayout';
import { Ruler } from '@/components/onb/Ruler';
import { bmi, fmtKg, fmtStLb, healthyFloorKg, LB_PER_KG } from '@/onb/plan';
import { C, F, PAD } from '@/onb/theme';
import { useOnbScreen } from '@/onb/useOnbScreen';

type Card = { tone: 'ok' | 'warn' | 'info'; title: string; body: string };

function bmiCard(targetKg: number, currentKg: number, heightCm: number, show: (kg: number) => string): Card {
  const b = bmi(targetKg, heightCm);
  const b1 = b.toFixed(1);
  if (b < 18.5) {
    return {
      tone: 'warn',
      title: 'Below a healthy weight for your height',
      body: `${show(targetKg)} is a BMI of ${b1}. A healthy weight for your height starts at ${show(healthyFloorKg(heightCm))}.`,
    };
  }
  if (b < 25) {
    return { tone: 'ok', title: 'A healthy goal for your height', body: `${show(targetKg)} is a BMI of ${b1}, inside the healthy range.` };
  }
  if (targetKg < currentKg - 0.5) {
    return { tone: 'ok', title: 'A healthier weight than today', body: `${show(targetKg)} is a BMI of ${b1}. Every kilo down counts.` };
  }
  return { tone: 'info', title: 'Above the healthy range for your height', body: `${show(targetKg)} is a BMI of ${b1}.` };
}

function CardIcon({ tone }: { tone: Card['tone'] }) {
  const bg = tone === 'ok' ? C.okSoft : tone === 'warn' ? C.warnSoft : C.infoSoft;
  const fg = tone === 'ok' ? C.ok : tone === 'warn' ? C.warn : C.info;
  return (
    <View style={[s.icon, { backgroundColor: bg }]}>
      <Svg width={15} height={15} viewBox="0 0 24 24" fill="none">
        {tone === 'ok' ? (
          <Path d="M20 6 9 17l-5-5" stroke={fg} strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" />
        ) : (
          <>
            <Path d="M12 7v6" stroke={fg} strokeWidth={2.6} strokeLinecap="round" />
            <Path d="M12 17h.01" stroke={fg} strokeWidth={2.6} strokeLinecap="round" />
          </>
        )}
      </Svg>
    </View>
  );
}

export default function TargetScreen() {
  const { intro, next, progress } = useOnbScreen('S7_target');
  const { width } = useWindowDimensions();
  const rulerW = width - PAD.side * 2;
  const imperial = intro.units === 'imperial';
  const current = intro.weight_kg;
  const floor = healthyFloorKg(intro.height_cm);

  // Ruler range: well below the healthy floor (so a too-low goal can be shown
  // and caught) up to +40 kg; whole units at index 0 so majors line up.
  const minKg = Math.max(30, Math.floor(Math.min(current - 40, floor - 8)));
  const maxKg = Math.min(250, Math.ceil(current + 40));
  const scale = useMemo(() => {
    if (!imperial) {
      return {
        count: Math.round((maxKg - minKg) / 0.2) + 1,
        perMajor: 5,
        toKg: (i: number) => Math.round((minKg + i * 0.2) * 10) / 10,
        toIndex: (kg: number) => Math.round((kg - minKg) / 0.2),
      };
    }
    const minLb = Math.floor((minKg * LB_PER_KG) / 14) * 14;
    const maxLb = Math.ceil(maxKg * LB_PER_KG);
    return {
      count: maxLb - minLb + 1,
      perMajor: 14,
      toKg: (i: number) => Math.round(((minLb + i) / LB_PER_KG) * 10) / 10,
      toIndex: (kg: number) => Math.round(kg * LB_PER_KG) - minLb,
    };
  }, [imperial, minKg, maxKg]);

  const defaultKg = useMemo(() => {
    if (intro.target_weight_kg) return intro.target_weight_kg;
    switch (intro.goal_type) {
      case 'lose':
        return Math.max(floor, Math.round(current * 0.92));
      case 'gain':
        return Math.round(current + 4);
      default:
        return Math.round(current);
    }
  }, [current, floor, intro.goal_type, intro.target_weight_kg]);

  const [index, setIndex] = useState(() => Math.max(0, Math.min(scale.count - 1, scale.toIndex(defaultKg))));
  const target = scale.toKg(index);
  const show = useCallback((kg: number) => (imperial ? fmtStLb(kg) : `${fmtKg(kg)} kg`), [imperial]);
  const majorLabel = useCallback(
    (i: number) => (imperial ? `${Math.round((scale.toKg(i) * LB_PER_KG) / 14)} st` : String(Math.round(scale.toKg(i)))),
    [imperial, scale],
  );

  const diff = target - current;
  const diffText =
    Math.abs(diff) < 0.1
      ? 'Same as today'
      : `${imperial ? fmtStLb(Math.abs(diff)) : `${fmtKg(Math.abs(diff))} kg`} ${diff < 0 ? 'less' : 'more'} than today`;
  const card = bmiCard(target, current, intro.height_cm, show);

  return (
    <OnbLayout
      progress={progress}
      title="What’s your target weight?"
      footer={
        <OnbButton
          label="Continue"
          onPress={() =>
            next(
              { target_weight_kg: target },
              { bmi_band: card.tone, direction: Math.abs(diff) <= 1 ? 'same' : diff < 0 ? 'down' : 'up' },
              { onb_direction: Math.abs(diff) <= 1 ? 'same' : diff < 0 ? 'down' : 'up', onb_target_bmi_band: card.tone },
            )
          }
        />
      }
    >
      <View style={{ flex: 1 }} />
      <View style={s.valueRow}>
        {imperial ? (
          <>
            <Text style={s.value}>{Math.floor(Math.round(target * LB_PER_KG) / 14)}</Text>
            <Text style={s.unit}>st</Text>
            <Text style={[s.value, { marginLeft: 6 }]}>{Math.round(target * LB_PER_KG) % 14}</Text>
            <Text style={s.unit}>lb</Text>
          </>
        ) : (
          <>
            <Text style={s.value}>{fmtKg(target)}</Text>
            <Text style={s.unit}>kg</Text>
          </>
        )}
      </View>
      <Text style={s.diff}>{diffText}</Text>
      <View style={s.ruler}>
        <Ruler
          count={scale.count}
          index={index}
          currentIndex={scale.toIndex(current)}
          perMajor={scale.perMajor}
          majorLabel={majorLabel}
          onChange={setIndex}
          width={rulerW}
        />
      </View>
      <View style={{ flex: 1 }} />
      <View style={s.card}>
        <CardIcon tone={card.tone} />
        <View style={s.cardText}>
          <Text style={s.cardTitle}>{card.title}</Text>
          <Text style={s.cardBody}>{card.body}</Text>
        </View>
      </View>
    </OnbLayout>
  );
}

const s = StyleSheet.create({
  valueRow: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'center', gap: 6 },
  value: { fontFamily: F.serif, fontSize: 72, lineHeight: 76, color: C.ink, fontVariant: ['tabular-nums'] },
  unit: { fontFamily: F.sans, fontSize: 22, color: C.muted },
  diff: { marginTop: 4, textAlign: 'center', fontFamily: F.sans, fontSize: 16, lineHeight: 22, color: C.muted },
  ruler: { marginTop: 26 },
  card: {
    marginBottom: 16,
    flexDirection: 'row',
    gap: 12,
    alignItems: 'flex-start',
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.hair,
    borderRadius: 16,
    padding: 16,
  },
  icon: { width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  cardText: { flex: 1, gap: 2 },
  cardTitle: { fontFamily: F.sansSemibold, fontSize: 15, lineHeight: 20, color: C.ink },
  cardBody: { fontFamily: F.sans, fontSize: 14, lineHeight: 20, color: C.muted },
});
