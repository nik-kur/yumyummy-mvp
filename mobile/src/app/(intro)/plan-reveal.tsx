/**
 * N3 Plan Reveal — daily target card, weight trajectory (lose/gain) or
 * maintenance zone (maintain/track), facts chips and an auto-rotating
 * testimonial carousel (prototype v3).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { View, StyleSheet, Animated, Image } from 'react-native';
import { useRouter } from 'expo-router';
import { adapty } from 'react-native-adapty';
import Svg, { Path, Line, Circle, Text as SvgText } from 'react-native-svg';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { SourcesLink } from '@/components/SourcesLink';
import { useIntro } from '@/state/introContext';
import { isAdaptyConfigured } from '@/billing/adapty';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';
import { track } from '@/analytics/posthog';
import { addBreadcrumb } from '@/analytics/sentry';

const STAR_GOLD = '#D99A28';

const AVATARS: Record<string, number> = {
  Maria: require('../../../assets/avatars/maria.jpg'),
  Denis: require('../../../assets/avatars/denis.jpg'),
  Sara: require('../../../assets/avatars/sara.jpg'),
  James: require('../../../assets/avatars/james.jpg'),
  Priya: require('../../../assets/avatars/priya.jpg'),
  Tom: require('../../../assets/avatars/tom.jpg'),
  Elena: require('../../../assets/avatars/elena.jpg'),
  Chris: require('../../../assets/avatars/chris.jpg'),
  Sophie: require('../../../assets/avatars/sophie.jpg'),
  Alex: require('../../../assets/avatars/alex.jpg'),
};

const TESTIMONIALS = [
  { name: 'Maria', text: 'Six weeks in and down 4 kg. Logging takes me maybe a minute a day — that\'s the whole trick.', who: 'lost 4 kg' },
  { name: 'Denis', text: 'I stopped guessing. The app knows the real numbers, so I finally trust what I eat.', who: 'maintaining' },
  { name: 'Sara', text: 'Tried three trackers before. This is the first one I didn\'t quit.', who: 'lost 6 kg' },
  { name: 'James', text: 'The weight graph actually matched reality — small ups and downs, but the trend was right.', who: 'lost 8 kg' },
  { name: 'Priya', text: 'Gaining lean mass without guessing portions. Macros finally make sense day to day.', who: 'gaining lean mass' },
  { name: 'Tom', text: 'Maintenance used to feel like a second job. Now I just check in and move on.', who: 'maintaining' },
  { name: 'Elena', text: 'Photo logging changed everything — I log restaurant meals I used to skip entirely.', who: 'lost 3 kg' },
  { name: 'Chris', text: 'Voice logging at lunch is stupidly fast. I\'m on a 19-day streak now.', who: 'lost 5 kg' },
  { name: 'Sophie', text: 'First tracker where the numbers felt verified, not made up by AI.', who: 'first-time tracker' },
  { name: 'Alex', text: 'Down 7 kg in 10 weeks. The plan felt realistic from day one — no crash-diet vibes.', who: 'lost 7 kg' },
];

function fmtDate(weeksFromNow: number): string {
  const d = new Date();
  d.setDate(d.getDate() + weeksFromNow * 7);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/** Weight trajectory with realistic week-to-week fluctuation. */
function Trajectory({
  weight,
  target,
  weeks,
  gaining,
}: {
  weight: number;
  target: number;
  weeks: number;
  gaining?: boolean;
}) {
  const W = 330;
  const H = 190;
  const padL = 14;
  const padR = 60;
  const padT = 22;
  const padB = 30;

  const lo = Math.min(weight, target) - 0.8;
  const hi = Math.max(weight, target) + 0.8;
  const span = Math.max(1.5, hi - lo);
  const x = (t: number) => padL + t * (W - padL - padR);
  const y = (v: number) => padT + ((hi - v) / span) * (H - padT - padB);

  const pts = Array.from({ length: 40 }, (_, i) => {
    const t = i / 39;
    const progress = gaining ? t : t;
    const base = gaining
      ? weight + (target - weight) * progress ** 1.35
      : target + (weight - target) * (1 - progress) ** 1.35;
    const waveAmp = span * 0.07 * (1 - progress * 0.65);
    const wave =
      waveAmp *
      (Math.sin(progress * Math.PI * 5.2) * 0.55 +
        Math.sin(progress * Math.PI * 2.4 + 0.8) * 0.35 +
        Math.sin(progress * Math.PI * 8.1 + 1.4) * 0.1);
    const plateau = progress > 0.32 && progress < 0.48 ? waveAmp * 0.45 : 0;
    const v = base + wave + plateau;
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
      <Circle cx={pts[39].px} cy={pts[39].py} r={5.5} fill={colors.terracotta} />
      <SvgText x={pts[0].px + 8} y={pts[0].py - 8} fontSize={11} fill={colors.inkMuted}>
        {`${weight} kg`}
      </SvgText>
      <SvgText
        x={pts[39].px + 10}
        y={pts[39].py + 4}
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

function Avatar({ name }: { name: string }) {
  const src = AVATARS[name];
  if (!src) {
    return (
      <View style={[s.avatar, { backgroundColor: colors.terracottaSoft }]}>
        <AppText variant="bodyStrong" color={colors.ink}>{name.charAt(0)}</AppText>
      </View>
    );
  }
  return <Image source={src} style={s.avatar} />;
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
      <Animated.View style={[s.carouselInner, { opacity }]}>
        <View style={s.carouselTop}>
          <Avatar name={t.name} />
          <View style={s.carouselMeta}>
            <AppText variant="bodyStrong">{t.name}</AppText>
            <AppText variant="caption" color={colors.terracottaText}>{t.who}</AppText>
          </View>
        </View>
        <AppText style={s.stars}>★★★★★</AppText>
        <AppText variant="body" style={s.quote}>
          “{t.text}”
        </AppText>
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
        // non-fatal
      }
    }

    router.push('/paywall');
  };

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.body}>
        <View style={s.header}>
          <AppText variant="overline" color={colors.terracottaText} center>
            Your plan is ready
          </AppText>
          <AppText variant="h1" center>Here’s your daily target</AppText>
        </View>

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
          <SourcesLink label="Mifflin–St Jeor equation — see the science" center />
        </View>

        {hasTarget && intro.target_weight_kg && intro.target_weeks ? (
          <View style={s.trajCard}>
            <Trajectory
              weight={intro.weight_kg}
              target={intro.target_weight_kg}
              weeks={intro.target_weeks}
              gaining={intro.goal_type === 'gain'}
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
              ⚖️ Your maintenance zone:{' '}
              <AppText variant="bodyStrong">
                {zoneLo.toLocaleString('en-US')}–{zoneHi.toLocaleString('en-US')} kcal
              </AppText>
              . Stay inside it — weight stays put.
            </AppText>
          </View>
        )}

        <View style={s.carouselWrap}>
          <TestimonialCarousel />
        </View>
      </View>

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
  body: { flex: 1, gap: space.base },
  header: { gap: space.sm, marginTop: space.sm },
  planCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    paddingVertical: space.lg,
    paddingHorizontal: space.base,
    gap: space.base,
    alignItems: 'center',
  },
  kcalRow: { flexDirection: 'row', alignItems: 'baseline', gap: space.sm },
  kcalBig: {
    fontFamily: fonts.serifBold,
    fontSize: 64,
    lineHeight: 72,
    color: colors.ink,
  },
  macroRow: { flexDirection: 'row', gap: space.sm, alignSelf: 'stretch' },
  macroBox: {
    flex: 1,
    borderRadius: radius.md,
    paddingVertical: space.md,
    alignItems: 'center',
    gap: 2,
  },
  trajCard: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.md,
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
  },
  carouselWrap: { flex: 1, minHeight: 140 },
  carousel: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.base,
    justifyContent: 'space-between',
  },
  carouselInner: { gap: space.sm },
  carouselTop: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  carouselMeta: { gap: 2 },
  avatar: {
    width: 52,
    height: 52,
    borderRadius: 26,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  stars: { color: STAR_GOLD, fontSize: 15, lineHeight: 18 },
  quote: { lineHeight: 23 },
  dots: {
    flexDirection: 'row',
    gap: 5,
    justifyContent: 'center',
    flexWrap: 'wrap',
    marginTop: space.sm,
  },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: colors.hairlineStrong },
  dotActive: { backgroundColor: colors.terracotta },
  cta: { marginTop: space.md },
});
