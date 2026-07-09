/**
 * S4 Gender — binary picker for the Mifflin–St Jeor formula.
 */
import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useIntro } from '@/state/introContext';
import type { Gender } from '@/utils/calories';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

const OPTIONS: { key: Gender; label: string; emoji: string }[] = [
  { key: 'male', label: 'Male', emoji: '♂' },
  { key: 'female', label: 'Female', emoji: '♀' },
];

export default function GenderScreen() {
  const router = useRouter();
  const { gender, set } = useIntro();

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.header}>
        <AppText variant="overline" color={colors.inkMuted}>Step 3 of 8</AppText>
        <AppText variant="h1" style={s.title}>How should we calculate?</AppText>
        <AppText variant="body" color={colors.inkMuted}>
          This affects your calorie target. We'll never show it publicly.
        </AppText>
      </View>

      <View style={s.options}>
        {OPTIONS.map((o) => {
          const selected = gender === o.key;
          return (
            <Pressable
              key={o.key}
              onPress={() => set({ gender: o.key })}
              style={[s.option, selected && s.optionSelected]}
            >
              <AppText variant="display">{o.emoji}</AppText>
              <AppText variant="title">{o.label}</AppText>
            </Pressable>
          );
        })}
      </View>

      <Button
        label="Continue"
        disabled={!gender}
        onPress={() => {
          track('onboarding_screen_completed', { screen: 'S4_gender' });
          router.push('/(intro)/age');
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.xl, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  options: {
    flex: 1,
    flexDirection: 'row',
    gap: space.base,
    justifyContent: 'center',
    alignItems: 'center',
  },
  option: {
    flex: 1,
    aspectRatio: 1,
    maxHeight: 160,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors.hairline,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.sm,
  },
  optionSelected: { borderColor: colors.terracotta, backgroundColor: colors.surfaceAlt },
  cta: { marginTop: 'auto' },
});
