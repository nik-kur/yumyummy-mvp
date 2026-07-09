/**
 * S2 Goal — "What's your goal right now?" (prototype v3).
 * Single-select with auto-advance; writes to the intro draft.
 */
import { useEffect, useRef } from 'react';
import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { TrendingDown, Utensils, Dumbbell, Eye, CircleCheck, type LucideIcon } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { IntroHeader } from '@/components/IntroHeader';
import { useIntro } from '@/state/introContext';
import type { GoalType } from '@/utils/calories';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

const GOALS: { key: GoalType; icon: LucideIcon; label: string }[] = [
  { key: 'lose', icon: TrendingDown, label: 'Lose weight' },
  { key: 'maintain', icon: Utensils, label: 'Maintain & eat healthier' },
  { key: 'gain', icon: Dumbbell, label: 'Gain muscle' },
  { key: 'just_track', icon: Eye, label: 'Just track my food' },
];

const AUTO_ADVANCE_MS = 280;

export default function GoalScreen() {
  const router = useRouter();
  const { goal_type, set } = useIntro();
  const navigating = useRef(false);

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'S2_goal' });
  }, []);

  const pick = (key: GoalType) => {
    if (navigating.current) return;
    navigating.current = true;
    set({ goal_type: key });
    track('onboarding_screen_completed', { screen: 'S2_goal', goal: key });
    setTimeout(() => {
      navigating.current = false;
      router.push('/(intro)/why');
    }, AUTO_ADVANCE_MS);
  };

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <IntroHeader step={1} />

      <View style={s.header}>
        <AppText variant="overline" color={colors.terracottaText}>About you</AppText>
        <AppText variant="h1" style={s.title}>What’s your goal right now?</AppText>
      </View>

      <View style={s.list}>
        {GOALS.map((g) => {
          const selected = goal_type === g.key;
          const Icon = g.icon;
          return (
            <Pressable
              key={g.key}
              onPress={() => pick(g.key)}
              style={[s.card, selected && s.cardSelected]}
            >
              <View style={[s.iconWrap, selected && s.iconWrapSelected]}>
                <Icon size={22} color={selected ? colors.white : colors.terracotta} strokeWidth={1.5} />
              </View>
              <View style={s.cardText}>
                <AppText variant="title">{g.label}</AppText>
              </View>
              {selected ? (
                <CircleCheck size={22} color={colors.terracotta} strokeWidth={1.5} />
              ) : (
                <View style={s.radio} />
              )}
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
  list: { flex: 1, justifyContent: 'center', gap: space.base },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.base,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors.hairline,
    padding: space.base,
  },
  cardSelected: { borderColor: colors.terracotta, backgroundColor: colors.terracottaSoft },
  iconWrap: {
    width: 44, height: 44, borderRadius: radius.md,
    backgroundColor: colors.terracottaSoft,
    alignItems: 'center', justifyContent: 'center',
  },
  iconWrapSelected: { backgroundColor: colors.terracotta },
  cardText: { flex: 1, gap: 2 },
  radio: { width: 22, height: 22, borderRadius: radius.pill, borderWidth: 1.5, borderColor: colors.hairlineStrong },
});
