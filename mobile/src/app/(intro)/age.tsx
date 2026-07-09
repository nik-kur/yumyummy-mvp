/**
 * S5 Age — numeric stepper/wheel.
 */
import { useState } from 'react';
import { View, StyleSheet, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { Minus, Plus } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useIntro } from '@/state/introContext';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

export default function AgeScreen() {
  const router = useRouter();
  const intro = useIntro();
  const [age, setAge] = useState(intro.age);

  const adjust = (delta: number) => {
    setAge((a) => Math.max(14, Math.min(99, a + delta)));
  };

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.header}>
        <AppText variant="overline" color={colors.inkMuted}>Step 4 of 8</AppText>
        <AppText variant="h1" style={s.title}>How old are you?</AppText>
        <AppText variant="body" color={colors.inkMuted}>
          Your age affects your base metabolic rate.
        </AppText>
      </View>

      <View style={s.picker}>
        <Pressable onPress={() => adjust(-1)} style={s.btn} hitSlop={12}>
          <Minus size={24} color={colors.ink} strokeWidth={1.5} />
        </Pressable>
        <AppText variant="hero">{age}</AppText>
        <Pressable onPress={() => adjust(1)} style={s.btn} hitSlop={12}>
          <Plus size={24} color={colors.ink} strokeWidth={1.5} />
        </Pressable>
      </View>

      <Button
        label="Continue"
        onPress={() => {
          intro.set({ age });
          track('onboarding_screen_completed', { screen: 'S5_age' });
          router.push('/(intro)/body');
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.xl, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  picker: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.xxl,
  },
  btn: {
    width: 48, height: 48,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.hairline,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cta: { marginTop: 'auto' },
});
