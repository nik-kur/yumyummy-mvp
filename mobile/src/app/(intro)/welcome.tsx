/**
 * S1 Welcome demo — first screen of the intro flow.
 *
 * Autoplay logging demo (photo → voice → text) from onboarding_prototype_v3.html.
 * "Already have an account? Sign in" link for returning users.
 */
import { useEffect } from 'react';
import { View, StyleSheet, Pressable, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { WelcomeDemo } from '@/components/WelcomeDemo';
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
      <ScrollView
        contentContainerStyle={s.scroll}
        showsVerticalScrollIndicator={false}
        bounces={false}
      >
        <View style={s.header}>
          <AppText style={s.emoji}>🥑</AppText>
          <AppText variant="overline" color={colors.inkMuted} center>
            YUMYUMMY
          </AppText>
          <AppText variant="h1" center style={s.headline}>
            The food tracker you'll actually keep up with
          </AppText>
          <AppText variant="body" color={colors.inkMuted} center>
            Any meal, any way — verified calories in ~10 seconds.
          </AppText>
        </View>

        <WelcomeDemo />

        <View style={s.chips}>
          {TRUST_CHIPS.map((label) => (
            <View key={label} style={s.chip}>
              <AppText variant="caption" color={colors.inkMuted}>{label}</AppText>
            </View>
          ))}
        </View>
      </ScrollView>

      <View style={s.bottom}>
        <Button
          label="Get Started"
          variant="brand"
          onPress={() => {
            track('onboarding_screen_completed', { screen: 'S1_welcome' });
            router.push('/(intro)/goal');
          }}
        />
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
  scroll: { flexGrow: 1, paddingTop: space.sm },
  header: { alignItems: 'center', paddingHorizontal: space.lg, gap: space.xs },
  emoji: { fontSize: 26 },
  headline: { marginTop: space.md },
  bottom: { gap: space.base, paddingBottom: space.lg, paddingHorizontal: space.lg },
  link: { marginTop: space.sm },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: space.sm,
    marginTop: space.sm,
    paddingHorizontal: space.lg,
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
