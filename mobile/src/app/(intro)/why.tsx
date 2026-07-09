/**
 * S3 Why this works — goal-specific big-stat science screen (prototype v3).
 *
 * Copy is final per Onboarding_Flow_Spec_v3.md §2 (concrete citations).
 */
import { useEffect } from 'react';
import { View, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { IntroHeader } from '@/components/IntroHeader';
import { useIntro } from '@/state/introContext';
import type { GoalType } from '@/utils/calories';
import { colors, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';
import { track } from '@/analytics/posthog';

interface WhyCopy {
  stat: string;
  statcap: string;
  h: string;
  b: string;
  foot: string;
}

const GOAL_COPY: Record<GoalType, WhyCopy> = {
  lose: {
    stat: '2×',
    statcap: 'more weight lost, on average',
    h: 'Tracking is your biggest lever',
    b: "People who log their meals consistently lose about twice as much weight as those who don't — and keep it off longer.",
    foot: 'Kaiser Permanente study of 1,685 adults · Am J Prev Med, 2008',
  },
  maintain: {
    stat: '#1',
    statcap: 'predictor of keeping it off',
    h: 'The habit that makes it stick',
    b: 'Simply writing down what you eat is one of the strongest predictors of maintaining a healthy weight for good.',
    foot: 'National Weight Control Registry · 10,000+ tracked members',
  },
  gain: {
    stat: '2×',
    statcap: 'faster lean gains',
    h: 'Muscle is a numbers game',
    b: 'Hit your protein and calorie targets consistently and you build lean mass far faster than training alone.',
    foot: 'Meta-analysis of 49 trials · Br J Sports Med, 2018',
  },
  just_track: {
    stat: '~30%',
    statcap: 'how much people misjudge intake',
    h: 'Awareness changes everything',
    b: 'Most people misjudge what they eat by about a third. Just seeing the real numbers is often enough to shift habits.',
    foot: 'Lichtman et al. · New England Journal of Medicine, 1992',
  },
};

export default function WhyScreen() {
  const router = useRouter();
  const { goal_type } = useIntro();
  const copy = GOAL_COPY[goal_type ?? 'lose'];

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'S3_why' });
  }, []);

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <IntroHeader step={2} />

      <AppText variant="overline" color={colors.terracottaText} style={s.eyebrow}>
        Why this works
      </AppText>

      <View style={s.content}>
        <AppText style={s.bigStat} center>{copy.stat}</AppText>
        <AppText variant="small" color={colors.inkMuted} center style={s.statCap}>
          {copy.statcap}
        </AppText>
        <AppText variant="h1" center style={s.headline}>{copy.h}</AppText>
        <AppText variant="body" color={colors.inkMuted} center style={s.body}>
          {copy.b}
        </AppText>
        <AppText variant="caption" color={colors.inkFaint} center style={s.foot}>
          {copy.foot}
        </AppText>
      </View>

      <Button
        label="Continue"
        variant="brand"
        onPress={() => {
          track('onboarding_screen_completed', { screen: 'S3_why' });
          router.push('/(intro)/gender');
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  eyebrow: { marginTop: space.md },
  content: { flex: 1, justifyContent: 'center', paddingHorizontal: space.sm },
  bigStat: {
    fontFamily: fonts.serifBold,
    fontSize: 60,
    lineHeight: 66,
    color: colors.terracotta,
  },
  statCap: { marginTop: space.xs },
  headline: { marginTop: space.base },
  body: { marginTop: space.sm },
  foot: { marginTop: space.base },
  cta: { marginTop: 'auto' },
});
