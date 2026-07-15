import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, View, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { TrendingDown, TrendingUp, Target, type LucideIcon } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { MacroBar } from '@/components/MacroBar';
import { useOnboarding } from '@/state/onboarding';
import { useAuth } from '@/state/auth';
import * as api from '@/api/endpoints';
import { reportJourneyEvent } from '@/state/journey';
import { computePlan } from '@/utils/calories';
import { formatInt } from '@/utils/format';
import { colors, radius, space } from '@/theme/tokens';

export default function PlanScreen() {
  const router = useRouter();
  const auth = useAuth();
  const draft = useOnboarding();
  const [phase, setPhase] = useState<'calc' | 'reveal'>('calc');
  const [saving, setSaving] = useState(false);

  const plan = useMemo(
    () =>
      computePlan({
        gender: draft.gender ?? 'male',
        age: draft.age,
        height_cm: draft.height_cm,
        weight_kg: draft.weight_kg,
        activity_level: draft.activity_level ?? 'moderate',
        goal_type: draft.goal_type ?? 'maintain',
      }),
    [draft],
  );

  useEffect(() => {
    const t = setTimeout(() => setPhase('reveal'), 1600);
    return () => clearTimeout(t);
  }, []);

  const projection = useMemo(() => {
    const diff = Math.abs(plan.tdee - plan.calories);
    const kgPerWeek = (diff * 7) / 7700;
    if (draft.goal_type === 'lose') return `About ${kgPerWeek.toFixed(1)} kg/week toward your goal.`;
    if (draft.goal_type === 'gain') return `Lean gain of about ${kgPerWeek.toFixed(1)} kg/week.`;
    if (draft.goal_type === 'just_track') return 'No limits — we’ll just show the numbers.';
    return 'A steady maintenance plan to eat with awareness.';
  }, [plan, draft.goal_type]);

  const ProjectionIcon: LucideIcon =
    draft.goal_type === 'lose' ? TrendingDown : draft.goal_type === 'gain' ? TrendingUp : Target;

  const onAccept = async () => {
    setSaving(true);
    try {
      const updated = await api.updateMe({
        goal_type: draft.goal_type,
        gender: draft.gender,
        age: draft.age,
        height_cm: draft.height_cm,
        weight_kg: draft.weight_kg,
        activity_level: draft.activity_level,
        target_calories: plan.calories,
        target_protein_g: plan.protein,
        target_fat_g: plan.fat,
        target_carbs_g: plan.carbs,
        onboarding_completed: true,
      });
      auth.applyProfile(updated);
      // Saving the questionnaire records fresh weight — that IS the Day 7
      // weigh-in, however the user got here (quest card or Profile).
      void reportJourneyEvent({ type: 'weight_updated' }).catch(() => {});
    } catch {
      // Offline: continue anyway so onboarding isn't a dead end.
    } finally {
      setSaving(false);
      router.push('/(onboarding)/first-log');
    }
  };

  if (phase === 'calc') {
    return (
      <Screen>
        <View style={styles.calc}>
          <ActivityIndicator size="large" color={colors.terracotta} />
          <AppText variant="h2" center style={styles.calcTitle}>
            Crunching the numbers…
          </AppText>
          <AppText variant="body" color={colors.inkMuted} center>
            Building a plan from your goal, body and activity.
          </AppText>
        </View>
      </Screen>
    );
  }

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.header}>
        <AppText variant="overline" color={colors.inkMuted}>
          Your daily plan
        </AppText>
        <AppText variant="h1" style={styles.title}>
          Here’s your target
        </AppText>
      </View>

      <View style={styles.body}>
        <Card style={styles.heroCard}>
          <AppText variant="hero" color={colors.terracotta}>
            {formatInt(plan.calories)}
          </AppText>
          <AppText variant="overline" color={colors.inkMuted}>
            kcal / day
          </AppText>
          <View style={styles.macros}>
            <MacroBar label="Protein" macro="protein" value={plan.protein} target={plan.protein} />
            <MacroBar label="Fat" macro="fat" value={plan.fat} target={plan.fat} />
            <MacroBar label="Carbs" macro="carbs" value={plan.carbs} target={plan.carbs} />
          </View>
        </Card>

        <Card flat style={styles.projection}>
          <View style={styles.projHead}>
            <View style={styles.projIcon}>
              <ProjectionIcon size={16} color={colors.infoBlue} strokeWidth={1.5} />
            </View>
            <AppText variant="eyebrow" color={colors.infoBlue}>
              Projection
            </AppText>
          </View>
          <AppText variant="bodyStrong">{projection}</AppText>
          <View style={styles.projDivider} />
          <AppText variant="caption" color={colors.inkFaint}>
            Mifflin–St Jeor · TDEE ≈ {formatInt(plan.tdee)} kcal. Adjusts as you log and your weight
            changes.
          </AppText>
        </Card>
      </View>

      <View style={styles.footer}>
        <Button label="Looks good" variant="brand" loading={saving} onPress={onAccept} />
        <Button
          label="Adjust details"
          variant="ghost"
          onPress={() => router.back()}
          haptic={false}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  calc: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.md },
  calcTitle: { marginTop: space.base },
  header: { marginTop: space.xl, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  body: { flex: 1, justifyContent: 'center', gap: space.base },
  heroCard: { alignItems: 'center', gap: space.xs, paddingVertical: space.xl },
  macros: { alignSelf: 'stretch', gap: space.md, marginTop: space.lg },
  projection: { gap: space.sm, backgroundColor: colors.infoBlueSoft, borderColor: colors.infoBlueSoft },
  projHead: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  projIcon: {
    width: 28,
    height: 28,
    borderRadius: radius.sm,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  projDivider: { height: StyleSheet.hairlineWidth, backgroundColor: 'rgba(31,92,153,0.18)', marginVertical: space.xs },
  footer: { paddingTop: space.lg, gap: space.sm },
});
