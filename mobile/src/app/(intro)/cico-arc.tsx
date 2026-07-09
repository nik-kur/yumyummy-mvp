/**
 * S9–S10 CICO arc — two narrative screens collapsed into one with a page indicator.
 *
 * S9: "So what's the answer?" — animated calorie balance concept.
 * S10: "Prove it to me" — how YumYummy makes it effortless.
 */
import { useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

const PAGES = [
  {
    overline: 'THE SCIENCE',
    headline: 'So what\'s the answer?',
    body: 'Weight change is energy balance. Eat less than you burn → you lose. Eat more → you gain. Simple in theory — but knowing your real numbers is the hard part.',
    cta: 'So what\'s the answer?',
  },
  {
    overline: 'HOW IT WORKS',
    headline: 'Prove it to me',
    body: 'YumYummy checks every meal against real data — verified menus, nutrition labels, and databases. No guessing, no generic estimates. Just text, snap, or speak — we handle the rest.',
    cta: 'Prove it to me',
  },
];

export default function CicoArcScreen() {
  const router = useRouter();
  const [page, setPage] = useState(0);
  const current = PAGES[page];

  const next = () => {
    if (page < PAGES.length - 1) {
      setPage(page + 1);
    } else {
      track('onboarding_screen_completed', { screen: 'S9_S10_cico_arc' });
      router.push('/(intro)/try-it');
    }
  };

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.header}>
        <AppText variant="overline" color={colors.inkMuted}>Step 7 of 8</AppText>
      </View>

      <View style={s.content}>
        <AppText variant="overline" color={colors.terracottaText}>
          {current.overline}
        </AppText>
        <AppText variant="display" style={s.headline}>
          {current.headline}
        </AppText>
        <AppText variant="body" color={colors.inkMuted} style={s.body}>
          {current.body}
        </AppText>
      </View>

      <View style={s.dots}>
        {PAGES.map((_, i) => (
          <View key={i} style={[s.dot, i === page && s.dotActive]} />
        ))}
      </View>

      <Button
        label={current.cta}
        variant="brand"
        onPress={next}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.xl },
  content: { flex: 1, justifyContent: 'center', gap: space.md },
  headline: { marginTop: space.sm },
  body: { marginTop: space.sm },
  dots: { flexDirection: 'row', justifyContent: 'center', gap: space.sm, marginBottom: space.base },
  dot: {
    width: 8, height: 8, borderRadius: radius.pill,
    backgroundColor: colors.hairlineStrong,
  },
  dotActive: { backgroundColor: colors.terracotta, width: 24 },
  cta: { marginTop: 'auto' },
});
