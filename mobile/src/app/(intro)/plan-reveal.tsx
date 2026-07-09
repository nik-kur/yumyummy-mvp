/**
 * N3 Plan Reveal — shows the computed plan with a testimonial carousel.
 *
 * For lose/gain: shows the trajectory to target weight.
 * For maintain/just_track: shows the daily target summary.
 *
 * CTA: "Start my plan" → paywall.
 *
 * Before navigating to paywall, pushes custom attributes to Adapty
 * for audience segmentation (anonymous profile, pre-purchase).
 */
import { useMemo } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { adapty } from 'react-native-adapty';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { useIntro } from '@/state/introContext';
import { isAdaptyConfigured } from '@/billing/adapty';
import { colors, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';
import { addBreadcrumb } from '@/analytics/sentry';

const TESTIMONIALS = [
  { text: 'Lost 4 kg in 6 weeks just by knowing my numbers.', author: 'Maria' },
  { text: 'Finally found an app that checks its own data.', author: 'Alex' },
  { text: 'The source links gave me confidence in my tracking.', author: 'Sarah' },
];

export default function PlanRevealScreen() {
  const router = useRouter();
  const intro = useIntro();

  const hasTarget = intro.goal_type === 'lose' || intro.goal_type === 'gain';
  const targetDate = useMemo(() => {
    if (!intro.target_weeks) return null;
    const d = new Date();
    d.setDate(d.getDate() + intro.target_weeks * 7);
    return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  }, [intro.target_weeks]);

  const pushAttributesAndNavigate = async () => {
    track('onboarding_screen_completed', { screen: 'N3_plan_reveal' });
    addBreadcrumb('onboarding', 'Plan reveal → paywall');

    if (isAdaptyConfigured()) {
      try {
        await adapty.updateProfile({
          codableCustomAttributes: {
            goal: intro.goal_type ?? 'track',
            pain_points: intro.pain_points.join(','),
            target_weight: intro.target_weight_kg ?? 0,
            target_calories: intro.target_calories ?? 0,
          },
        });
      } catch {
        // non-fatal: segmentation just won't work
      }
    }

    router.push('/paywall');
  };

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.header}>
        <AppText variant="overline" color={colors.terracottaText}>
          YOUR PERSONAL PLAN
        </AppText>
        <AppText variant="display" style={s.title}>
          {hasTarget
            ? `${intro.target_weight_kg} kg by ${targetDate}`
            : `${intro.target_calories} kcal / day`}
        </AppText>
      </View>

      <Card style={s.summaryCard}>
        <View style={s.macroGrid}>
          <View style={s.macroItem}>
            <AppText variant="h2">{intro.target_calories ?? '—'}</AppText>
            <AppText variant="caption" color={colors.inkMuted}>kcal/day</AppText>
          </View>
          <View style={s.macroItem}>
            <AppText variant="macroValue" color={colors.protein}>{intro.target_protein_g ?? '—'}g</AppText>
            <AppText variant="caption" color={colors.inkMuted}>protein</AppText>
          </View>
          <View style={s.macroItem}>
            <AppText variant="macroValue" color={colors.fat}>{intro.target_fat_g ?? '—'}g</AppText>
            <AppText variant="caption" color={colors.inkMuted}>fat</AppText>
          </View>
          <View style={s.macroItem}>
            <AppText variant="macroValue" color={colors.carbs}>{intro.target_carbs_g ?? '—'}g</AppText>
            <AppText variant="caption" color={colors.inkMuted}>carbs</AppText>
          </View>
        </View>
        {hasTarget && intro.deficit_pct && (
          <AppText variant="caption" color={colors.inkMuted} center>
            {intro.deficit_pct}% deficit · ~{intro.target_weeks} weeks
          </AppText>
        )}
      </Card>

      <AppText variant="overline" color={colors.inkMuted} style={s.socialLabel}>
        WHAT OTHERS SAY
      </AppText>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.testimonials}>
        {TESTIMONIALS.map((t) => (
          <Card key={t.author} style={s.testimonialCard}>
            <AppText variant="small" color={colors.inkMuted} style={s.quoteText}>
              "{t.text}"
            </AppText>
            <AppText variant="caption" color={colors.inkFaint}>— {t.author}</AppText>
          </Card>
        ))}
      </ScrollView>

      <Button
        label="Start my plan"
        variant="brand"
        onPress={pushAttributesAndNavigate}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.xl, marginBottom: space.lg, gap: space.sm },
  title: { marginTop: space.xs },
  summaryCard: { marginBottom: space.lg },
  macroGrid: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: space.md },
  macroItem: { alignItems: 'center', gap: 2 },
  socialLabel: { marginBottom: space.sm },
  testimonials: { gap: space.md, paddingRight: space.lg },
  testimonialCard: { width: 240, padding: space.base },
  quoteText: { fontStyle: 'italic', marginBottom: space.sm },
  cta: { marginTop: space.lg },
});
