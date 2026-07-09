/**
 * N1 Target & Pace — only shown for lose/gain goals.
 *
 * Safety constraints (per spec v2):
 *   - 7700 kcal per kg body weight
 *   - Floor: M 1500 / F 1200 kcal/day
 *   - Deficit options: 10% (gentle), 15% (moderate), 20% (aggressive)
 *   - Dynamic default timeline based on delta
 */
import { useMemo, useState } from 'react';
import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Minus, Plus } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useIntro } from '@/state/introContext';
import { computePlan } from '@/utils/calories';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

const KCAL_PER_KG = 7700;

interface PaceOption {
  pct: number;
  label: string;
  difficulty: string;
}

const PACES: PaceOption[] = [
  { pct: 10, label: 'Gentle', difficulty: 'Easy to sustain' },
  { pct: 15, label: 'Moderate', difficulty: 'Balanced pace' },
  { pct: 20, label: 'Aggressive', difficulty: 'Requires discipline' },
];

function floorCalories(kcal: number, gender: string | null): number {
  const floor = gender === 'female' ? 1200 : 1500;
  return Math.max(kcal, floor);
}

export default function TargetPaceScreen() {
  const router = useRouter();
  const intro = useIntro();

  const plan = useMemo(() => {
    if (!intro.gender || !intro.activity_level || !intro.goal_type) return null;
    return computePlan({
      gender: intro.gender,
      age: intro.age,
      height_cm: intro.height_cm,
      weight_kg: intro.weight_kg,
      activity_level: intro.activity_level,
      goal_type: 'maintain',
    });
  }, [intro.gender, intro.age, intro.height_cm, intro.weight_kg, intro.activity_level, intro.goal_type]);

  const defaultTarget = intro.goal_type === 'lose'
    ? Math.round(intro.weight_kg * 0.9)
    : Math.round(intro.weight_kg * 1.1);
  const [target, setTarget] = useState(intro.target_weight_kg ?? defaultTarget);
  const [selectedPace, setSelectedPace] = useState(1);
  const pace = PACES[selectedPace];

  const delta = Math.abs(target - intro.weight_kg);
  const tdee = plan?.tdee ?? 2000;
  const dailyDeficit = Math.round(tdee * (pace.pct / 100));
  const adjustedKcal = floorCalories(
    intro.goal_type === 'lose' ? tdee - dailyDeficit : tdee + dailyDeficit,
    intro.gender,
  );
  const weeks = delta > 0 ? Math.ceil((delta * KCAL_PER_KG) / (dailyDeficit * 7)) : 4;

  const targetDate = useMemo(() => {
    const d = new Date();
    d.setDate(d.getDate() + weeks * 7);
    return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  }, [weeks]);

  const adjustTarget = (d: number) => {
    setTarget((t) => Math.max(30, Math.min(250, t + d)));
  };

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.header}>
        <AppText variant="overline" color={colors.inkMuted}>YOUR PLAN</AppText>
        <AppText variant="h1" style={s.title}>
          Set your target
        </AppText>
      </View>

      <View style={s.targetPicker}>
        <AppText variant="bodyStrong">Target weight</AppText>
        <View style={s.stepperRow}>
          <Pressable onPress={() => adjustTarget(-1)} style={s.stepBtn} hitSlop={12}>
            <Minus size={20} color={colors.ink} strokeWidth={1.5} />
          </Pressable>
          <View style={s.valBox}>
            <AppText variant="hero">{target}</AppText>
            <AppText variant="caption" color={colors.inkMuted}>kg</AppText>
          </View>
          <Pressable onPress={() => adjustTarget(1)} style={s.stepBtn} hitSlop={12}>
            <Plus size={20} color={colors.ink} strokeWidth={1.5} />
          </Pressable>
        </View>
      </View>

      <AppText variant="bodyStrong" style={s.paceLabel}>Choose your pace</AppText>
      <View style={s.paces}>
        {PACES.map((p, i) => (
          <Pressable
            key={p.pct}
            onPress={() => setSelectedPace(i)}
            style={[s.paceCard, selectedPace === i && s.paceCardActive]}
          >
            <AppText variant="title">{p.label}</AppText>
            <AppText variant="caption" color={colors.inkMuted}>{p.difficulty}</AppText>
            <AppText variant="caption" color={colors.terracottaText}>{p.pct}% deficit</AppText>
          </Pressable>
        ))}
      </View>

      <View style={s.summary}>
        <View style={s.summaryRow}>
          <AppText variant="body" color={colors.inkMuted}>Daily target</AppText>
          <AppText variant="title">{adjustedKcal} kcal</AppText>
        </View>
        <View style={s.summaryRow}>
          <AppText variant="body" color={colors.inkMuted}>Timeline</AppText>
          <AppText variant="title">~{weeks} weeks</AppText>
        </View>
        <View style={s.summaryRow}>
          <AppText variant="body" color={colors.inkMuted}>Target date</AppText>
          <AppText variant="title">{targetDate}</AppText>
        </View>
      </View>

      <Button
        label="Lock it in"
        variant="brand"
        onPress={() => {
          const fullPlan = computePlan({
            gender: intro.gender!,
            age: intro.age,
            height_cm: intro.height_cm,
            weight_kg: intro.weight_kg,
            activity_level: intro.activity_level!,
            goal_type: intro.goal_type!,
          });

          intro.set({
            target_weight_kg: target,
            deficit_pct: pace.pct,
            target_weeks: weeks,
            target_calories: adjustedKcal,
            target_protein_g: fullPlan.protein,
            target_fat_g: fullPlan.fat,
            target_carbs_g: fullPlan.carbs,
          });

          track('n1_completed', { deficit_pct: pace.pct, weeks, target_kcal: adjustedKcal });
          router.push('/(intro)/loader');
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.xl, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  targetPicker: { alignItems: 'center', gap: space.md, marginBottom: space.lg },
  stepperRow: { flexDirection: 'row', alignItems: 'center', gap: space.xl },
  stepBtn: {
    width: 44, height: 44, borderRadius: radius.pill,
    backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.hairline,
    alignItems: 'center', justifyContent: 'center',
  },
  valBox: { alignItems: 'center', minWidth: 80 },
  paceLabel: { marginBottom: space.md },
  paces: { gap: space.md, marginBottom: space.lg },
  paceCard: {
    backgroundColor: colors.surface, borderRadius: radius.lg,
    borderWidth: 1.5, borderColor: colors.hairline, padding: space.base, gap: 2,
  },
  paceCardActive: { borderColor: colors.terracotta, backgroundColor: colors.surfaceAlt },
  summary: {
    backgroundColor: colors.surface, borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth, borderColor: colors.hairline,
    padding: space.base, gap: space.md, marginBottom: space.lg,
  },
  summaryRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cta: { marginTop: 'auto' },
});
