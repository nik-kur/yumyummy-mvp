/**
 * Preview mode (V3 screen 21, artboard Preview_today): Today dimmed, a
 * "See how it works" bubble with a bobbing arrow over a glowing "+". Shown
 * while the free log is still available and nothing is being logged; a tap on
 * "+" opens capture, a tap anywhere else lets the person look around.
 */
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import Animated, {
  cancelAnimation,
  Easing,
  FadeIn,
  FadeOut,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';
import Svg, { Path } from 'react-native-svg';

import { track } from '@/analytics/posthog';
import { C, F, SHADOW } from '@/onb/theme';

import { measureTourTarget } from './TourOverlay';

interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function PreviewHint({ visible }: { visible: boolean }) {
  const router = useRouter();
  const { width } = useWindowDimensions();
  const [plus, setPlus] = useState<Box | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const show = visible && !dismissed;

  useEffect(() => {
    if (!show) return;
    let alive = true;
    const tick = () =>
      void measureTourTarget('plus').then((r) => {
        if (alive && r) setPlus((p) => (p && Math.abs(p.y - r.y) < 0.5 && Math.abs(p.x - r.x) < 0.5 ? p : { x: r.x, y: r.y, w: r.w, h: r.h }));
      });
    tick();
    const id = setInterval(tick, 400);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [show]);

  useEffect(() => {
    if (show && plus) track('preview_hint_shown');
  }, [show, plus]);

  const bob = useSharedValue(0);
  useEffect(() => {
    const e = Easing.inOut(Easing.ease);
    bob.value = withRepeat(withSequence(withTiming(-8, { duration: 1600, easing: e }), withTiming(0, { duration: 1600, easing: e })), -1);
    return () => cancelAnimation(bob);
  }, [bob]);
  const bobStyle = useAnimatedStyle(() => ({ transform: [{ translateY: bob.value }] }));

  if (!show || !plus) return null;
  const cx = plus.x + plus.w / 2;

  const openCapture = () => {
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    track('preview_hint_tapped');
    setDismissed(true);
    router.push('/capture');
  };

  return (
    <Animated.View entering={FadeIn.duration(250)} exiting={FadeOut.duration(150)} style={StyleSheet.absoluteFill}>
      <Pressable
        style={[StyleSheet.absoluteFill, s.dim]}
        onPress={() => setDismissed(true)}
        accessibilityRole="button"
        accessibilityLabel="Dismiss hint"
      />
      <View style={[s.bubble, SHADOW, { left: width / 2 - 100, top: plus.y - 100 }]} pointerEvents="none">
        <Text style={s.bubbleText}>See how it works</Text>
      </View>
      <Animated.View style={[s.arrow, { left: cx - 12, top: plus.y - 48 }, bobStyle]} pointerEvents="none">
        <Svg width={24} height={40} viewBox="0 0 24 40" fill="none">
          <Path d="M12 2V34M4 26l8 8 8-8" stroke="#FFFFFF" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
        </Svg>
      </Animated.View>
      <Pressable
        onPress={openCapture}
        style={[s.glow, { left: cx - 34, top: plus.y + plus.h / 2 - 34 }]}
        accessibilityRole="button"
        accessibilityLabel="Log a meal"
      >
        <View style={s.plus}>
          <Svg width={26} height={26} viewBox="0 0 24 24" fill="none">
            <Path d="M12 5v14M5 12h14" stroke={C.paper} strokeWidth={2} strokeLinecap="round" />
          </Svg>
        </View>
      </Pressable>
    </Animated.View>
  );
}

const s = StyleSheet.create({
  dim: { backgroundColor: 'rgba(20,16,12,0.38)' },
  bubble: {
    position: 'absolute',
    width: 200,
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: C.surface,
    borderRadius: 14,
    alignItems: 'center',
  },
  bubbleText: { fontFamily: F.sansSemibold, fontSize: 16, lineHeight: 21, color: C.ink },
  arrow: { position: 'absolute', width: 24, height: 40 },
  // The "+" itself inside the terracotta glow of the artboard (6 pt ring).
  glow: {
    position: 'absolute',
    width: 68,
    height: 68,
    borderRadius: 34,
    backgroundColor: 'rgba(184,90,58,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  plus: { width: 56, height: 56, borderRadius: 28, backgroundColor: C.ink, alignItems: 'center', justifyContent: 'center' },
});
