/**
 * V3 screen 25 — Payoff: once, after the tour, when Today has the first meal.
 * "Log like this for 3 days and you'll be on track to reach 66 kg by 31 Dec."
 * The goal line comes from the intro draft (kept on the device after
 * sign-in); without a dated weight goal the line speaks about the habit.
 */
import { useEffect, useRef, useState } from 'react';
import { Image, Modal, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

import { track } from '@/analytics/posthog';
import { OnbButton } from '@/components/onb/OnbButton';
import { IMG } from '@/onb/assets';
import { direction, fmtKg, fmtStLb, planMode } from '@/onb/plan';
import { C, F } from '@/onb/theme';
import { loadDraft, type IntroDraft } from '@/state/introDraft';

function goalLine(d: IntroDraft | null): string {
  const habit = 'Log like this for 3 days and it starts to feel automatic.';
  if (!d?.goal_type || !d.target_date) return habit;
  const target = d.target_weight_kg ?? d.weight_kg;
  const mode = planMode(d.goal_type, direction(d.weight_kg, target));
  if (mode !== 'lose' && mode !== 'cut' && mode !== 'gain') return habit;
  const date = new Date(`${d.target_date}T12:00:00`);
  if (date.getTime() < Date.now()) return habit;
  const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
  if (date.getTime() - Date.now() > 300 * 24 * 3600 * 1000) opts.year = 'numeric';
  const weight = d.units === 'imperial' ? fmtStLb(target) : `${fmtKg(target)} kg`;
  return `Log like this for 3 days and you’ll be on track to reach ${weight} by ${date.toLocaleDateString('en-GB', opts)}.`;
}

/** Canvas `yy-bob`, 2.6 s: up 7 pt with a −2° tilt and back. */
function BobbingMascot() {
  const t = useSharedValue(0);
  useEffect(() => {
    const e = Easing.inOut(Easing.ease);
    t.value = withRepeat(withSequence(withTiming(1, { duration: 1300, easing: e }), withTiming(0, { duration: 1300, easing: e })), -1);
    return () => cancelAnimation(t);
  }, [t]);
  const style = useAnimatedStyle(() => ({
    transform: [{ translateY: -7 * t.value }, { rotate: `${-2 * t.value}deg` }],
  }));
  return (
    <Animated.View style={[s.mascotBox, style]}>
      <Image source={IMG.mascot_great} style={s.mascot} accessibilityLabel="YumYummy peach mascot giving a thumbs up" />
    </Animated.View>
  );
}

export function PayoffSheet({ visible, onDone }: { visible: boolean; onDone: () => void }) {
  const insets = useSafeAreaInsets();
  const [draft, setDraft] = useState<IntroDraft | null>(null);
  const viewed = useRef(false);
  useEffect(() => {
    if (!visible) return;
    loadDraft().then(setDraft).catch(() => {});
    if (!viewed.current) {
      viewed.current = true;
      track('onboarding_screen_viewed', { screen: 'S25_payoff' });
    }
  }, [visible]);

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onDone}>
      <View style={s.dim}>
        <View style={[s.sheet, { paddingBottom: Math.max(insets.bottom, 20) }]}>
          <BobbingMascot />
          <Text style={s.h1} accessibilityRole="header">
            That’s your first log!
          </Text>
          <Text style={s.body}>{goalLine(draft)}</Text>
          <OnbButton label="Got it" onPress={onDone} style={{ marginTop: 24 }} />
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  dim: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(20,16,12,0.45)' },
  sheet: {
    backgroundColor: C.surface,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingTop: 26,
    paddingHorizontal: 24,
  },
  mascotBox: { alignSelf: 'center', width: 104, height: 104, transformOrigin: '50% 88%' },
  mascot: { width: 104, height: 104 },
  h1: {
    marginTop: 10,
    textAlign: 'center',
    fontFamily: F.serif,
    fontSize: 28,
    lineHeight: 34,
    letterSpacing: -0.28,
    color: C.ink,
  },
  body: { marginTop: 8, textAlign: 'center', fontFamily: F.sans, fontSize: 17, lineHeight: 25, color: C.muted },
});
