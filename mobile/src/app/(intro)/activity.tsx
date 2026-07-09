/**
 * S7 Activity — 4 levels per prototype v3, single-select with auto-advance.
 * Routes to pain-points (S8).
 */
import { useEffect, useRef } from 'react';
import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { CircleCheck } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { IntroHeader } from '@/components/IntroHeader';
import { useIntro } from '@/state/introContext';
import type { ActivityLevel } from '@/utils/calories';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

const OPTIONS: { key: ActivityLevel; emoji: string; label: string; sub: string }[] = [
  { key: 'sedentary', emoji: '🪑', label: 'Mostly sitting', sub: 'Desk job, little movement' },
  { key: 'light', emoji: '🚶', label: 'Lightly active', sub: 'Walks, 1–2 workouts a week' },
  { key: 'moderate', emoji: '🏃', label: 'Active', sub: '3–5 workouts a week' },
  { key: 'active', emoji: '🏋️', label: 'Very active', sub: 'Training 6–7 days a week' },
];

const AUTO_ADVANCE_MS = 280;

export default function ActivityScreen() {
  const router = useRouter();
  const { activity_level, set } = useIntro();
  const navigating = useRef(false);

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'S7_activity' });
  }, []);

  const pick = (key: ActivityLevel) => {
    if (navigating.current) return;
    navigating.current = true;
    set({ activity_level: key });
    track('onboarding_screen_completed', { screen: 'S7_activity' });
    setTimeout(() => {
      navigating.current = false;
      router.push('/(intro)/pain-points');
    }, AUTO_ADVANCE_MS);
  };

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <IntroHeader step={6} />

      <View style={s.header}>
        <AppText variant="overline" color={colors.terracottaText}>Your metabolism</AppText>
        <AppText variant="h1" style={s.title}>How active is your typical week?</AppText>
      </View>

      <View style={s.list}>
        {OPTIONS.map((o) => {
          const selected = activity_level === o.key;
          return (
            <Pressable
              key={o.key}
              onPress={() => pick(o.key)}
              style={[s.card, selected && s.cardSelected]}
            >
              <AppText style={s.emoji}>{o.emoji}</AppText>
              <View style={s.cardText}>
                <AppText variant="title">{o.label}</AppText>
                <AppText variant="small" color={colors.inkMuted}>{o.sub}</AppText>
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
  emoji: { fontSize: 26, lineHeight: 32 },
  cardText: { flex: 1, gap: 2 },
  radio: { width: 22, height: 22, borderRadius: radius.pill, borderWidth: 1.5, borderColor: colors.hairlineStrong },
});
