/**
 * V3 screen 7 (Pace) — kg per week on a slider; the goal date and daily
 * calories update live. Losing: 0.1–1.0 kg/week (recommended 0.4); gaining:
 * 0.1–0.4 (recommended 0.25). Calories never go under `minKcal`: a faster
 * pace can be picked, the plan then stays on the minimum (the date is the
 * earliest the minimum allows) and the card says so (wording agreed 18 Oct).
 */
import { useCallback, useMemo, useState } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';

import { OnbButton } from '@/components/onb/OnbButton';
import { OnbLayout } from '@/components/onb/OnbLayout';
import { PaceSlider } from '@/components/onb/PaceSlider';
import { IMG } from '@/onb/assets';
import {
  dailyPlan,
  direction,
  fmtKg,
  fmtStLb,
  formatLongDate,
  LB_PER_KG,
  maxLossPace,
  minKcal,
  PACE,
  paceZone,
  planMode,
  type PaceZone,
} from '@/onb/plan';
import { C, F } from '@/onb/theme';
import { useOnbScreen } from '@/onb/useOnbScreen';

const ZONE_LINE: Record<PaceZone, string> = {
  gentle: 'Easy to stick with.',
  recommended: 'Steady enough to stick with.',
  fast: 'Fast, so it takes more discipline.',
};

export default function PaceScreen() {
  const { intro, next, progress } = useOnbScreen('S7_pace');
  const target = intro.target_weight_kg ?? intro.weight_kg;
  const dir = direction(intro.weight_kg, target) === 'up' ? 'up' : 'down';
  const p = PACE[dir];
  const steps = useMemo(() => {
    const out: number[] = [];
    for (let v = p.min; v <= p.max + 1e-6; v += p.step) out.push(Math.round(v * 100) / 100);
    return out;
  }, [p]);
  const body = {
    gender: intro.gender ?? 'other',
    age: intro.age,
    height_cm: intro.height_cm,
    weight_kg: intro.weight_kg,
    activity_level: intro.activity_level ?? 'light',
  } as const;
  // Fastest losing step that keeps calories on or above the floor (-1: not even the slowest).
  const maxPace = dir === 'up' ? Infinity : maxLossPace(body);
  const safeIndex = steps.reduce((last, v, i) => (v <= maxPace + 1e-6 ? i : last), -1);
  const initial = intro.pace_kg_week ?? p.recommended;
  const [index, setIndex] = useState(() => {
    const i = steps.findIndex((v) => Math.abs(v - initial) < 1e-6);
    return i >= 0 ? i : steps.findIndex((v) => Math.abs(v - p.recommended) < 1e-6);
  });
  const pace = steps[index];
  const zone = paceZone(dir, pace);
  const zoneOf = useCallback((i: number) => paceZone(dir, steps[i]), [dir, steps]);

  const mode = planMode(intro.goal_type ?? 'lose', direction(intro.weight_kg, target));
  const plan = dailyPlan(body, mode, target, pace);
  const imperial = intro.units === 'imperial';
  const fmtPace = (kg: number) => (imperial ? String(Math.round(kg * LB_PER_KG * 10) / 10) : String(kg));
  const floor = minKcal(body).toLocaleString('en-GB');
  const kcal = plan.calories.toLocaleString('en-GB');
  const cardLine = !plan.capped
    ? `${kcal} kcal a day. ${ZONE_LINE[zone]}`
    : safeIndex >= 0
      ? `Faster than ${fmtPace(steps[safeIndex])} ${imperial ? 'lb' : 'kg'} a week would mean under ${floor} kcal a day, which is hard to maintain. Consider a slower pace.`
      : `Even the gentlest pace would mean under ${floor} kcal a day, which is hard to maintain. Moving more gets you there sooner.`;
  const paceText = fmtPace(pace);
  const targetText = imperial ? fmtStLb(target) : `${fmtKg(target)} kg`;

  const zones: { z: PaceZone; label: string; img: number }[] = [
    { z: 'gentle', label: 'Gentle', img: IMG.pace_tortoise },
    { z: 'recommended', label: 'Recommended', img: IMG.pace_rabbit },
    { z: 'fast', label: 'Fast', img: IMG.pace_cheetah },
  ];

  return (
    <OnbLayout
      progress={progress}
      title="How fast do you want to reach your goal?"
      footer={
        <OnbButton
          label="Continue"
          onPress={() =>
            next(
              {
                pace_kg_week: pace,
                target_weeks: plan.weeks,
                target_date: plan.target_date,
                target_calories: plan.calories,
                target_protein_g: plan.protein,
                target_fat_g: plan.fat,
                target_carbs_g: plan.carbs,
              },
              { pace, zone },
              { onb_pace_zone: zone },
            )
          }
        />
      }
    >
      <View style={{ flex: 1 }} />
      <Text style={s.caption}>{dir === 'down' ? 'Weight loss per week' : 'Weight gain per week'}</Text>
      <View style={s.valueRow}>
        <Text style={s.value}>{paceText}</Text>
        <Text style={s.unit}>{imperial ? 'lb' : 'kg'}</Text>
      </View>
      <View style={s.zones}>
        {zones.map(({ z, label, img }) => {
          const on = z === zone;
          return (
            <View key={z} style={[s.zone, { width: on ? 120 : 96, opacity: on ? 1 : 0.45 }]}>
              <Image source={img} style={{ width: on ? 56 : 44, height: on ? 56 : 44 }} />
              <Text style={[s.zoneLabel, on && s.zoneOn]}>{label}</Text>
            </View>
          );
        })}
      </View>
      <View style={s.slider}>
        <PaceSlider steps={steps} index={index} onChange={setIndex} zoneOf={zoneOf} />
      </View>
      <View style={{ flex: 1 }} />
      <View style={s.card}>
        <Text style={s.cardCaption}>You’ll reach {targetText} by</Text>
        <Text style={s.cardDate}>{plan.target_date ? formatLongDate(plan.target_date) : '—'}</Text>
        <Text style={s.cardLine}>{cardLine}</Text>
      </View>
    </OnbLayout>
  );
}

const s = StyleSheet.create({
  caption: { textAlign: 'center', fontFamily: F.sans, fontSize: 15, lineHeight: 20, color: C.muted },
  valueRow: { marginTop: 4, flexDirection: 'row', alignItems: 'baseline', justifyContent: 'center', gap: 6 },
  value: { fontFamily: F.serif, fontSize: 52, lineHeight: 58, color: C.ink, fontVariant: ['tabular-nums'] },
  unit: { fontFamily: F.sans, fontSize: 20, color: C.muted },
  zones: { marginTop: 30, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' },
  zone: { alignItems: 'center', gap: 6 },
  zoneLabel: { fontFamily: F.sans, fontSize: 13, lineHeight: 18, color: C.muted },
  zoneOn: { fontFamily: F.sansSemibold, color: C.ink },
  slider: { marginTop: 18 },
  card: {
    marginBottom: 16,
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.hair,
    borderRadius: 16,
    paddingVertical: 18,
    paddingHorizontal: 20,
  },
  cardCaption: { textAlign: 'center', fontFamily: F.sans, fontSize: 15, lineHeight: 20, color: C.muted },
  cardDate: { marginTop: 4, textAlign: 'center', fontFamily: F.serif, fontSize: 30, lineHeight: 36, color: C.ink },
  cardLine: { marginTop: 6, textAlign: 'center', fontFamily: F.sans, fontSize: 14, lineHeight: 20, color: C.muted },
});
