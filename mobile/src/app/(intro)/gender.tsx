/**
 * S4 Gender — binary picker for the Mifflin–St Jeor formula (prototype v3).
 * Single-select with auto-advance.
 */
import { useEffect, useRef } from 'react';
import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { IntroHeader } from '@/components/IntroHeader';
import { useIntro } from '@/state/introContext';
import type { Gender } from '@/utils/calories';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

const OPTIONS: { key: Gender; label: string; emoji: string }[] = [
  { key: 'male', label: 'Male', emoji: '👨' },
  { key: 'female', label: 'Female', emoji: '👩' },
];

const AUTO_ADVANCE_MS = 280;

export default function GenderScreen() {
  const router = useRouter();
  const { gender, set } = useIntro();
  const navigating = useRef(false);

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'S4_gender' });
  }, []);

  const pick = (key: Gender) => {
    if (navigating.current) return;
    navigating.current = true;
    set({ gender: key });
    track('onboarding_screen_completed', { screen: 'S4_gender' });
    setTimeout(() => {
      navigating.current = false;
      router.push('/(intro)/age');
    }, AUTO_ADVANCE_MS);
  };

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <IntroHeader step={3} />

      <View style={s.header}>
        <AppText variant="overline" color={colors.terracottaText}>Your metabolism</AppText>
        <AppText variant="h1" style={s.title}>How should we calculate your metabolism?</AppText>
        <AppText variant="body" color={colors.inkMuted}>
          We use this for your calorie formula only.
        </AppText>
      </View>

      <View style={s.options}>
        {OPTIONS.map((o) => {
          const selected = gender === o.key;
          return (
            <Pressable
              key={o.key}
              onPress={() => pick(o.key)}
              style={[s.option, selected && s.optionSelected]}
            >
              <AppText style={s.emoji}>{o.emoji}</AppText>
              <AppText variant="title">{o.label}</AppText>
            </Pressable>
          );
        })}
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.md, marginBottom: space.lg, gap: space.xs },
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
  optionSelected: { borderColor: colors.terracotta, backgroundColor: colors.terracottaSoft },
  emoji: { fontSize: 40, lineHeight: 48 },
});
