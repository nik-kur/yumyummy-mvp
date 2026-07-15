/**
 * S10 Fix — "So we built both into one app" (prototype v3).
 * Precise first, frictionless second; mascot + brand line instead of synth banner.
 */
import { useEffect } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { IntroHeader } from '@/components/IntroHeader';
import { MascotBadge } from '@/components/MascotBadge';
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
        <View>
          <AppText variant="overline" color={colors.terracottaText}>The answer</AppText>
          <AppText variant="h1" style={s.title}>So we built both into one app</AppText>
        </View>

        <View style={s.cards}>
        {/* Fix 1 — precise (with Oikos proof meal) */}
        <View style={s.fixCard}>
          <View style={s.fixHead}>
            <View style={s.fixNum}><AppText style={s.fixNumText}>1</AppText></View>
            <AppText variant="title" style={s.fixTitle}>Precise — so it actually counts</AppText>
          </View>
          <AppText variant="small" color={colors.inkMuted}>
            Every meal checked against official databases and verified brand data — USDA,
            restaurant menus, packaged foods. Not AI guesses.
          </AppText>
          <View style={s.mealCard}>
            <View style={s.mealHead}>
              <AppText variant="bodyStrong" style={s.mealName}>
                Oikos Greek yogurt, 150g
              </AppText>
              <SourceBadge source="Danone" />
            </View>
            <View style={s.mealKcalRow}>
              <AppText style={s.mealKcal}>90</AppText>
              <AppText variant="small" color={colors.inkMuted}>kcal</AppText>
            </View>
            <View style={s.macroRow}>
              <View style={[s.macroPill, { backgroundColor: colors.oliveSoft }]}>
                <AppText variant="caption" color={colors.protein}>P 15g</AppText>
              </View>
              <View style={[s.macroPill, { backgroundColor: colors.warningSoft }]}>
                <AppText variant="caption" color={colors.fat}>F 0g</AppText>
              </View>
              <View style={[s.macroPill, { backgroundColor: colors.infoBlueSoft }]}>
                <AppText variant="caption" color={colors.carbs}>C 6g</AppText>
              </View>
            </View>
          </View>
        </View>

        {/* Fix 2 — frictionless */}
        <View style={s.fixCard}>
          <View style={s.fixHead}>
            <View style={s.fixNum}><AppText style={s.fixNumText}>2</AppText></View>
            <AppText variant="title" style={s.fixTitle}>Frictionless — so you keep it up</AppText>
          </View>
          <AppText variant="small" color={colors.inkMuted}>
            Log any meal in ~10 seconds — photo, text, or voice. No barcodes, no scrolling.
          </AppText>
          <View style={s.waysRow}>
            {['📷 Photo', '🎤 Voice', '⌨️ Text'].map((w) => (
              <View key={w} style={s.wayChip}>
                <AppText variant="small">{w}</AppText>
              </View>
            ))}
          </View>
        </View>

        </View>

        <MascotBadge
          variant="thumbsUp"
          size={104}
          label="That's YumYummy"
          style={s.mascotRow}
        />
      </ScrollView>

      <Button label="Build my plan" variant="brand" onPress={onContinue} style={s.cta} />
    </Screen>
  );
}

const s = StyleSheet.create({
  // flexGrow + space-between: header / cards / mascot spread over the full
  // height instead of stacking at the top (falls back to scrolling if tall).
  scroll: {
    flexGrow: 1,
    justifyContent: 'space-between',
    paddingTop: space.sm,
    paddingBottom: space.base,
  },
  title: { marginTop: space.sm },
  cards: { gap: space.base, paddingVertical: space.md },
  fixCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.base,
    gap: space.md,
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
  mascotRow: {
    paddingVertical: space.sm,
  },
  cta: { marginTop: space.md },
});
