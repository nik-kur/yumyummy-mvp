/**
 * N1 Target & Pace — two sliders (target weight, timeline) with live
 * kcal/pace recalculation and difficulty tiers (prototype v3).
 * Lose/gain goals only; maintain/track skips straight to the loader.
 */
import { useEffect, useMemo, useState } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import Slider from '@react-native-community/slider';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { SourcesLink } from '@/components/SourcesLink';
import { IntroHeader } from '@/components/IntroHeader';
import { useIntro } from '@/state/introContext';
import { computePlan, macrosForCalories } from '@/utils/calories';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';
import { track } from '@/analytics/posthog';

const KCAL_PER_KG = 7700;

function targetDate(weeks: number): string {
  const d = new Date();
  d.setDate(d.getDate() + weeks * 7);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default function TargetPaceScreen() {
  const router = useRouter();
  const intro = useIntro();

  const goal = intro.goal_type === 'gain' ? 'gain' : 'lose';
  const lose = goal === 'lose';
  const weight = intro.weight_kg;
  const gender = intro.gender ?? 'male';

  const { tdee } = useMemo(
    () =>
      computePlan({
        gender,
        age: intro.age,
        height_cm: intro.height_cm,
        weight_kg: weight,
        activity_level: intro.activity_level ?? 'light',
        goal_type: goal,
      }),
    [gender, intro.age, intro.height_cm, weight, intro.activity_level, goal],
  );

  // Target-weight slider bounds: BMI 18.5 floor for lose, +15 kg cap for gain.
  const tmin = lose
    ? Math.max(45, Math.round(18.5 * (intro.height_cm / 100) ** 2))
    : weight + 1;
  const tmax = lose ? weight - 1 : weight + 15;

  const defaultTarget = lose
    ? Math.max(tmin, weight - 8)
    : Math.min(tmax, weight + 6);

  const defaultWeeks = useMemo(() => {
    const dw = Math.abs(weight - defaultTarget);
    const tgtDaily = (lose ? 0.15 : 0.08) * tdee;
    const w = Math.ceil((dw * KCAL_PER_KG) / tgtDaily / 7);
    return Math.min(lose ? 40 : 52, Math.max(lose ? 8 : 12, w));
  }, [weight, defaultTarget, lose, tdee]);

  const [target, setTarget] = useState(
    intro.target_weight_kg && intro.target_weight_kg >= tmin && intro.target_weight_kg <= tmax
      ? intro.target_weight_kg
      : defaultTarget,
  );
  const [weeks, setWeeks] = useState(intro.target_weeks ?? defaultWeeks);

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'N1_target_pace' });
  }, []);

  // Live derived values
  const floor = gender === 'female' ? 1200 : 1500;
  const dw = Math.abs(weight - target);
  const dailyDelta = (dw * KCAL_PER_KG) / (weeks * 7);
  const cal = Math.round((lose ? tdee - dailyDelta : tdee + dailyDelta) / 10) * 10;
  const pace = dw / weeks;
  const pct = Math.round((dailyDelta / tdee) * 100);

  type Tier = { level: 'ok' | 'mid' | 'bad'; label: string; sub?: string };
  const tier: Tier = useMemo(() => {
    if (lose) {
      if (cal < floor || pct > 25) {
        const maxDelta = Math.min(0.25 * tdee, tdee - floor);
        const suggest = Math.ceil((dw * KCAL_PER_KG) / maxDelta / 7);
        return {
          level: 'bad',
          label: 'Too aggressive',
          sub: `This pace drops you below a safe minimum. Try ${suggest} weeks or more — you'd still finish by ${targetDate(suggest)}.`,
        };
      }
      if (pct > 18) return { level: 'mid', label: 'Ambitious — doable, needs consistency' };
      if (pct > 10) return { level: 'ok', label: 'Steady — sustainable for most people' };
      return { level: 'ok', label: 'Gentle — barely feels like a diet' };
    }
    if (pct > 15) {
      const suggest = Math.ceil((dw * KCAL_PER_KG) / (0.15 * tdee) / 7);
      return {
        level: 'bad',
        label: 'Aggressive — expect fat gain too',
        sub: `Slow down to keep gains lean. Try ${suggest} weeks or more.`,
      };
    }
    if (pct > 8) return { level: 'mid', label: 'Steady build' };
    return { level: 'ok', label: 'Lean gain — slow and clean' };
  }, [lose, cal, floor, pct, tdee, dw]);

  const tierColor =
    tier.level === 'bad' ? colors.error : tier.level === 'mid' ? colors.warning : colors.success;

  const lockIn = () => {
    // Never ship a plan below the safe calorie floor: clamp and stretch the timeline.
    let finalCal = cal;
    let finalWeeks = weeks;
    if (lose && cal < floor) {
      finalCal = floor;
      const delta = tdee - floor;
      if (delta > 0) finalWeeks = Math.ceil((dw * KCAL_PER_KG) / delta / 7);
    }
    const macros = macrosForCalories(finalCal, weight, goal);
    intro.set({
      target_weight_kg: target,
      deficit_pct: pct,
      target_weeks: finalWeeks,
      target_calories: finalCal,
      target_protein_g: macros.protein,
      target_fat_g: macros.fat,
      target_carbs_g: macros.carbs,
    });
    track('onboarding_screen_completed', {
      screen: 'N1_target_pace',
      target_weight_kg: target,
      target_weeks: finalWeeks,
      deficit_pct: pct,
      tier: tier.level,
    });
    router.push('/(intro)/loader');
  };

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <IntroHeader step={10} />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scroll}>
        <AppText variant="overline" color={colors.terracottaText}>Your target</AppText>
        <AppText variant="h1" style={s.title}>Set your goal — see what it takes</AppText>
        <AppText variant="body" color={colors.inkMuted} style={s.lead}>
          You burn about ~{Math.round(tdee).toLocaleString('en-US')} kcal a day at your
          activity level. Drag the sliders — watch what changes.
        </AppText>

        {/* Slider 1 — target weight */}
        <View style={s.sliderBlock}>
          <View style={s.sliderHead}>
            <AppText variant="bodyStrong">Target weight</AppText>
            <AppText variant="bodyStrong" color={colors.terracottaText}>{target} kg</AppText>
          </View>
          <Slider
            minimumValue={tmin}
            maximumValue={tmax}
            step={1}
            value={target}
            onValueChange={(v) => setTarget(Math.round(v))}
            minimumTrackTintColor={colors.terracotta}
            maximumTrackTintColor={colors.hairlineStrong}
            thumbTintColor={colors.terracotta}
          />
          <View style={s.sliderScale}>
            <AppText variant="caption" color={colors.inkFaint}>{tmin} kg</AppText>
            <AppText variant="caption" color={colors.inkFaint}>{tmax} kg</AppText>
          </View>
        </View>

        {/* Slider 2 — timeline */}
        <View style={s.sliderBlock}>
          <View style={s.sliderHead}>
            <AppText variant="bodyStrong">By when</AppText>
            <AppText variant="bodyStrong" color={colors.terracottaText}>
              {weeks} wk · by {targetDate(weeks)}
            </AppText>
          </View>
          <Slider
            minimumValue={4}
            maximumValue={52}
            step={1}
            value={weeks}
            onValueChange={(v) => setWeeks(Math.round(v))}
            minimumTrackTintColor={colors.terracotta}
            maximumTrackTintColor={colors.hairlineStrong}
            thumbTintColor={colors.terracotta}
          />
          <View style={s.sliderScale}>
            <AppText variant="caption" color={colors.inkFaint}>4 wk</AppText>
            <AppText variant="caption" color={colors.inkFaint}>52 wk</AppText>
          </View>
        </View>

        {/* Live plan card */}
        <View style={s.liveCard}>
          <View style={s.kcalRow}>
            <AppText style={s.kcalBig}>{Math.max(cal, 0).toLocaleString('en-US')}</AppText>
            <AppText variant="small" color={colors.inkMuted}>kcal/day</AppText>
            <View style={s.paceChip}>
              <AppText variant="small" color={colors.ink}>
                {lose ? '−' : '+'}{pace.toFixed(1)} kg/wk
              </AppText>
            </View>
          </View>
          <View style={s.deficitTrack}>
            <View
              style={[
                s.deficitFill,
                { width: `${(Math.min(pct, 30) / 30) * 100}%`, backgroundColor: tierColor },
              ]}
            />
          </View>
          <AppText variant="caption" color={colors.inkMuted}>
            {pct}% {lose ? 'below' : 'above'} your burn
          </AppText>
          <AppText variant="bodyStrong" color={tierColor} style={s.tierLabel}>
            {tier.label}
          </AppText>
          {tier.sub ? (
            <AppText variant="small" color={colors.inkMuted}>{tier.sub}</AppText>
          ) : null}
        </View>

        <SourcesLink
          label="Burn & pacing based on published research — see sources"
          center
          style={s.sources}
        />
      </ScrollView>

      <Button label="Lock it in" variant="brand" onPress={lockIn} style={s.cta} />
    </Screen>
  );
}

const s = StyleSheet.create({
  scroll: { paddingBottom: space.base },
  title: { marginTop: space.sm },
  lead: { marginTop: space.sm, marginBottom: space.lg },
  sliderBlock: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    paddingHorizontal: space.base,
    paddingVertical: space.md,
    marginBottom: space.md,
  },
  sliderHead: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: space.xs,
  },
  sliderScale: { flexDirection: 'row', justifyContent: 'space-between' },
  liveCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors.hairlineStrong,
    padding: space.base,
    gap: space.sm,
  },
  kcalRow: { flexDirection: 'row', alignItems: 'baseline', gap: space.sm },
  kcalBig: {
    fontFamily: fonts.serifBold,
    fontSize: 36,
    lineHeight: 42,
    color: colors.ink,
  },
  paceChip: {
    marginLeft: 'auto',
    paddingHorizontal: space.md,
    paddingVertical: 3,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.hairline,
  },
  deficitTrack: {
    height: 8,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    overflow: 'hidden',
  },
  deficitFill: { height: '100%', borderRadius: radius.pill },
  tierLabel: { marginTop: space.xs },
  sources: { marginTop: space.md },
  cta: { marginTop: space.sm },
});
