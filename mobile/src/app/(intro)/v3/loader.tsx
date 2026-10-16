/**
 * V3 screen 14 — Loader with ATT on top.
 *
 * With `att: "loader"` (default) the system ATT prompt opens over the loader at
 * 0 % and the progress only starts once it is answered (agreed 15 Oct;
 * AppsFlyer holds the install postback for up to 180 s). Then the four rows
 * tick off with the person's own numbers and the plan is saved to the draft.
 * The review card shows only when the arm turns it on and `onb_content` has a
 * review for this goal (demo reviews never ship).
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, {
  Easing,
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import Svg, { Circle, Path } from 'react-native-svg';
import * as Haptics from 'expo-haptics';
import { getTrackingPermissionsAsync } from 'expo-tracking-transparency';

import { requestTrackingConsent } from '@/analytics/attribution';
import { track } from '@/analytics/posthog';
import { OnbLayout } from '@/components/onb/OnbLayout';
import type { ContentGoal } from '@/config/types';
import { buildPlan } from '@/onb/buildPlan';
import { ACTIVITY_LABELS_V3 } from '@/onb/labels';
import { cmToFtIn, fmtKg, fmtStLb, formatShortDate } from '@/onb/plan';
import { C, F } from '@/onb/theme';
import { useOnbScreen } from '@/onb/useOnbScreen';


const DURATION_MS = 5200;
const ROW_DONE_AT = [22, 46, 72, 94];
const LINES: [number, string][] = [
  [0, 'Reading your answers…'],
  [24, 'Matching your activity…'],
  [48, 'Working out your calorie target…'],
  [74, 'Setting your goal date…'],
  [100, 'Your plan is ready'],
];

function Star() {
  return (
    <Svg width={14} height={14} viewBox="0 0 24 24">
      <Path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6-4.9-4.6 6.6-.8z" fill="#D9A441" />
    </Svg>
  );
}

function Spinner() {
  const r = useSharedValue(0);
  useEffect(() => {
    r.value = withRepeat(withTiming(360, { duration: 900, easing: Easing.linear }), -1, false);
    return () => cancelAnimation(r);
  }, [r]);
  const st = useAnimatedStyle(() => ({ transform: [{ rotate: `${r.value}deg` }] }));
  return (
    <Animated.View style={st}>
      <Svg width={22} height={22} viewBox="0 0 22 22" fill="none">
        <Circle cx={11} cy={11} r={9} stroke={C.hair} strokeWidth={2} />
        <Path d="M11 2a9 9 0 0 1 9 9" stroke={C.terra} strokeWidth={2} strokeLinecap="round" />
      </Svg>
    </Animated.View>
  );
}

function RowIcon({ state }: { state: 'done' | 'busy' | 'todo' }) {
  if (state === 'done') {
    return (
      <View style={s.done}>
        <Svg width={13} height={13} viewBox="0 0 24 24" fill="none">
          <Path d="M20 6 9 17l-5-5" stroke="#FFFFFF" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
        </Svg>
      </View>
    );
  }
  if (state === 'busy') return <Spinner />;
  return <View style={s.todo} />;
}

const GOAL_KEY: Record<string, ContentGoal> = { lose: 'lose', gain: 'gain', maintain: 'maintain', just_track: 'track' };

export default function LoaderScreen() {
  const { intro, config, content, next } = useOnbScreen('S14_loader');
  const [pct, setPct] = useState(0);
  const [started, setStarted] = useState(false);
  const finished = useRef(false);

  // Plan from the answers (also for paths without a Pace screen).
  const { patch, mode } = useMemo(() => buildPlan(intro), [intro]);

  // ATT first, progress after.
  useEffect(() => {
    let alive = true;
    void (async () => {
      if (config.att === 'loader') {
        const current = await getTrackingPermissionsAsync().catch(() => null);
        if (current?.status === 'undetermined' && current.canAskAgain) {
          track('att_prompt_shown', { source: 'v3_loader' });
          const granted = await requestTrackingConsent();
          track('att_prompt_answered', { granted, source: 'v3_loader' });
        }
      }
      if (alive) setStarted(true);
    })();
    return () => {
      alive = false;
    };
  }, [config.att]);

  useEffect(() => {
    if (!started) return;
    const t0 = Date.now();
    let lastRow = -1;
    const id = setInterval(() => {
      const p = Math.min(100, Math.round(((Date.now() - t0) / DURATION_MS) * 100));
      setPct(p);
      const row = ROW_DONE_AT.filter((x) => p >= x).length - 1;
      if (row > lastRow) {
        lastRow = row;
        void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
      }
      if (p >= 100 && !finished.current) {
        finished.current = true;
        clearInterval(id);
        void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
        setTimeout(() => next(patch, { plan_mode: mode }, { onb_plan_mode: mode }, { replace: true }), 450);
      }
    }, 50);
    return () => clearInterval(id);
  }, [started, next, patch, mode]);

  const imperial = intro.units === 'imperial';
  const ft = cmToFtIn(intro.height_cm);
  const bodyText = imperial
    ? `${ft.ft} ft ${ft.inch} in · ${fmtStLb(intro.weight_kg)}`
    : `${Math.round(intro.height_cm)} cm · ${fmtKg(intro.weight_kg)} kg`;
  const dateText = patch.target_date ? formatShortDate(patch.target_date) : 'Your zone';
  const rows = [
    { label: 'Your body', value: bodyText },
    { label: 'Activity', value: ACTIVITY_LABELS_V3[intro.activity_level ?? 'light'] },
    { label: 'Daily calories', value: `${(patch.target_calories ?? 0).toLocaleString('en-GB')} kcal` },
    { label: 'Your goal date', value: dateText },
  ];
  const line = [...LINES].reverse().find(([at]) => pct >= at)?.[1] ?? LINES[0][1];
  const review = config.loader_review ? content.loader_review[GOAL_KEY[intro.goal_type ?? 'lose']] : undefined;

  return (
    <OnbLayout progress={null}>
      <View style={{ flex: 0.7 }} />
      <Text style={s.pct}>{pct}%</Text>
      <Text style={s.h1}>Building your plan</Text>
      <View style={s.bar}>
        <View style={[s.fill, { width: `${pct}%` }]} />
      </View>
      <Text style={s.line}>{line}</Text>
      <View style={s.card}>
        {rows.map((r, i) => {
          const state = pct >= ROW_DONE_AT[i] ? 'done' : started && (i === 0 || pct >= ROW_DONE_AT[i - 1]) ? 'busy' : 'todo';
          const shown = state === 'done' ? r.value : state === 'busy' ? 'Calculating…' : '';
          return (
            <View key={r.label} style={[s.row, i < rows.length - 1 && s.rowLine]}>
              <RowIcon state={state} />
              <Text style={[s.rowLabel, state === 'todo' && s.faint]}>{r.label}</Text>
              <Text style={[s.rowValue, state === 'todo' && s.faint]}>{shown}</Text>
            </View>
          );
        })}
      </View>
      <View style={{ flex: 1 }} />
      {review ? (
        <View style={s.review}>
          <View style={s.stars}>
            {[0, 1, 2, 3, 4].map((i) => (
              <Star key={i} />
            ))}
          </View>
          <Text style={s.reviewText}>“{review.text}”</Text>
          <Text style={s.reviewName}>
            {review.name}
            {review.city ? `, ${review.city}` : ''}
          </Text>
        </View>
      ) : null}
    </OnbLayout>
  );
}

const s = StyleSheet.create({
  pct: { textAlign: 'center', fontFamily: F.serif, fontSize: 64, lineHeight: 68, color: C.ink, fontVariant: ['tabular-nums'] },
  h1: { marginTop: 6, textAlign: 'center', fontFamily: F.serif, fontSize: 30, lineHeight: 36, letterSpacing: -0.3, color: C.ink },
  bar: { marginTop: 24, height: 8, borderRadius: 4, backgroundColor: C.hair, overflow: 'hidden' },
  fill: { height: 8, borderRadius: 4, backgroundColor: C.terra },
  line: { marginTop: 12, textAlign: 'center', fontFamily: F.sans, fontSize: 15, lineHeight: 20, color: C.muted },
  card: {
    marginTop: 28,
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.hair,
    borderRadius: 16,
    paddingVertical: 4,
    paddingHorizontal: 18,
  },
  row: { height: 52, flexDirection: 'row', alignItems: 'center', gap: 12 },
  rowLine: { borderBottomWidth: 1, borderBottomColor: C.hair },
  rowLabel: { fontFamily: F.sans, fontSize: 16, lineHeight: 22, color: C.ink },
  rowValue: { marginLeft: 'auto', fontFamily: F.sans, fontSize: 15, lineHeight: 20, color: C.muted },
  faint: { color: C.faint },
  done: { width: 22, height: 22, borderRadius: 11, backgroundColor: C.terra, alignItems: 'center', justifyContent: 'center' },
  todo: { width: 22, height: 22, borderRadius: 11, borderWidth: 1.5, borderColor: C.hair2 },
  review: {
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.hair,
    borderRadius: 16,
    paddingVertical: 14,
    paddingHorizontal: 16,
  },
  stars: { flexDirection: 'row', gap: 2 },
  reviewText: { marginTop: 8, fontFamily: F.sans, fontSize: 15, lineHeight: 21, color: C.ink },
  reviewName: { marginTop: 6, fontFamily: F.sans, fontSize: 13, lineHeight: 18, color: C.muted },
});
