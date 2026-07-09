/**
 * S3 Pain points — multi-select chips, goal-dependent variants.
 */
import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useIntro } from '@/state/introContext';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

const PAIN_MAP: Record<string, string[]> = {
  lose: [
    'I keep starting and stopping',
    'I don\'t know what to eat',
    'Tracking feels like a chore',
    'I eat out a lot',
  ],
  gain: [
    'I forget to eat enough',
    'Not hitting protein targets',
    'Hard to track homemade meals',
    'Don\'t know my ideal surplus',
  ],
  maintain: [
    'I want awareness without obsessing',
    'I snack too much',
    'Portions feel inconsistent',
    'Not sure my diet is balanced',
  ],
  just_track: [
    'I want quick, accurate logging',
    'Curious about my macros',
    'Building better habits',
    'Want data on my eating patterns',
  ],
};

export default function PainPointsScreen() {
  const router = useRouter();
  const { goal_type, pain_points, set } = useIntro();
  const options = PAIN_MAP[goal_type ?? 'lose'] ?? PAIN_MAP.lose;

  const toggle = (item: string) => {
    const next = pain_points.includes(item)
      ? pain_points.filter((p) => p !== item)
      : [...pain_points, item];
    set({ pain_points: next });
  };

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.header}>
        <AppText variant="overline" color={colors.inkMuted}>Step 2 of 8</AppText>
        <AppText variant="h1" style={s.title}>What's been the hardest part?</AppText>
        <AppText variant="body" color={colors.inkMuted}>
          Select all that apply — this helps us personalize your experience.
        </AppText>
      </View>

      <View style={s.chips}>
        {options.map((o) => {
          const selected = pain_points.includes(o);
          return (
            <Pressable
              key={o}
              onPress={() => toggle(o)}
              style={[s.chip, selected && s.chipSelected]}
            >
              <AppText
                variant="body"
                color={selected ? colors.terracottaText : colors.ink}
              >
                {o}
              </AppText>
            </Pressable>
          );
        })}
      </View>

      <Button
        label="Continue"
        disabled={pain_points.length === 0}
        onPress={() => {
          track('onboarding_screen_completed', { screen: 'S3_pain_points', count: pain_points.length });
          router.push('/(intro)/gender');
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.xl, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  chips: { flex: 1, gap: space.md },
  chip: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors.hairline,
    paddingHorizontal: space.base,
    paddingVertical: space.md,
  },
  chipSelected: { borderColor: colors.terracotta, backgroundColor: colors.terracottaSoft },
  cta: { marginTop: 'auto' },
});
