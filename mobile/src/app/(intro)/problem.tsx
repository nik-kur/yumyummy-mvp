/**
 * S9 Problem — "It all comes down to one thing" (prototype v3).
 * Animated calories-in vs calories-out balance cycling surplus → deficit,
 * followed by the two "traps" that quietly break CICO.
 */
import { useEffect, useRef, useState } from 'react';
import { View, ScrollView, StyleSheet, Animated, Pressable, Linking } from 'react-native';
import { useRouter } from 'expo-router';
import { ExternalLink } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { IntroHeader } from '@/components/IntroHeader';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

// Illustrative-chart tints (not UI chrome): softened red/green for the delta strip.
const SURPLUS_STRIP = '#C97A6A';
const DEFICIT_STRIP = '#7FA06F';

const TALL = 128;
const SHORT = 112;
const CYCLE_MS = 3400;

function CicoBalance() {
  const [surplus, setSurplus] = useState(true);
  const inH = useRef(new Animated.Value(TALL)).current;
  const outH = useRef(new Animated.Value(SHORT)).current;
  const deltaOp = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    let alive = true;
    let phase = true;

    const showDelta = () => {
      Animated.timing(deltaOp, { toValue: 1, duration: 300, useNativeDriver: false }).start();
    };
    // Initial delta reveal
    const t0 = setTimeout(showDelta, 850);

    const interval = setInterval(() => {
      if (!alive) return;
      Animated.timing(deltaOp, { toValue: 0, duration: 200, useNativeDriver: false }).start(() => {
        if (!alive) return;
        phase = !phase;
        setSurplus(phase);
        Animated.parallel([
          Animated.timing(inH, { toValue: phase ? TALL : SHORT, duration: 600, useNativeDriver: false }),
          Animated.timing(outH, { toValue: phase ? SHORT : TALL, duration: 600, useNativeDriver: false }),
        ]).start();
        setTimeout(() => alive && showDelta(), 850);
      });
    }, CYCLE_MS);

    return () => {
      alive = false;
      clearTimeout(t0);
      clearInterval(interval);
    };
  }, [inH, outH, deltaOp]);

  return (
    <View style={s.balanceCard}>
      <View style={s.bars}>
        <View style={s.barCol}>
          <Animated.View style={[s.bar, s.barIn, { height: inH }]}>
            {surplus && (
              <Animated.View style={[s.strip, { backgroundColor: SURPLUS_STRIP, opacity: deltaOp }]} />
            )}
            <AppText style={s.barNum}>{surplus ? '2,450' : '1,950'}</AppText>
          </Animated.View>
          <AppText variant="small" color={colors.inkMuted}>In</AppText>
        </View>
        <View style={s.barCol}>
          <Animated.View style={[s.bar, s.barOut, { height: outH }]}>
            {!surplus && (
              <Animated.View style={[s.strip, { backgroundColor: DEFICIT_STRIP, opacity: deltaOp }]} />
            )}
            <AppText style={s.barNum}>2,200</AppText>
          </Animated.View>
          <AppText variant="small" color={colors.inkMuted}>Out</AppText>
        </View>
      </View>
      <Animated.View style={{ opacity: deltaOp }}>
        <AppText
          variant="bodyStrong"
          color={surplus ? colors.error : colors.success}
          center
        >
          {surplus ? '+250 kcal a day ≈ +1 kg a month' : '−250 kcal a day ≈ −1 kg a month'}
        </AppText>
      </Animated.View>
      <AppText variant="caption" color={colors.inkFaint} center>
        Illustrative numbers
      </AppText>
    </View>
  );
}

const TRAPS = [
  {
    emoji: '📏',
    title: 'The margin is tiny',
    text: 'The gap between losing and gaining is often just 200–300 kcal a day. One dressing. One latte.',
  },
  {
    emoji: '🎯',
    title: 'Guesses are usually wrong',
    text: 'Most people misjudge what they eat by 20–40%. "Feels healthy" doesn\'t mean the numbers add up.',
  },
];

export default function ProblemScreen() {
  const router = useRouter();

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'S9_problem' });
  }, []);

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <IntroHeader step={8} />

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scroll}>
        <AppText variant="overline" color={colors.terracottaText}>The truth</AppText>
        <AppText variant="h1" style={s.title}>It all comes down to one thing</AppText>
        <AppText variant="body" color={colors.inkMuted} style={s.lead}>
          Weight change is driven by one equation:{' '}
          <AppText variant="bodyStrong">calories in vs. calories out.</AppText>
        </AppText>

        <CicoBalance />

        <AppText variant="body" color={colors.inkMuted} style={s.breaker}>
          Sounds simple. But two things quietly break it:
        </AppText>

        {TRAPS.map((t) => (
          <View key={t.title} style={s.trap}>
            <AppText style={s.trapEmoji}>{t.emoji}</AppText>
            <View style={s.trapText}>
              <AppText variant="title">{t.title}</AppText>
              <AppText variant="small" color={colors.inkMuted}>{t.text}</AppText>
            </View>
          </View>
        ))}

        <Pressable
          onPress={() => Linking.openURL('https://pubmed.ncbi.nlm.nih.gov/1454084/').catch(() => {})}
          hitSlop={8}
          style={s.research}
        >
          <AppText variant="caption" color={colors.inkFaint}>
            Research: self-reported food intake is off by ~30% on average (Lichtman et al., NEJM 1992).
          </AppText>
          <ExternalLink size={12} color={colors.infoBlue} strokeWidth={1.5} />
        </Pressable>
      </ScrollView>

      <Button
        label="So what's the answer?"
        variant="brand"
        onPress={() => {
          track('onboarding_screen_completed', { screen: 'S9_problem' });
          router.push('/(intro)/fix');
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  scroll: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingTop: space.sm,
    paddingBottom: space.base,
  },
  title: { marginTop: space.sm },
  lead: { marginTop: space.sm },
  balanceCard: {
    marginTop: space.lg,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.base,
    gap: space.md,
  },
  bars: {
    flexDirection: 'row',
    gap: space.lg,
    alignItems: 'flex-end',
    justifyContent: 'center',
    height: TALL + 26,
  },
  barCol: { width: 86, alignItems: 'center', gap: space.xs },
  bar: {
    width: '100%',
    borderRadius: radius.md,
    overflow: 'hidden',
    justifyContent: 'flex-end',
    alignItems: 'center',
  },
  barIn: { backgroundColor: colors.terracotta },
  barOut: { backgroundColor: colors.ink },
  strip: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: 16,
  },
  barNum: { color: colors.white, fontSize: 12, lineHeight: 16, marginBottom: space.sm },
  breaker: { marginTop: space.lg },
  trap: {
    flexDirection: 'row',
    gap: space.md,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.base,
    marginTop: space.md,
  },
  trapEmoji: { fontSize: 22, lineHeight: 28 },
  trapText: { flex: 1, gap: 2 },
  research: {
    marginTop: space.base,
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    flexWrap: 'wrap',
  },
  cta: { marginTop: space.sm },
});
