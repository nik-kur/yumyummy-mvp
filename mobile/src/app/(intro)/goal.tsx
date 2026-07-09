/**
 * S2 Goal — what brings you here?
 * Same 4 options as the existing onboarding, but writes to the intro draft.
 */
import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { TrendingDown, Utensils, Dumbbell, Activity, CircleCheck, type LucideIcon } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useIntro } from '@/state/introContext';
import { GOAL_LABELS, type GoalType } from '@/utils/calories';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

const GOALS: { key: GoalType; icon: LucideIcon; desc: string }[] = [
  { key: 'lose', icon: TrendingDown, desc: 'Gentle deficit, steady results' },
  { key: 'maintain', icon: Utensils, desc: 'Awareness without obsessing' },
  { key: 'gain', icon: Dumbbell, desc: 'Fuel training, build muscle' },
  { key: 'just_track', icon: Activity, desc: 'See the numbers, set no limits' },
];

export default function GoalScreen() {
  const router = useRouter();
  const { goal_type, set } = useIntro();

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.header}>
        <AppText variant="overline" color={colors.inkMuted}>Step 1 of 8</AppText>
        <AppText variant="h1" style={s.title}>What brings you to YumYummy?</AppText>
        <AppText variant="body" color={colors.inkMuted}>
          We'll tailor your targets to this. You can change it anytime.
        </AppText>
      </View>

      <View style={s.list}>
        {GOALS.map((g) => {
          const selected = goal_type === g.key;
          const Icon = g.icon;
          return (
            <Pressable
              key={g.key}
              onPress={() => set({ goal_type: g.key })}
              style={[s.card, selected && s.cardSelected]}
            >
              <View style={[s.iconWrap, selected && s.iconWrapSelected]}>
                <Icon size={22} color={selected ? colors.white : colors.terracotta} strokeWidth={1.5} />
              </View>
              <View style={s.cardText}>
                <AppText variant="title">{GOAL_LABELS[g.key]}</AppText>
                <AppText variant="caption" color={colors.inkMuted}>{g.desc}</AppText>
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

      <Button
        label="Continue"
        disabled={!goal_type}
        onPress={() => {
          track('onboarding_screen_completed', { screen: 'S2_goal' });
          router.push('/(intro)/pain-points');
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.xl, marginBottom: space.lg, gap: space.xs },
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
  cardSelected: { borderColor: colors.terracotta, backgroundColor: colors.surfaceAlt },
  iconWrap: {
    width: 44, height: 44, borderRadius: radius.md,
    backgroundColor: colors.terracottaSoft,
    alignItems: 'center', justifyContent: 'center',
  },
  iconWrapSelected: { backgroundColor: colors.terracotta },
  cardText: { flex: 1, gap: 2 },
  radio: { width: 22, height: 22, borderRadius: radius.pill, borderWidth: 1.5, borderColor: colors.hairlineStrong },
  cta: { marginTop: 'auto' },
});
