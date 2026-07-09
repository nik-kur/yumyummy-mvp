/**
 * N2 Loader — percentage ring building the plan (prototype v3).
 * Four staged status lines, then auto-navigates to the plan reveal.
 * For maintain/track goals (which skip N1) the plan is computed here.
 */
import { useEffect, useRef, useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import Svg, { Circle } from 'react-native-svg';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { useIntro } from '@/state/introContext';
import { computePlan } from '@/utils/calories';
import { colors, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';
import { track } from '@/analytics/posthog';

const LINES = [
  'Calculating your metabolism…',
  'Finding your calorie margin…',
  'Verifying food data for your region…',
  'Almost there…',
];

const SIZE = 130;
const STROKE = 10;
const R = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * R;

export default function LoaderScreen() {
  const router = useRouter();
  const intro = useIntro();
  const [pct, setPct] = useState(0);
  const navigated = useRef(false);

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'N2_loader' });
    // Maintain/track path skips N1 — compute the plan from the quiz inputs here.
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setPct((p) => {
        const next = Math.min(100, p + 2);
        if (next >= 100 && !navigated.current) {
          navigated.current = true;
          clearInterval(interval);
          setTimeout(() => router.replace('/(intro)/plan-reveal'), 400);
        }
        return next;
      });
    }, 60);
    return () => clearInterval(interval);
  }, [router]);

  const line = LINES[Math.min(LINES.length - 1, Math.floor(pct / 26))];

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.center}>
        <View style={s.ringWrap}>
          <Svg width={SIZE} height={SIZE}>
            <Circle
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={R}
              stroke={colors.terracottaSoft}
              strokeWidth={STROKE}
              fill="none"
            />
            <Circle
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={R}
              stroke={colors.terracotta}
              strokeWidth={STROKE}
              fill="none"
              strokeLinecap="round"
              strokeDasharray={`${CIRCUMFERENCE}`}
              strokeDashoffset={CIRCUMFERENCE * (1 - pct / 100)}
              transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
            />
          </Svg>
          <View style={s.ringCenter}>
            <AppText style={s.pctText}>{pct}%</AppText>
          </View>
        </View>
        <AppText variant="title" center style={s.line}>{line}</AppText>
        <AppText variant="caption" color={colors.inkFaint} center>
          300,000+ meals logged with YumYummy
        </AppText>
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', gap: space.lg },
  ringWrap: { width: SIZE, height: SIZE, alignItems: 'center', justifyContent: 'center' },
  ringCenter: { position: 'absolute', alignItems: 'center', justifyContent: 'center' },
  pctText: {
    fontFamily: fonts.serifBold,
    fontSize: 26,
    lineHeight: 32,
    color: colors.ink,
  },
  line: { paddingHorizontal: space.xl },
});
