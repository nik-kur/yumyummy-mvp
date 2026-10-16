/**
 * Screen 0 — "the icon comes alive" (canvas V3_Splash, V3_Splash_story).
 *
 * Picks up exactly where the native launch screen leaves off (terracotta, cream
 * "Y" in the centre), then: the "Y" pops (0.3–0.5 s) and a cream disc opens with
 * the peach jumping into it (Soft haptic at 0.42 s); the heart beats twice and
 * two rings ripple out (Light → Medium, 130 ms apart); the name rises in letter
 * by letter (≈1.4 s). It holds there until the onboarding config has arrived,
 * then fades out and calls `onDone`.
 *
 * Positions are the canvas's 390 × 844 coordinates on a stage centred on the
 * screen, so the "Y" lands on the native splash's "Y" on any iPhone.
 */
import { useEffect, useRef, useState } from 'react';
import { AccessibilityInfo, StyleSheet, View, useWindowDimensions } from 'react-native';
import Animated, {
  Easing,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withSequence,
  withTiming,
  type EasingFunction,
  type EasingFunctionFactory,
  type SharedValue,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';

import { fonts } from '@/theme/typography';

export const SPLASH_BG = '#B85A3A';
const CREAM = '#F7F1E6';
const STAGE_W = 390;
const STAGE_H = 844;
/** Earliest the splash may leave: the name is fully in by ~1.3 s. */
export const SPLASH_MIN_MS = 1500;

const POP = Easing.bezier(0.3, 0.7, 0.4, 1);
const IN_OUT = Easing.inOut(Easing.ease);
const OUT = Easing.out(Easing.ease);

const LETTERS = 'YumYummy'.split('');
const MASCOT = require('../../../assets/v3/splash/mascot_heart.png');

/**
 * Drive `sv` through absolute-time keyframes: `[[ms, value], …]`, starting from
 * the first frame's value at its time.
 */
function keyframes(
  sv: SharedValue<number>,
  frames: [number, number][],
  easing: EasingFunction | EasingFunctionFactory,
) {
  const [t0, v0] = frames[0];
  sv.value = v0;
  const steps = frames.slice(1).map(([t, v], i) =>
    withTiming(v, { duration: Math.max(1, t - frames[i][0]), easing }),
  );
  sv.value = withDelay(t0, withSequence(...(steps as [number]))) as number;
}

interface Props {
  /** The onboarding config is in; the splash may leave once its intro has played. */
  ready: boolean;
  onDone: () => void;
}

export function SplashIntro({ ready, onDone }: Props) {
  const { width, height } = useWindowDimensions();
  const [reduceMotion, setReduceMotion] = useState<boolean | null>(null);
  const [introPlayed, setIntroPlayed] = useState(false);
  const exiting = useRef(false);

  const iconScale = useSharedValue(1);
  const iconOpacity = useSharedValue(1);
  const discScale = useSharedValue(0.2);
  const discOpacity = useSharedValue(0);
  const peachY = useSharedValue(24);
  const peachSX = useSharedValue(0.4);
  const peachSY = useSharedValue(0.4);
  const peachOpacity = useSharedValue(0);
  const ring1Scale = useSharedValue(1);
  const ring1Opacity = useSharedValue(0);
  const ring2Scale = useSharedValue(1);
  const ring2Opacity = useSharedValue(0);
  const letters = LETTERS.map(() => ({
    // eslint-disable-next-line react-hooks/rules-of-hooks
    y: useSharedValue(10),
    // eslint-disable-next-line react-hooks/rules-of-hooks
    o: useSharedValue(0),
  }));
  const exit = useSharedValue(0);

  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled()
      .then(setReduceMotion)
      .catch(() => setReduceMotion(false));
  }, []);

  useEffect(() => {
    if (reduceMotion === null) return;
    if (reduceMotion) {
      // Final frame, no motion, no haptics.
      iconOpacity.value = 0;
      discScale.value = 1;
      discOpacity.value = 1;
      peachY.value = 0;
      peachSX.value = 1;
      peachSY.value = 1;
      peachOpacity.value = 1;
      letters.forEach((l) => {
        l.y.value = 0;
        l.o.value = 1;
      });
      setIntroPlayed(true);
      return;
    }

    keyframes(iconScale, [[150, 1], [300, 0.86], [420, 1.3]], IN_OUT);
    keyframes(iconOpacity, [[300, 1], [420, 0]], IN_OUT);
    keyframes(discScale, [[300, 0.2], [440, 1.08], [560, 1]], POP);
    keyframes(discOpacity, [[300, 0], [440, 1]], POP);
    keyframes(peachY, [[380, 24], [500, -10], [620, 0]], POP);
    keyframes(peachSX, [[380, 0.4], [500, 1.06], [620, 1.05], [720, 1], [850, 1.07], [920, 1], [980, 1.05], [1050, 1]], POP);
    keyframes(peachSY, [[380, 0.4], [500, 1.06], [620, 0.94], [720, 1], [850, 1.07], [920, 1], [980, 1.05], [1050, 1]], POP);
    keyframes(peachOpacity, [[380, 0], [500, 1]], POP);
    keyframes(ring1Scale, [[840, 1], [860, 1.02], [1450, 1.6]], OUT);
    keyframes(ring1Opacity, [[840, 0], [860, 0.5], [1450, 0]], OUT);
    keyframes(ring2Scale, [[970, 1], [990, 1.02], [1600, 1.75]], OUT);
    keyframes(ring2Opacity, [[970, 0], [990, 0.4], [1600, 0]], OUT);
    letters.forEach((l, i) => {
      const start = 700 + i * 50;
      keyframes(l.y, [[start, 10], [start + 220, 0]], OUT);
      keyframes(l.o, [[start, 0], [start + 220, 1]], OUT);
    });

    const timers = [
      setTimeout(() => void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Soft).catch(() => {}), 420),
      setTimeout(() => void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {}), 850),
      setTimeout(() => void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {}), 980),
      setTimeout(() => setIntroPlayed(true), SPLASH_MIN_MS),
    ];
    return () => timers.forEach(clearTimeout);
    // Shared values are stable; the intro plays once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reduceMotion]);

  useEffect(() => {
    if (!ready || !introPlayed || exiting.current) return;
    exiting.current = true;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      onDone();
    };
    exit.value = withTiming(1, { duration: 200, easing: OUT }, () => {
      runOnJS(finish)();
    });
    // An interrupted animation must not strand the user on the splash.
    const fallback = setTimeout(finish, 600);
    return () => clearTimeout(fallback);
  }, [ready, introPlayed, exit, onDone]);

  // Exit (canvas 83–89 %): disc, peach and name shrink to 0.6 and fade.
  const iconStyle = useAnimatedStyle(() => ({
    opacity: iconOpacity.value,
    transform: [{ scale: iconScale.value }],
  }));
  const discStyle = useAnimatedStyle(() => ({
    opacity: discOpacity.value * (1 - exit.value),
    transform: [{ scale: discScale.value * (1 - 0.4 * exit.value) }],
  }));
  const peachStyle = useAnimatedStyle(() => {
    const k = 1 - 0.4 * exit.value;
    return {
      opacity: peachOpacity.value * (1 - exit.value),
      transform: [
        { translateY: peachY.value },
        { scaleX: peachSX.value * k },
        { scaleY: peachSY.value * k },
      ],
    };
  });
  const ring1Style = useAnimatedStyle(() => ({
    opacity: ring1Opacity.value,
    transform: [{ scale: ring1Scale.value }],
  }));
  const ring2Style = useAnimatedStyle(() => ({
    opacity: ring2Opacity.value,
    transform: [{ scale: ring2Scale.value }],
  }));
  const nameStyle = useAnimatedStyle(() => ({ opacity: 1 - exit.value }));

  const stage = {
    left: (width - STAGE_W) / 2,
    top: height / 2 - STAGE_H / 2,
  };

  return (
    <View style={s.fill} accessibilityLabel="YumYummy">
      <View style={[s.stage, stage]} pointerEvents="none">
        <Animated.View style={[s.ring, ring1Style]} />
        <Animated.View style={[s.ring, ring2Style]} />
        <Animated.View style={[s.icon, iconStyle]}>
          <Animated.Text style={s.iconText}>Y</Animated.Text>
        </Animated.View>
        <Animated.View style={[s.disc, discStyle]} />
        <Animated.Image source={MASCOT} style={[s.peach, peachStyle]} />
        <Animated.View style={[s.name, nameStyle]}>
          {LETTERS.map((ch, i) => (
            <Letter key={i} ch={ch} y={letters[i].y} o={letters[i].o} />
          ))}
        </Animated.View>
      </View>
    </View>
  );
}

function Letter({ ch, y, o }: { ch: string; y: SharedValue<number>; o: SharedValue<number> }) {
  const style = useAnimatedStyle(() => ({ opacity: o.value, transform: [{ translateY: y.value }] }));
  return <Animated.Text style={[s.nameText, style]}>{ch}</Animated.Text>;
}

/** The native launch screen, drawn in JS: shown while auth restores, no motion. */
export function StaticSplash() {
  return (
    <View style={[s.fill, s.center]} accessibilityLabel="YumYummy">
      <View style={s.staticIcon}>
        <Animated.Text style={s.iconText}>Y</Animated.Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  fill: { flex: 1, backgroundColor: SPLASH_BG, overflow: 'hidden' },
  center: { alignItems: 'center', justifyContent: 'center' },
  stage: { position: 'absolute', width: STAGE_W, height: STAGE_H },
  ring: {
    position: 'absolute',
    left: 87,
    top: 292,
    width: 216,
    height: 216,
    borderRadius: 108,
    borderWidth: 2,
    borderColor: CREAM,
  },
  icon: {
    position: 'absolute',
    left: 147,
    top: 374,
    width: 96,
    height: 96,
    alignItems: 'center',
    justifyContent: 'center',
  },
  staticIcon: { width: 96, height: 96, alignItems: 'center', justifyContent: 'center' },
  iconText: {
    fontFamily: fonts.serifSemibold,
    fontSize: 76,
    lineHeight: 76,
    color: CREAM,
    marginTop: 6,
  },
  disc: {
    position: 'absolute',
    left: 89,
    top: 294,
    width: 212,
    height: 212,
    borderRadius: 106,
    backgroundColor: CREAM,
  },
  peach: {
    position: 'absolute',
    left: 109,
    top: 316,
    width: 172,
    height: 172,
    transformOrigin: '50% 85%',
  },
  name: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 528,
    flexDirection: 'row',
    justifyContent: 'center',
  },
  nameText: {
    fontFamily: fonts.serifSemibold,
    fontSize: 40,
    lineHeight: 48,
    letterSpacing: -0.4,
    color: CREAM,
  },
});
