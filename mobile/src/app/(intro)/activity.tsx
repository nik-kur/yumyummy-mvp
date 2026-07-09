/**
 * S7 Activity level — single select list.
 */
import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { CircleCheck } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useIntro } from '@/state/introContext';
import { ACTIVITY_LABELS, type ActivityLevel } from '@/utils/calories';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

const LEVELS: { key: ActivityLevel; desc: string }[] = [
  { key: 'sedentary', desc: 'Desk job, little exercise' },
  { key: 'light', desc: '1–3 light workouts/week' },
  { key: 'moderate', desc: '3–5 moderate sessions/week' },
  { key: 'active', desc: '6–7 hard sessions/week' },
  { key: 'very_active', desc: 'Athlete / physical job' },
];

export default function ActivityScreen() {
  const router = useRouter();
  const { activity_level, set } = useIntro();

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.header}>
        <AppText variant="overline" color={colors.inkMuted}>Step 6 of 8</AppText>
        <AppText variant="h1" style={s.title}>How active are you?</AppText>
        <AppText variant="body" color={colors.inkMuted}>
          Be honest — this shapes your daily calorie target.
        </AppText>
      </View>

      <View style={s.list}>
        {LEVELS.map((l) => {
          const selected = activity_level === l.key;
          return (
            <Pressable
              key={l.key}
              onPress={() => set({ activity_level: l.key })}
              style={[s.card, selected && s.cardSelected]}
            >
              <View style={s.cardText}>
                <AppText variant="bodyStrong">{ACTIVITY_LABELS[l.key]}</AppText>
                <AppText variant="caption" color={colors.inkMuted}>{l.desc}</AppText>
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
        disabled={!activity_level}
        onPress={() => {
          track('onboarding_screen_completed', { screen: 'S7_activity' });
          router.push('/(intro)/cico-arc');
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.xl, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  list: { flex: 1, justifyContent: 'center', gap: space.md },
  card: {
    flexDirection: 'row', alignItems: 'center', gap: space.base,
    backgroundColor: colors.surface, borderRadius: radius.lg,
    borderWidth: 1.5, borderColor: colors.hairline, padding: space.base,
  },
  cardSelected: { borderColor: colors.terracotta, backgroundColor: colors.surfaceAlt },
  cardText: { flex: 1, gap: 2 },
  radio: { width: 22, height: 22, borderRadius: radius.pill, borderWidth: 1.5, borderColor: colors.hairlineStrong },
  cta: { marginTop: 'auto' },
});
