/**
 * The post-purchase tour (V3 screen 24, artboards Tour_1–6): the app is dimmed,
 * one real element is cut out with a white ring, and a card explains it.
 *
 * Elements register with `useTourTarget(id)` wherever they are drawn; the
 * overlay measures them in window coordinates a few times a second, so it
 * follows scrolling, the keyboard and late layout. Two scopes:
 *   - `tabs`: over Today and the tab bar (steps 1, 2, 4, 5, 6); touches are
 *     blocked except the card and, on step 2, the "+" itself;
 *   - `capture`: inside the capture screen (step 3); a light dim that lets the
 *     person type, with the card over the input bar.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { useRouter } from 'expo-router';
import * as Haptics from 'expo-haptics';
import Animated, {
  cancelAnimation,
  Easing,
  FadeIn,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';
import Svg, { Circle, Path, Rect } from 'react-native-svg';

import { track } from '@/analytics/posthog';
import { C, F, SHADOW } from '@/onb/theme';
import { nextTourStep, setTourStep, useTour, type TourStep } from '@/state/tour';

export type TourTargetId =
  | 'dashboard'
  | 'plus'
  | 'capture_bar'
  | 'capture_extras'
  | 'first_meal'
  | 'tabbar'
  | 'journey';

const nodes = new Map<TourTargetId, View>();

/** Ref callback for the element a tour step points at. */
export function useTourTarget(id: TourTargetId) {
  const own = useRef<View | null>(null);
  return useCallback(
    (node: View | null) => {
      if (node) {
        own.current = node;
        nodes.set(id, node);
      } else {
        // Forget only our own element: another copy of the screen may have
        // registered the live one under the same id meanwhile.
        if (own.current && nodes.get(id) === own.current) nodes.delete(id);
        own.current = null;
      }
    },
    [id],
  );
}

interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function measureTourTarget(id: TourTargetId): Promise<Box | null> {
  const node = nodes.get(id);
  if (!node) return Promise.resolve(null);
  return new Promise((resolve) => {
    try {
      node.measureInWindow((x, y, w, h) => resolve(w > 0 && h > 0 ? { x, y, w, h } : null));
    } catch {
      resolve(null);
    }
  });
}

interface StepDef {
  target: TourTargetId;
  scope: 'tabs' | 'capture';
  title: string;
  body: string;
  /** Button on the card; none = the step waits for an action in the app. */
  cta: string | null;
  pad: number;
  radius: number;
  circle?: boolean;
  dim: number;
  /** Give up and move on if the element never shows up (it is optional). */
  optional?: boolean;
  /** Card above the element (the "+", the keyboard-docked capture bar, the tab bar). */
  above?: boolean;
  /** Also keep the card above this element when it is on screen (capture's example chips, photos). */
  aboveToo?: TourTargetId;
}

const STEPS: Record<TourStep, StepDef> = {
  1: {
    target: 'dashboard',
    scope: 'tabs',
    title: 'This is your dashboard',
    body: 'Calories, protein, fat and carbs for today fill up here as you log.',
    cta: 'Next',
    pad: 4,
    radius: 20,
    dim: 0.58,
    optional: true,
  },
  2: {
    target: 'plus',
    scope: 'tabs',
    title: 'Log your first meal',
    body: 'Tap + and tell us what you just ate.',
    cta: null,
    pad: 3,
    radius: 32,
    circle: true,
    dim: 0.58,
    above: true,
  },
  3: {
    target: 'capture_bar',
    scope: 'capture',
    title: 'Type it, say it or snap it',
    body: 'Write it like a text to a friend, then tap Analyze.',
    cta: null,
    pad: 8,
    radius: 16,
    dim: 0.3,
    above: true,
    aboveToo: 'capture_extras',
  },
  4: {
    target: 'first_meal',
    scope: 'tabs',
    title: 'Your first meal is in',
    body: 'Tap it any time to see where each number came from.',
    cta: 'Next',
    pad: 4,
    radius: 18,
    dim: 0.58,
  },
  5: {
    target: 'tabbar',
    scope: 'tabs',
    title: 'Your week and your menu',
    body: 'Week shows your trends, and My Menu saves meals you eat often.',
    cta: 'Next',
    pad: -8,
    radius: 16,
    dim: 0.58,
    optional: true,
    above: true,
  },
  6: {
    target: 'journey',
    scope: 'tabs',
    title: 'Your first week',
    body: 'One small quest a day helps the habit stick.',
    cta: 'Got it',
    pad: 4,
    radius: 18,
    dim: 0.58,
    optional: true,
  },
};

const POLL_MS = 200;
const GIVE_UP_MS = 4000;

/** Dim everything but a rounded hole; a 3 pt paper ring hugs the hole. */
function Spotlight({ hole, width, height, dim, radius }: { hole: Box; width: number; height: number; dim: number; radius: number }) {
  const r = Math.min(radius, hole.w / 2, hole.h / 2);
  const { x, y, w, h } = hole;
  const d =
    `M0 0H${width}V${height}H0Z ` +
    `M${x + r} ${y}H${x + w - r}A${r} ${r} 0 0 1 ${x + w} ${y + r}V${y + h - r}A${r} ${r} 0 0 1 ${x + w - r} ${y + h}` +
    `H${x + r}A${r} ${r} 0 0 1 ${x} ${y + h - r}V${y + r}A${r} ${r} 0 0 1 ${x + r} ${y}Z`;
  // react-native-svg ignores `pointerEvents` on iOS: the wrapping View is what
  // lets touches through to the app (the capture bar on step 3).
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none">
    <Svg width={width} height={height} style={StyleSheet.absoluteFill}>
      <Path d={d} fill={`rgba(20,16,12,${dim})`} fillRule="evenodd" />
      <Rect
        x={x - 1.5}
        y={y - 1.5}
        width={w + 3}
        height={h + 3}
        rx={r + 1.5}
        stroke="rgba(255,253,249,0.9)"
        strokeWidth={3}
        fill="none"
      />
    </Svg>
    </View>
  );
}

/** Step 2: the white arrow floating above "+" (canvas `yy-float`). */
interface Pt {
  x: number;
  y: number;
}

/**
 * Arrow from the tip card to the element it explains: a dot on the card's
 * edge, an S-curve, an arrowhead on the element. It nudges towards the
 * element, so it is clear what points where.
 */
function ConnectorArrow({ from, to }: { from: Pt; to: Pt }) {
  const t = useSharedValue(0);
  useEffect(() => {
    const e = Easing.inOut(Easing.ease);
    t.value = withRepeat(withSequence(withTiming(1, { duration: 800, easing: e }), withTiming(0, { duration: 800, easing: e })), -1);
    return () => cancelAnimation(t);
  }, [t]);
  const dir = to.y > from.y ? 1 : -1;
  const style = useAnimatedStyle(() => ({ transform: [{ translateY: dir * 3 * t.value }] }));
  const pad = 10;
  const left = Math.min(from.x, to.x) - pad;
  const top = Math.min(from.y, to.y) - pad;
  const w = Math.abs(to.x - from.x) + pad * 2;
  const h = Math.abs(to.y - from.y) + pad * 2;
  const sx = from.x - left;
  const sy = from.y - top;
  const ex = to.x - left;
  const ey = to.y - top;
  const my = (sy + ey) / 2;
  return (
    <Animated.View style={[{ position: 'absolute', left, top, width: w, height: h }, style]} pointerEvents="none">
      <Svg width={w} height={h}>
        <Circle cx={sx} cy={sy} r={3.5} fill="#FFFFFF" />
        <Path d={`M${sx} ${sy}C${sx} ${my} ${ex} ${my} ${ex} ${ey}`} stroke="#FFFFFF" strokeWidth={2.2} strokeLinecap="round" fill="none" />
        <Path
          d={`M${ex - 6} ${ey - 8 * dir}L${ex} ${ey}L${ex + 6} ${ey - 8 * dir}`}
          stroke="#FFFFFF"
          strokeWidth={2.2}
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        />
      </Svg>
    </Animated.View>
  );
}

function FloatingArrow({ x, y }: { x: number; y: number }) {
  const t = useSharedValue(0);
  useEffect(() => {
    const e = Easing.inOut(Easing.ease);
    t.value = withRepeat(withSequence(withTiming(-8, { duration: 1600, easing: e }), withTiming(0, { duration: 1600, easing: e })), -1);
    return () => cancelAnimation(t);
  }, [t]);
  const style = useAnimatedStyle(() => ({ transform: [{ translateY: t.value }] }));
  return (
    <Animated.View style={[{ position: 'absolute', left: x - 12, top: y - 44, width: 24, height: 40 }, style]} pointerEvents="none">
      <Svg width={24} height={40} viewBox="0 0 24 40" fill="none">
        <Path d="M12 2V34M4 26l8 8 8-8" stroke="#FFFFFF" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" />
      </Svg>
    </Animated.View>
  );
}

/** Where the arrow(s) of a step land on the element (x in window points). */
function arrowTargets(target: TourTargetId, hole: Box, width: number): number[] {
  if (target === 'tabbar') {
    // My Menu and Week: the bar is Today | My Menu | + (72 pt) | Week | Profile.
    const tab = (width - 16 - 72) / 4;
    return [8 + tab * 1.5, width - 8 - tab * 1.5];
  }
  if (target === 'dashboard') return [hole.x + hole.w / 2];
  return [hole.x + hole.w * 0.32];
}

export function TourOverlay({ scope }: { scope: 'tabs' | 'capture' }) {
  const tour = useTour();
  const router = useRouter();
  const { width, height } = useWindowDimensions();
  const rootRef = useRef<View>(null);
  const [hole, setHole] = useState<Box | null>(null);
  const [ceiling, setCeiling] = useState<number | null>(null);
  const [cardH, setCardH] = useState(0);
  const active = tour.status === 'active' && STEPS[tour.step].scope === scope;
  const def = STEPS[tour.step];

  // Follow the target while the step is on screen.
  useEffect(() => {
    if (!active) {
      setHole(null);
      return;
    }
    let alive = true;
    const startedAt = Date.now();
    let seen = false;
    const tick = async () => {
      const [rect, origin, extra] = await Promise.all([
        measureTourTarget(def.target),
        new Promise<{ x: number; y: number }>((resolve) => {
          const n = rootRef.current;
          if (!n) return resolve({ x: 0, y: 0 });
          n.measureInWindow((x, y) => resolve({ x, y }));
        }),
        def.aboveToo ? measureTourTarget(def.aboveToo) : Promise.resolve(null),
      ]);
      if (!alive) return;
      setCeiling(extra ? extra.y - origin.y : null);
      if (rect) {
        seen = true;
        const pad = def.pad;
        const next =
          pad < 0
            ? { x: rect.x - origin.x - pad, y: rect.y - origin.y, w: rect.w + 2 * pad, h: rect.h }
            : { x: rect.x - origin.x - pad, y: rect.y - origin.y - pad, w: rect.w + 2 * pad, h: rect.h + 2 * pad };
        setHole((h) =>
          h && Math.abs(h.x - next.x) < 0.5 && Math.abs(h.y - next.y) < 0.5 && Math.abs(h.w - next.w) < 0.5 && Math.abs(h.h - next.h) < 0.5
            ? h
            : next,
        );
      } else {
        setHole(null);
        if (!seen && def.optional && Date.now() - startedAt > GIVE_UP_MS) {
          track('tour_step_unavailable', { step: tour.step });
          void nextTourStep();
        }
      }
    };
    void tick();
    const id = setInterval(() => void tick(), POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [active, def, tour.step]);

  // Once per step, not every time the element blinks out and back.
  const shown = active && hole !== null;
  const tracked = useRef(0);
  useEffect(() => {
    if (shown && tracked.current !== tour.step) {
      tracked.current = tour.step;
      track('tour_step_viewed', { step: tour.step });
    }
  }, [shown, tour.step]);

  if (!active) return null;

  const onNext = () => {
    void Haptics.selectionAsync().catch(() => {});
    void nextTourStep();
  };
  const onPlus = () => {
    void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    void setTourStep(3);
    router.push('/capture');
  };

  // Card below the hole when it fits above the bottom, otherwise above it,
  // with room for the arrow between them (step 3 has no arrow: the example
  // chips sit there).
  let cardTop = 0;
  let cardBelow = false;
  const curved = def.target !== 'plus' && def.target !== 'capture_bar';
  if (hole) {
    const gap = curved ? 46 : 18;
    const below = hole.y + hole.h + gap;
    const roof = ceiling !== null && ceiling < hole.y ? ceiling : hole.y;
    const above = roof - (def.circle ? 58 : gap) - cardH;
    // Below the element if the card clears the tab bar there (squeezing the
    // arrow gap a little rather than covering the element from above).
    const floor = height - (scope === 'tabs' ? 92 : 40);
    const squeezed = Math.min(below, floor - cardH);
    cardBelow = !def.above && squeezed >= hole.y + hole.h + (curved ? 34 : 12);
    cardTop = cardBelow ? squeezed : Math.max(56, above);
  }

  // The app is blocked only while a step is actually on screen: a step still
  // waiting for its element (the meal is analysing) must leave the app usable.
  const blocking = scope === 'tabs' && hole !== null;
  return (
    <View
      ref={rootRef}
      style={StyleSheet.absoluteFill}
      pointerEvents={blocking ? 'auto' : 'box-none'}
      onStartShouldSetResponder={() => blocking}
    >
      {hole ? (
        <Animated.View
          key={tour.step}
          entering={FadeIn.duration(200)}
          style={StyleSheet.absoluteFill}
          pointerEvents="box-none"
          accessibilityViewIsModal={scope === 'tabs'}
        >
          <Spotlight hole={hole} width={width} height={height} dim={def.dim} radius={def.circle ? hole.w / 2 : def.radius} />
          {curved && cardH > 0
            ? arrowTargets(def.target, hole, width).map((ex, i) => {
                const edge = cardBelow ? cardTop - 3 : cardTop + cardH + 3;
                const end = cardBelow ? hole.y + hole.h + 5 : hole.y - 5;
                // Start on the card a little towards its middle, so the curve reads.
                const sx = Math.min(width - 48, Math.max(48, ex + (ex < width / 2 ? 48 : -48)));
                return <ConnectorArrow key={i} from={{ x: sx, y: edge }} to={{ x: ex, y: end }} />;
              })
            : null}
          {def.target === 'plus' ? (
            <>
              <FloatingArrow x={hole.x + hole.w / 2} y={hole.y} />
              <Pressable
                onPress={onPlus}
                style={{ position: 'absolute', left: hole.x, top: hole.y, width: hole.w, height: hole.h, borderRadius: hole.w / 2 }}
                accessibilityRole="button"
                accessibilityLabel="Log a meal"
              />
            </>
          ) : null}
          <View
            style={[s.card, SHADOW, { top: cardTop, opacity: cardH > 0 ? 1 : 0 }]}
            onLayout={(e) => setCardH(e.nativeEvent.layout.height)}
            pointerEvents="auto"
          >
            <Text style={s.title} accessibilityRole="header">
              {def.title}
            </Text>
            <Text style={s.body}>{def.body}</Text>
            <View style={s.footer}>
              <Text style={s.count}>{tour.step} of 6</Text>
              <View style={s.actions}>
                {def.cta ? (
                  <Pressable onPress={onNext} style={({ pressed }) => [s.next, pressed && { opacity: 0.85 }]} accessibilityRole="button">
                    <Text style={s.nextText}>{def.cta}</Text>
                  </Pressable>
                ) : null}
              </View>
            </View>
          </View>
        </Animated.View>
      ) : null}
    </View>
  );
}

const s = StyleSheet.create({
  // Olive (the protein colour) with white text: clearly a tip, not one of
  // the app's own cream cards, and softer than black.
  card: {
    position: 'absolute',
    left: 20,
    right: 20,
    paddingVertical: 16,
    paddingHorizontal: 18,
    backgroundColor: C.protein,
    borderRadius: 16,
  },
  title: { fontFamily: F.sansSemibold, fontSize: 17, lineHeight: 22, color: C.white },
  body: { marginTop: 4, fontFamily: F.sans, fontSize: 15, lineHeight: 21, color: 'rgba(255,255,255,0.86)' },
  footer: { marginTop: 14, height: 36, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  count: { fontFamily: F.sans, fontSize: 13, color: 'rgba(255,255,255,0.62)' },
  actions: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  next: { height: 36, paddingHorizontal: 16, borderRadius: 10, backgroundColor: C.paper, alignItems: 'center', justifyContent: 'center' },
  nextText: { fontFamily: F.sansSemibold, fontSize: 14, color: C.protein },
});
