/**
 * N2 Loader — animated "building your plan" screen.
 * Runs a sequence of status messages then auto-navigates to the plan reveal.
 */
import { useEffect, useState } from 'react';
import { View, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { useIntro } from '@/state/introContext';
import { computePlan } from '@/utils/calories';
import { colors, space } from '@/theme/tokens';

const STEPS = [
  'Analyzing your profile…',
  'Checking nutrition databases…',
  'Calculating your targets…',
  'Building your plan…',
];

export default function LoaderScreen() {
  const router = useRouter();
  const intro = useIntro();
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!intro.target_calories && intro.gender && intro.activity_level && intro.goal_type) {
      const plan = computePlan({
        gender: intro.gender,
        age: intro.age,
        height_cm: intro.height_cm,
        weight_kg: intro.weight_kg,
        activity_level: intro.activity_level,
        goal_type: intro.goal_type,
      });
      intro.set({
        target_calories: plan.calories,
        target_protein_g: plan.protein,
        target_fat_g: plan.fat,
        target_carbs_g: plan.carbs,
      });
    }
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setStep((s) => {
        if (s >= STEPS.length - 1) {
          clearInterval(interval);
          setTimeout(() => router.replace('/(intro)/plan-reveal'), 500);
          return s;
        }
        return s + 1;
      });
    }, 800);
    return () => clearInterval(interval);
  }, [router]);

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.center}>
        <ActivityIndicator size="large" color={colors.terracotta} />
        <AppText variant="title" center style={s.text}>
          {STEPS[step]}
        </AppText>
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: space.lg },
  text: { paddingHorizontal: space.xl },
});
