/**
 * N3 Plan Reveal — daily target card, weight trajectory (lose/gain) or
 * maintenance zone (maintain/track), facts chips and an auto-rotating
 * testimonial carousel (prototype v3).
 *
 * Before navigating to the paywall, pushes custom attributes to Adapty
 * for audience segmentation (anonymous profile, pre-purchase).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { View, StyleSheet, Animated } from 'react-native';
import { useRouter } from 'expo-router';
import { adapty } from 'react-native-adapty';
import Svg, { Path, Line, Circle, Text as SvgText } from 'react-native-svg';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useIntro } from '@/state/introContext';
import { isAdaptyConfigured } from '@/billing/adapty';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';
import { track } from '@/analytics/posthog';
import { addBreadcrumb } from '@/analytics/sentry';

const STAR_GOLD = '#D99A28';

const TESTIMONIALS = [
  {
    text: 'Six weeks in and down 4 kg. Logging takes me maybe a minute a day — that\'s the whole trick.',
    who: 'Maria · lost 4 kg',
  },
  {
    text: 'I stopped guessing. The app knows the real numbers, so I finally trust what I eat.',
    who: 'Denis · maintaining',
  },
  {
    text: 'Tried three trackers before. This is the first one I didn\'t quit.',
    who: 'Sara · lost 6 kg',
  },
];

function fmtDate(weeksFromNow: number): string {
  const d = new Date();
  d.setDate(d.getDate() + weeksFromNow * 7);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Weight trajectory: fast start easing into the target (v = t1 + Δ·(1−t)^1.5). */
function Trajectory({ weight, target, weeks }: { weight: number; target: number; weeks: number }) {
  const W = 330;
  const H = 150;
  const padL = 14;
  const padR = 60;
  const padT = 20;
  const padB = 28;

  const lo = Math.min(weight, target);
  const hi = Math.max(weight, target);
  const span = Math.max(1, hi - lo);
  const x = (t: number) => padL + t * (W - padL - padR);
  const y = (v: number) => padT + ((hi - v) / span) * (H - padT - padB);

  const pts = Array.from({ length: 25 }, (_, i) => {
    const t = i / 24;
    const v = target + (weight - target) * (1 - t) ** 1.5;
    return { px: x(t), py: y(v) };
  });
  const d = pts
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.px.toFixed(1)} ${p.py.toFixed(1)}`)
    .join(' ');
  const yTarget = y(target);

  return (
    <Svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`}>
      <Line
        x1={padL}
        y1={yTarget}
        x2={W - padR}
        y2={yTarget}
        stroke={colors.hairlineStrong}
        strokeWidth={1}
        strokeDasharray="4 4"
      />
      <Path d={d} stroke={colors.terracotta} strokeWidth={2.5} fill="none" />
      <Circle cx={pts[0].px} cy={pts[0].py} r={4.5} fill={colors.ink} />
      <Circle cx={pts[24].px} cy={pts[24].py} r={5.5} fill={colors.terracotta} />
      <SvgText x={pts[0].px + 8} y={pts[0].py - 8} fontSize={11} fill={colors.inkMuted}>
        {`${weight} kg`}
      </SvgText>
      <SvgText
        x={pts[24].px + 10}
        y={pts[24].py + 4}
        fontSize={11}
        fontWeight="bold"
        fill={colors.terracottaText}
      >
        {`${target} kg`}
      </SvgText>
      <SvgText x={padL} y={H - 8} fontSize={10} fill={colors.inkFaint}>
        {fmtDate(0)}
      </SvgText>
      <SvgText x={W - padR} y={H - 8} fontSize={10} fill={colors.inkFaint} textAnchor="end">
        {fmtDate(weeks)}
      </SvgText>
    </Svg>
  );
}

function TestimonialCarousel() {
  const [idx, setIdx] = useState(0);
  const opacity = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    const interval = setInterval(() => {
      Animated.timing(opacity, { toValue: 0, duration: 250, useNativeDriver: true }).start(() => {
        setIdx((i) => (i + 1) % TESTIMONIALS.length);
        Animated.timing(opacity, { toValue: 1, duration: 250, useNativeDriver: true }).start();
      });
    }, 3200);
    return () => clearInterval(interval);
  }, [opacity]);

  const t = TESTIMONIALS[idx];
  return (
    <View style={s.carousel}>
      <Animated.View style={{ opacity }}>
        <AppText style={s.stars}>★★★★★</AppText>
        <AppText variant="small" color={colors.inkMuted} style={s.quote}>
          “{t.text}”
        </AppText>
        <AppText variant="caption" color={colors.terracottaText}>— {t.who}</AppText>
      </Animated.View>
      <View style={s.dots}>
        {TESTIMONIALS.map((_, i) => (
          <View key={i} style={[s.dot, i === idx && s.dotActive]} />
        ))}
      </View>
    </View>
  );
}

export default function PlanRevealScreen() {
  const router = useRouter();
  const intro = useIntro();

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'N3_plan_reveal' });
  }, []);

  const hasTarget =
    (intro.goal_type === 'lose' || intro.goal_type === 'gain') &&
    !!intro.target_weight_kg &&
    !!intro.target_weeks;

  const cal = intro.target_calories ?? 0;
  const pace = useMemo(() => {
    if (!hasTarget || !intro.target_weight_kg || !intro.target_weeks) return 0;
    return Math.abs(intro.weight_kg - intro.target_weight_kg) / intro.target_weeks;
  }, [hasTarget, intro.weight_kg, intro.target_weight_kg, intro.target_weeks]);

  const zoneLo = Math.round((cal * 0.97) / 10) * 10;
  const zoneHi = Math.round((cal * 1.03) / 10) * 10;

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
        <AppText variant="overline" color={colors.terracottaText} center>
          Your plan is ready
        </AppText>
        <AppText variant="h1" center>Here’s your daily target</AppText>
      </View>

      {/* Daily target card */}
      <View style={s.planCard}>
        <View style={s.kcalRow}>
          <AppText style={s.kcalBig}>{cal.toLocaleString('en-US')}</AppText>
          <AppText variant="small" color={colors.inkMuted}>kcal/day</AppText>
        </View>
        <View style={s.macroRow}>
          <View style={[s.macroBox, { backgroundColor: colors.oliveSoft }]}>
            <AppText variant="bodyStrong" color={colors.protein}>{intro.target_protein_g ?? '—'} g</AppText>
            <AppText variant="caption" color={colors.protein}>Protein</AppText>
          </View>
          <View style={[s.macroBox, { backgroundColor: colors.warningSoft }]}>
            <AppText variant="bodyStrong" color={colors.fat}>{intro.target_fat_g ?? '—'} g</AppText>
            <AppText variant="caption" color={colors.fat}>Fat</AppText>
          </View>
          <View style={[s.macroBox, { backgroundColor: colors.infoBlueSoft }]}>
            <AppText variant="bodyStrong" color={colors.carbs}>{intro.target_carbs_g ?? '—'} g</AppText>
            <AppText variant="caption" color={colors.carbs}>Carbs</AppText>
          </View>
        </View>
      </View>

      {hasTarget && intro.target_weight_kg && intro.target_weeks ? (
        <View style={s.trajCard}>
          <Trajectory
            weight={intro.weight_kg}
            target={intro.target_weight_kg}
            weeks={intro.target_weeks}
          />
          <View style={s.factsRow}>
            <View style={s.factChip}>
              <AppText variant="caption">
                {intro.goal_type === 'lose' ? '−' : '+'}{pace.toFixed(1)} kg/week
              </AppText>
            </View>
            <View style={s.factChip}>
              <AppText variant="caption">{cal.toLocaleString('en-US')} kcal/day</AppText>
            </View>
            {intro.deficit_pct ? (
              <View style={s.factChip}>
                <AppText variant="caption">
                  {intro.deficit_pct}% {intro.goal_type === 'lose' ? 'below' : 'above'} burn
                </AppText>
              </View>
            ) : null}
          </View>
        </View>
      ) : (
        <View style={s.zoneCard}>
          <AppText variant="body">
            ⚖️ Your maintenance zone: <AppText variant="bodyStrong">{zoneLo.toLocaleString('en-US')}–{zoneHi.toLocaleString('en-US')} kcal</AppText>.
            Stay inside it — weight stays put.
          </AppText>
        </View>
      )}

      <TestimonialCarousel />

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
  planCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.base,
    gap: space.md,
    alignItems: 'center',
  },
  kcalRow: { flexDirection: 'row', alignItems: 'baseline', gap: space.sm },
  kcalBig: {
    fontFamily: fonts.serifBold,
    fontSize: 52,
    lineHeight: 60,
    color: colors.ink,
  },
  macroRow: { flexDirection: 'row', gap: space.sm, alignSelf: 'stretch' },
  macroBox: {
    flex: 1,
    borderRadius: radius.md,
    paddingVertical: space.sm,
    alignItems: 'center',
    gap: 1,
  },
  trajCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.md,
    marginTop: space.md,
    gap: space.sm,
  },
  factsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, justifyContent: 'center' },
  factChip: {
    paddingHorizontal: space.md,
    paddingVertical: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.hairline,
  },
  zoneCard: {
    backgroundColor: colors.infoBlueSoft,
    borderRadius: radius.lg,
    padding: space.base,
    marginTop: space.md,
  },
  carousel: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.base,
    marginTop: space.md,
    minHeight: 132,
  },
  stars: { color: STAR_GOLD, fontSize: 14, lineHeight: 18, marginBottom: space.xs },
  quote: { fontStyle: 'italic', marginBottom: space.sm },
  dots: {
    flexDirection: 'row',
    gap: 6,
    justifyContent: 'center',
    marginTop: space.md,
  },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.hairlineStrong },
  dotActive: { backgroundColor: colors.terracotta },
  cta: { marginTop: space.lg },
});
