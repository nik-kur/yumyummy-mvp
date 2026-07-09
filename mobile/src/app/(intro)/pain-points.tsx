/**
 * S8 Pain points — 5 fixed options per prototype v3, multi-select.
 * Stores stable ids (not labels) in the draft — they feed Adapty custom
 * attributes and future paywall personalization.
 */
import { useEffect, useState } from 'react';
import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Check } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { IntroHeader } from '@/components/IntroHeader';
import { useIntro } from '@/state/introContext';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

const OPTIONS: { id: string; emoji: string; label: string }[] = [
  { id: 'too_long', emoji: '⏱️', label: 'Logging took too long' },
  { id: 'gave_up', emoji: '📉', label: 'I gave up after a few days' },
  { id: 'accuracy', emoji: '🤔', label: 'Never sure the calories were right' },
  { id: 'eating_out', emoji: '🍽️', label: 'Eating out broke everything' },
  { id: 'first_time', emoji: '🌱', label: 'First time tracking' },
];

export default function PainPointsScreen() {
  const router = useRouter();
  const intro = useIntro();
  const [selected, setSelected] = useState<string[]>(intro.pain_points);

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'S8_pain_points' });
  }, []);

  const toggle = (id: string) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <IntroHeader step={7} />

      <View style={s.header}>
        <AppText variant="overline" color={colors.terracottaText}>Be honest</AppText>
        <AppText variant="h1" style={s.title}>What made tracking hard before?</AppText>
        <AppText variant="body" color={colors.inkMuted}>Pick all that apply.</AppText>
      </View>

      <View style={s.list}>
        {OPTIONS.map((o) => {
          const isOn = selected.includes(o.id);
          return (
            <Pressable
              key={o.id}
              onPress={() => toggle(o.id)}
              style={[s.card, isOn && s.cardSelected]}
            >
              <AppText style={s.emoji}>{o.emoji}</AppText>
              <AppText variant="title" style={s.cardLabel}>{o.label}</AppText>
              <View style={[s.checkbox, isOn && s.checkboxOn]}>
                {isOn && <Check size={14} color={colors.white} strokeWidth={2.5} />}
              </View>
            </Pressable>
          );
        })}
      </View>

      <Button
        label="Continue"
        variant="brand"
        onPress={() => {
          intro.set({ pain_points: selected });
          track('onboarding_screen_completed', {
            screen: 'S8_pain_points',
            pain_points: selected,
          });
          router.push('/(intro)/problem');
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.md, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  list: { flex: 1, justifyContent: 'center', gap: space.md },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1.5,
    borderColor: colors.hairline,
    paddingVertical: space.md,
    paddingHorizontal: space.base,
  },
  cardSelected: { borderColor: colors.terracotta, backgroundColor: colors.terracottaSoft },
  emoji: { fontSize: 20, lineHeight: 26 },
  cardLabel: { flex: 1 },
  checkbox: {
    width: 22, height: 22,
    borderRadius: radius.sm,
    borderWidth: 1.5,
    borderColor: colors.hairlineStrong,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxOn: { backgroundColor: colors.terracotta, borderColor: colors.terracotta },
  cta: { marginTop: 'auto' },
});
