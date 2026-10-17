/**
 * V3 screen 22 — Success: right after StoreKit confirms the purchase.
 * Signed-out buyers continue to the sign-in gate (/save-plan, screen 23);
 * signed-in ones (lapsed member, Profile) go straight to Today.
 */
import { useEffect, useRef } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import Animated, {
  cancelAnimation,
  Easing,
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { track } from '@/analytics/posthog';
import { OnbButton } from '@/components/onb/OnbButton';
import { OnbLayout } from '@/components/onb/OnbLayout';
import { IMG } from '@/onb/assets';
import { C, F } from '@/onb/theme';

const ROWS = [
  { icon: IMG.feat_snap, text: 'Unlimited photo, voice and text logs' },
  { icon: IMG.feat_verified, text: 'Verified numbers with their sources' },
  { icon: IMG.feat_target, text: 'Your plan, weekly recap and AI advisor' },
];

/** Canvas `yy-hop`, 1.5 s: squash, jump 20 pt with a stretch, land, settle. */
function HoppingMascot() {
  const t = useSharedValue(0);
  useEffect(() => {
    t.value = withRepeat(withTiming(1, { duration: 1500, easing: Easing.bezier(0.3, 0.7, 0.4, 1) }), -1);
    return () => cancelAnimation(t);
  }, [t]);
  const style = useAnimatedStyle(() => {
    const p = [0, 0.12, 0.4, 0.62, 0.78, 1];
    return {
      transform: [
        { translateY: interpolate(t.value, p, [0, 0, -20, 0, 0, 0]) },
        { scaleX: interpolate(t.value, p, [1, 1.05, 0.97, 1.04, 1, 1]) },
        { scaleY: interpolate(t.value, p, [1, 0.95, 1.04, 0.96, 1, 1]) },
      ],
    };
  });
  return (
    <View style={s.circle}>
      <Animated.View style={[s.mascotBox, style]}>
        <Image source={IMG.mascot_stellar} style={s.mascot} accessibilityLabel="YumYummy peach mascot jumping with joy" />
      </Animated.View>
    </View>
  );
}

export default function SuccessScreen() {
  const router = useRouter();
  const { next } = useLocalSearchParams<{ next?: string }>();
  const signedOut = next !== 'tabs';

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'S22_success', next: signedOut ? 'save_plan' : 'tabs' });
  }, [signedOut]);

  const left = useRef(false);
  const onContinue = () => {
    if (left.current) return;
    left.current = true;
    track('onboarding_screen_completed', { screen: 'S22_success' });
    router.replace(signedOut ? '/save-plan' : '/(tabs)');
  };

  return (
    <OnbLayout progress={null} footer={<OnbButton label="Continue" onPress={onContinue} />}>
      <View style={{ flex: 0.8 }} />
      <HoppingMascot />
      <Text style={s.h1} accessibilityRole="header">
        You’re all set!
      </Text>
      <Text style={s.sub}>Premium is on. Here’s what you just unlocked.</Text>
      <View style={s.card}>
        {ROWS.map((r, i) => (
          <View key={r.text} style={[s.row, i < ROWS.length - 1 && s.rowLine]}>
            <Image source={r.icon} style={s.icon} />
            <Text style={s.rowText}>{r.text}</Text>
          </View>
        ))}
      </View>
      <View style={{ flex: 1, minHeight: 16 }} />
    </OnbLayout>
  );
}

const s = StyleSheet.create({
  circle: {
    alignSelf: 'center',
    width: 176,
    height: 176,
    borderRadius: 88,
    backgroundColor: C.terraSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Squash and stretch pivot at the feet, as on the canvas (transform-origin 50% 88%).
  mascotBox: { width: 166, height: 166, transformOrigin: '50% 88%' },
  mascot: { width: 166, height: 166 },
  h1: {
    marginTop: 24,
    textAlign: 'center',
    fontFamily: F.serif,
    fontSize: 34,
    lineHeight: 40,
    letterSpacing: -0.34,
    color: C.ink,
  },
  sub: { marginTop: 8, textAlign: 'center', fontFamily: F.sans, fontSize: 18, lineHeight: 27, color: C.muted },
  card: {
    marginTop: 24,
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.hair,
    borderRadius: 16,
    paddingVertical: 4,
    paddingHorizontal: 18,
  },
  row: { minHeight: 62, flexDirection: 'row', alignItems: 'center', gap: 14 },
  rowLine: { borderBottomWidth: 1, borderBottomColor: C.hair },
  icon: { width: 40, height: 40 },
  rowText: { flex: 1, fontFamily: F.sans, fontSize: 16, lineHeight: 22, color: C.ink },
});
