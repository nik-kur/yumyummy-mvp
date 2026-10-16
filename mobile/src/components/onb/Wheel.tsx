/**
 * V3 wheel picker (Age, Height & weight): 40 pt rows, a 56 pt centre slot,
 * neighbours fading 0.62 → 0.38 → 0.2 and shrinking 20 → 18 → 16 pt, the
 * selected value in Fraunces with a muted unit. A Taptic "selection" tick on
 * every value that passes the centre, like the system picker.
 *
 * Layout trick: rows sit on a 40 pt grid so snapping is a plain interval;
 * rows above / below the centre are pushed 8 pt apart to open the 56 pt slot.
 */
import { memo, useCallback, useMemo, useRef } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Animated, {
  runOnJS,
  useAnimatedScrollHandler,
  useAnimatedStyle,
  useSharedValue,
  type SharedValue,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';

import { C, F } from '@/onb/theme';

export const ROW = 40;
const CENTER = 56;
const GAP = (CENTER - ROW) / 2;

/** How one value reads: big parts in Fraunces, units in small muted Inter. */
export type WheelLabel = { text: string; unit?: boolean }[];

interface Props {
  values: number[];
  value: number;
  onChange: (v: number) => void;
  /** Rows visible on each side of the centre (Age 3, Height & weight 2). */
  half: number;
  label: (v: number) => WheelLabel;
  /** Size of the selected number (Age 34, Body 30). */
  bigSize?: number;
  /** Draw the centre band (Body draws one band across both wheels). */
  band?: boolean;
  width?: number;
}

function plain(label: WheelLabel): string {
  return label.map((p) => p.text).join(' ');
}

const Row = memo(function Row({
  index,
  y,
  label,
  bigSize,
}: {
  index: number;
  y: SharedValue<number>;
  label: WheelLabel;
  bigSize: number;
}) {
  const wrap = useAnimatedStyle(() => {
    const d = index - y.value / ROW;
    const shift = Math.max(-1, Math.min(1, d)) * GAP;
    return { transform: [{ translateY: shift }] };
  });
  const small = useAnimatedStyle(() => {
    const a = Math.abs(index - y.value / ROW);
    const opacity = a < 1 ? a * 0.62 : a < 2 ? 0.62 - (a - 1) * 0.24 : a < 3 ? 0.38 - (a - 2) * 0.18 : 0.2;
    const size = a < 1 ? 20 : Math.max(16, 20 - (a - 1) * 2);
    return { opacity, transform: [{ scale: size / 20 }] };
  });
  const big = useAnimatedStyle(() => {
    const a = Math.abs(index - y.value / ROW);
    return { opacity: Math.max(0, 1 - a * 1.6) };
  });
  return (
    <Animated.View style={[s.row, wrap]}>
      <Animated.Text style={[s.small, small]}>{plain(label)}</Animated.Text>
      <Animated.View style={[s.bigWrap, big]} pointerEvents="none">
        {label.map((p, i) =>
          p.unit ? (
            <Text key={i} style={s.unit}>
              {p.text}
            </Text>
          ) : (
            <Text key={i} style={[s.big, { fontSize: bigSize }, i > 0 && { marginLeft: 6 }]}>
              {p.text}
            </Text>
          ),
        )}
      </Animated.View>
    </Animated.View>
  );
});

export function Wheel({ values, value, onChange, half, label, bigSize = 34, band = true, width }: Props) {
  const start = Math.max(0, values.indexOf(value));
  const y = useSharedValue(start * ROW);
  const lastIdx = useSharedValue(start);
  const height = half * 2 * ROW + CENTER;
  const pad = half * ROW + GAP;
  const committed = useRef(value);

  const tick = useCallback(() => {
    void Haptics.selectionAsync().catch(() => {});
  }, []);

  const commit = useCallback(
    (idx: number) => {
      const v = values[Math.max(0, Math.min(values.length - 1, idx))];
      if (v !== undefined && v !== committed.current) {
        committed.current = v;
        onChange(v);
      }
    },
    [onChange, values],
  );

  const onScroll = useAnimatedScrollHandler({
    onScroll: (e) => {
      y.value = e.contentOffset.y;
      const idx = Math.round(e.contentOffset.y / ROW);
      if (idx !== lastIdx.value && idx >= 0 && idx < values.length) {
        lastIdx.value = idx;
        runOnJS(tick)();
      }
    },
    onMomentumEnd: (e) => {
      runOnJS(commit)(Math.round(e.contentOffset.y / ROW));
    },
    onEndDrag: (e) => {
      // A slow release without momentum never fires onMomentumEnd.
      if (Math.abs(e.velocity?.y ?? 0) < 0.05) runOnJS(commit)(Math.round(e.contentOffset.y / ROW));
    },
  });

  const labels = useMemo(() => values.map(label), [values, label]);

  return (
    <View style={{ height, width }}>
      {band ? <View pointerEvents="none" style={[s.band, { top: half * ROW }]} /> : null}
      <Animated.ScrollView
        onScroll={onScroll}
        scrollEventThrottle={16}
        showsVerticalScrollIndicator={false}
        snapToInterval={ROW}
        decelerationRate="fast"
        contentOffset={{ x: 0, y: start * ROW }}
        contentContainerStyle={{ paddingVertical: pad }}
      >
        {labels.map((l, i) => (
          <Row key={values[i]} index={i} y={y} label={l} bigSize={bigSize} />
        ))}
      </Animated.ScrollView>
    </View>
  );
}

/** The 56 pt centre band, for screens that draw one across several wheels. */
export function WheelBand({ top }: { top: number }) {
  return <View pointerEvents="none" style={[s.band, { top }]} />;
}

const s = StyleSheet.create({
  band: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: CENTER,
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.hair,
    borderRadius: 14,
  },
  row: { height: ROW, alignItems: 'center', justifyContent: 'center' },
  small: { fontFamily: F.sans, fontSize: 20, color: C.ink, fontVariant: ['tabular-nums'] },
  bigWrap: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: -8,
    bottom: -8,
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'center',
    paddingTop: 8,
  },
  big: { fontFamily: F.serif, lineHeight: 40, color: C.ink, fontVariant: ['tabular-nums'] },
  unit: { fontFamily: F.sans, fontSize: 15, color: C.muted, marginLeft: 6 },
});
