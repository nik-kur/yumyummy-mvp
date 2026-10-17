/**
 * Horizontal weight ruler (screen 7): a minor tick every step (0.2 kg / 1 lb),
 * a labelled major tick every whole unit (1 kg / 1 st), the terracotta centre
 * marker and a soft band between the centre and today's weight. Haptics: a
 * light tick per step, a firmer one on each whole unit.
 *
 * Canvas geometry: 342 × 86, 12 pt per step, minor ticks y 40–56, major
 * 28–56, labels at y 78 (Inter 13), band y 22–60, marker y 12–62.
 */
import { memo, useCallback, useMemo, useRef } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  runOnJS,
  scrollTo,
  useAnimatedRef,
  useAnimatedScrollHandler,
  useAnimatedStyle,
  useSharedValue,
} from 'react-native-reanimated';
import Svg, { Path, Text as SvgText } from 'react-native-svg';
import * as Haptics from 'expo-haptics';

import { C, F } from '@/onb/theme';

const STEP_PX = 12;
const H = 86;

interface Props {
  /** Number of steps (ticks) from `min`. */
  count: number;
  /** Index of the selected tick. */
  index: number;
  /** Index of today's weight (the band runs from it to the centre). */
  currentIndex: number;
  /** Ticks per labelled unit (5 for 0.2 kg, 14 for lb → st). */
  perMajor: number;
  /** Label for a major tick. */
  majorLabel: (index: number) => string;
  onChange: (index: number) => void;
  width: number;
}

/** Ticks per SVG chunk: one huge SVG can exceed the 16k px texture limit at @3x. */
const CHUNK = 60;

const Ticks = memo(function Ticks({
  count,
  perMajor,
  majorLabel,
  pad,
}: {
  count: number;
  perMajor: number;
  majorLabel: (i: number) => string;
  pad: number;
}) {
  const chunks: { left: number; width: number; minor: string; major: string; labels: { x: number; t: string }[] }[] = [];
  for (let start = 0; start < count; start += CHUNK) {
    const end = Math.min(count, start + CHUNK);
    // Each chunk is its own coordinate space starting half a step left of its first tick.
    const left = pad + start * STEP_PX - STEP_PX / 2;
    const minor: string[] = [];
    const major: string[] = [];
    const labels: { x: number; t: string }[] = [];
    for (let i = start; i < end; i += 1) {
      const x = pad + i * STEP_PX - left;
      if (i % perMajor === 0) {
        major.push(`M${x} 28 V56`);
        labels.push({ x, t: majorLabel(i) });
      } else {
        minor.push(`M${x} 40 V56`);
      }
    }
    chunks.push({ left, width: (end - start) * STEP_PX, minor: minor.join(' '), major: major.join(' '), labels });
  }
  return (
    <View style={{ width: pad * 2 + (count - 1) * STEP_PX, height: H }}>
      {chunks.map((c) => (
        <Svg key={c.left} width={c.width + 24} height={H} style={{ position: 'absolute', left: c.left }}>
          {c.minor ? <Path d={c.minor} stroke={C.hair2} strokeWidth={1.5} strokeLinecap="round" /> : null}
          {c.major ? <Path d={c.major} stroke={C.faint} strokeWidth={2} strokeLinecap="round" /> : null}
          {c.labels.map((l) => (
            <SvgText key={l.x} x={l.x} y={78} textAnchor="middle" fontFamily={F.sans} fontSize={13} fill={C.muted}>
              {l.t}
            </SvgText>
          ))}
        </Svg>
      ))}
    </View>
  );
});

export function Ruler({ count, index, currentIndex, perMajor, majorLabel, onChange, width }: Props) {
  const pad = width / 2;
  const x = useSharedValue(index * STEP_PX);
  const last = useSharedValue(index);
  const reported = useRef(index);
  const ref = useAnimatedRef<Animated.ScrollView>();

  const onStep = useCallback(
    (i: number) => {
      if (i % perMajor === 0) void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
      else void Haptics.selectionAsync().catch(() => {});
      if (i !== reported.current) {
        reported.current = i;
        onChange(i);
      }
    },
    [onChange, perMajor],
  );

  const onScroll = useAnimatedScrollHandler({
    onScroll: (e) => {
      x.value = e.contentOffset.x;
      const i = Math.round(e.contentOffset.x / STEP_PX);
      if (i !== last.value && i >= 0 && i < count) {
        last.value = i;
        runOnJS(onStep)(i);
      }
    },
    onEndDrag: (e) => {
      if (Math.abs(e.velocity?.x ?? 0) < 0.3) {
        scrollTo(ref, Math.round(e.contentOffset.x / STEP_PX) * STEP_PX, 0, true);
      }
    },
    onMomentumEnd: (e) => {
      const i = Math.round(e.contentOffset.x / STEP_PX);
      if (Math.abs(e.contentOffset.x - i * STEP_PX) > 0.5) scrollTo(ref, i * STEP_PX, 0, true);
    },
  });

  const curX = pad + currentIndex * STEP_PX;
  const band = useAnimatedStyle(() => {
    const centre = x.value + pad;
    return { left: Math.min(curX, centre), width: Math.abs(curX - centre) };
  });

  const ticks = useMemo(
    () => <Ticks count={count} perMajor={perMajor} majorLabel={majorLabel} pad={pad} />,
    [count, perMajor, majorLabel, pad],
  );

  return (
    <View style={{ width, height: H }}>
      <Animated.ScrollView
        ref={ref}
        horizontal
        onScroll={onScroll}
        scrollEventThrottle={16}
        showsHorizontalScrollIndicator={false}
        snapToInterval={STEP_PX}
        decelerationRate="fast"
        contentOffset={{ x: index * STEP_PX, y: 0 }}
      >
        <View>
          <Animated.View style={[s.band, band]} />
          {ticks}
        </View>
      </Animated.ScrollView>
      <View pointerEvents="none" style={[s.marker, { left: pad - 1.5 }]} />
    </View>
  );
}

const s = StyleSheet.create({
  band: { position: 'absolute', top: 22, height: 38, backgroundColor: C.terraSoft },
  marker: { position: 'absolute', top: 12, width: 3, height: 50, borderRadius: 1.5, backgroundColor: C.terra },
});
