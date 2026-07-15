/**
 * S1 Welcome demo — first screen of the intro flow.
 */
import { useEffect } from 'react';
import { View, StyleSheet, Pressable } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { WelcomeDemo } from '@/components/WelcomeDemo';
import { MascotBadge } from '@/components/MascotBadge';
import { track } from '@/analytics/posthog';
import { colors, radius, space } from '@/theme/tokens';

const TRUST_CHIPS = ['★ 4.8', '12,000+ trackers', '✓ Verified data'];

export default function WelcomeScreen() {
  const router = useRouter();

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'S1_welcome' });
  }, []);

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.body}>
        <View style={s.header}>
          <MascotBadge variant="welcome" size={64} style={s.mascot} />
          <AppText variant="h1" center style={s.headline}>
            The food tracker you&rsquo;ll actually keep up with
          </AppText>
          <AppText variant="title" color={colors.inkMuted} center style={s.sub}>
            Any meal, any way — verified calories in ~10 seconds.
          </AppText>
        </View>

        <View style={s.demoWrap}>
          <WelcomeDemo />
        </View>
      </View>

      <View style={s.bottom}>
        <Button
          label="Get Started"
          variant="brand"
          onPress={() => {
            track('onboarding_screen_completed', { screen: 'S1_welcome' });
            router.push('/(intro)/goal');
          }}
        />
        <View style={s.chips}>
          {TRUST_CHIPS.map((label) => (
            <View key={label} style={s.chip}>
              <AppText variant="caption" color={colors.inkMuted}>{label}</AppText>
            </View>
          ))}
        </View>
        <Pressable onPress={() => router.replace('/(auth)/sign-in')}>
          <AppText variant="small" color={colors.terracottaText} center style={s.link}>
            Already have an account? Sign in
          </AppText>
        </Pressable>
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  body: {
    flex: 1,
    justifyContent: 'center',
    paddingHorizontal: space.lg,
    gap: space.lg,
  },
  header: { alignItems: 'center', gap: space.sm },
  mascot: { marginBottom: space.xs },
  headline: { marginTop: space.xs },
  sub: { lineHeight: 26, maxWidth: 320 },
  demoWrap: { alignSelf: 'stretch' },
  bottom: { gap: space.md, paddingBottom: space.lg, paddingHorizontal: space.lg },
  link: { marginTop: space.xs },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: space.sm,
  },
  chip: {
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
    borderRadius: radius.pill,
    paddingHorizontal: space.md,
    paddingVertical: 5,
  },
});
