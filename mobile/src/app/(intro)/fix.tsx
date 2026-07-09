/**
 * S10 Fix — "So we built both into one app" (prototype v3).
 * Two numbered fix-cards (frictionless + precise, with the Oikos proof meal),
 * a synthesis block, then CTA "Build my plan" branching by goal:
 * lose/gain → target-pace, maintain/track → loader.
 */
import { useEffect } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { IntroHeader } from '@/components/IntroHeader';
import { SourceBadge } from '@/components/Badges';
import { useIntro } from '@/state/introContext';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';
import { track } from '@/analytics/posthog';

export default function FixScreen() {
  const router = useRouter();
  const { goal_type } = useIntro();

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'S10_fix' });
  }, []);

  const onContinue = () => {
    track('onboarding_screen_completed', { screen: 'S10_fix' });
    if (goal_type === 'lose' || goal_type === 'gain') {
      router.push('/(intro)/target-pace');
    } else {
      router.push('/(intro)/loader');
    }
  };

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <IntroHeader step={9} />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scroll}>
        <AppText variant="overline" color={colors.terracottaText}>The answer</AppText>
        <AppText variant="h1" style={s.title}>So we built both into one app</AppText>

        {/* Fix 1 — frictionless */}
        <View style={s.fixCard}>
          <View style={s.fixHead}>
            <View style={s.fixNum}><AppText style={s.fixNumText}>1</AppText></View>
            <AppText variant="title" style={s.fixTitle}>Frictionless — so you keep it up</AppText>
          </View>
          <AppText variant="small" color={colors.inkMuted}>
            Say it, snap it, or type it — logging a meal takes seconds, not minutes.
            No barcode hunting, no database digging.
          </AppText>
          <View style={s.waysRow}>
            {['🎙️ Voice', '📸 Photo', '⌨️ Text'].map((w) => (
              <View key={w} style={s.wayChip}>
                <AppText variant="small">{w}</AppText>
              </View>
            ))}
          </View>
        </View>

        {/* Fix 2 — precise, with the Oikos proof meal */}
        <View style={s.fixCard}>
          <View style={s.fixHead}>
            <View style={s.fixNum}><AppText style={s.fixNumText}>2</AppText></View>
            <AppText variant="title" style={s.fixTitle}>Precise — so it actually counts</AppText>
          </View>
          <AppText variant="small" color={colors.inkMuted}>
            Numbers come from verified sources — USDA, EU labels, manufacturers —
            not AI guesses. Here’s a real one:
          </AppText>
          <View style={s.mealCard}>
            <View style={s.mealHead}>
              <AppText variant="bodyStrong" style={s.mealName}>
                Oikos Greek yogurt, 150 g
              </AppText>
              <SourceBadge source="Danone" />
            </View>
            <View style={s.mealKcalRow}>
              <AppText style={s.mealKcal}>90</AppText>
              <AppText variant="small" color={colors.inkMuted}>kcal</AppText>
            </View>
            <View style={s.macroRow}>
              <View style={[s.macroPill, { backgroundColor: colors.oliveSoft }]}>
                <AppText variant="caption" color={colors.protein}>P 15 g</AppText>
              </View>
              <View style={[s.macroPill, { backgroundColor: colors.warningSoft }]}>
                <AppText variant="caption" color={colors.fat}>F 0 g</AppText>
              </View>
              <View style={[s.macroPill, { backgroundColor: colors.infoBlueSoft }]}>
                <AppText variant="caption" color={colors.carbs}>C 6 g</AppText>
              </View>
            </View>
          </View>
        </View>

        {/* Synthesis */}
        <View style={s.synth}>
          <AppText variant="body" color={colors.white} center>
            Frictionless, so you stick with it.{'\n'}
            <AppText style={s.synthSerif}>Precise, so it works. That’s YumYummy.</AppText>
          </AppText>
        </View>
      </ScrollView>

      <Button label="Build my plan" variant="brand" onPress={onContinue} style={s.cta} />
    </Screen>
  );
}

const s = StyleSheet.create({
  scroll: { paddingBottom: space.base },
  title: { marginTop: space.sm, marginBottom: space.base },
  fixCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.base,
    gap: space.md,
    marginBottom: space.md,
  },
  fixHead: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  fixNum: {
    width: 28, height: 28,
    borderRadius: radius.sm,
    backgroundColor: colors.terracotta,
    alignItems: 'center', justifyContent: 'center',
  },
  fixNumText: { color: colors.white, fontFamily: fonts.sansSemibold, fontSize: 14, lineHeight: 18 },
  fixTitle: { flex: 1 },
  waysRow: { flexDirection: 'row', gap: space.sm },
  wayChip: {
    paddingHorizontal: space.md,
    paddingVertical: space.xs,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.hairline,
  },
  mealCard: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.md,
    gap: space.sm,
  },
  mealHead: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.sm,
  },
  mealName: { flex: 1 },
  mealKcalRow: { flexDirection: 'row', alignItems: 'baseline', gap: space.xs },
  mealKcal: {
    fontFamily: fonts.serifBold,
    fontSize: 34,
    lineHeight: 40,
    color: colors.ink,
  },
  macroRow: { flexDirection: 'row', gap: space.sm },
  macroPill: {
    paddingHorizontal: space.md,
    paddingVertical: 3,
    borderRadius: radius.pill,
  },
  synth: {
    backgroundColor: colors.terracotta,
    borderRadius: radius.lg,
    padding: space.lg,
    marginTop: space.xs,
  },
  synthSerif: { fontFamily: fonts.serifBold, color: colors.white },
  cta: { marginTop: space.sm },
});
