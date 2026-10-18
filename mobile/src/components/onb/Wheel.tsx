/**
 * V3 wheel picker (Age, Height & weight): 40 pt rows, a 56 pt centre slot,
 * neighbours fading 0.62 → 0.38 → 0.2 and shrinking 20 → 18 → 16 pt, the
 * selected value in Fraunces with a muted unit. A Taptic "selection" tick on
 * every value that passes the centre, like the system picker.
 *
 * Layout trick: rows sit on a 40 pt grid so snapping is a plain interval;
 * rows above / below the centre are pushed 8 pt apart to open the 56 pt slot.
 *
 * The selected value is drawn by a lens, like UIPickerView: an opaque window
 * over the slot holds its own column of big labels that moves exactly with the
 * rows next to the centre. A number is big inside the window and small outside
 * it, never both at once (a crossfade of the two read as a doubled digit). At
 * the window's edges the big number fades out before the small one fades in,
 * so a half big / half small number never shows either.
 */
import { memo, useCallback, useMemo, useRef } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';
import Animated, {
  runOnJS,
  scrollTo,
  useAnimatedRef,
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
/** Spacing of the lens labels: rows next to the centre move 48 pt per value. */
const SLOT = ROW + GAP;
/** The lens sits inside the band's 1 pt border. */
const INSET = 1;
/** Soft top and bottom edges inside the lens. */
const FADE = 12;

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

const Row = memo(function Row({ index, y, text }: { index: number; y: SharedValue<number>; text: string }) {
  const style = useAnimatedStyle(() => {
    const d = index - y.value / ROW;
    const a = Math.abs(d);
    // Hidden while any of it is under the lens; fades in once it has left.
    const opacity = a < 0.55 ? 0 : a < 1 ? ((a - 0.55) / 0.45) * 0.62 : a < 2 ? 0.62 - (a - 1) * 0.24 : a < 3 ? 0.38 - (a - 2) * 0.18 : 0.2;
    const size = a < 1 ? 20 : Math.max(16, 20 - (a - 1) * 2);
    return { opacity, transform: [{ translateY: Math.max(-1, Math.min(1, d)) * GAP }, { scale: size / 20 }] };
  });
  return (
    <Animated.View style={[s.row, style]}>
      <Text style={s.small}>{text}</Text>
    </Animated.View>
  );
});

function BigLabel({ label, bigSize }: { label: WheelLabel; bigSize: number }) {
  return (
    <View style={s.lensRow}>
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
    </View>
  );
}

function LensEdge({ at }: { at: 'top' | 'bottom' }) {
  const id = `wheelLens_${at}`;
  return (
    <Svg width="100%" height={FADE} style={[s.edge, at === 'top' ? { top: 0 } : { bottom: 0 }]}>
      <Defs>
        <LinearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={C.surface} stopOpacity={at === 'top' ? 1 : 0} />
          <Stop offset="1" stopColor={C.surface} stopOpacity={at === 'top' ? 0 : 1} />
        </LinearGradient>
      </Defs>
      <Rect x="0" y="0" width="100%" height="100%" fill={`url(#${id})`} />
    </Svg>
  );
}

const Lens = memo(function Lens({
  y,
  labels,
  bigSize,
  top,
}: {
  y: SharedValue<number>;
  labels: WheelLabel[];
  bigSize: number;
  top: number;
}) {
  const column = useAnimatedStyle(() => ({
    transform: [{ translateY: (CENTER - 2 * INSET - SLOT) / 2 - (y.value / ROW) * SLOT }],
  }));
  return (
    <View pointerEvents="none" style={[s.lens, { top: top + INSET }]}>
      <Animated.View style={column}>
        {labels.map((l, i) => (
          <BigLabel key={i} label={l} bigSize={bigSize} />
        ))}
      </Animated.View>
      <LensEdge at="top" />
      <LensEdge at="bottom" />
    </View>
  );
});

export function Wheel({ values, value, onChange, half, label, bigSize = 34, band = true, width }: Props) {
  const start = Math.max(0, values.indexOf(value));
  const y = useSharedValue(start * ROW);
  const lastIdx = useSharedValue(start);
  const height = half * 2 * ROW + CENTER;
  const pad = half * ROW + GAP;
  const committed = useRef(value);
  const ref = useAnimatedRef<Animated.ScrollView>();

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
        // Commit as the value passes the centre: a tap on Continue mid-fling
        // must submit what the wheel shows.
        runOnJS(commit)(idx);
      }
    },
    onMomentumEnd: (e) => {
      const idx = Math.round(e.contentOffset.y / ROW);
      // snapToInterval can leave a slow fling between rows; finish the snap.
      if (Math.abs(e.contentOffset.y - idx * ROW) > 0.5) scrollTo(ref, 0, idx * ROW, true);
      runOnJS(commit)(idx);
    },
    onEndDrag: (e) => {
      // A slow release without momentum never fires onMomentumEnd.
      if (Math.abs(e.velocity?.y ?? 0) < 0.3) {
        const idx = Math.round(e.contentOffset.y / ROW);
        scrollTo(ref, 0, idx * ROW, true);
        runOnJS(commit)(idx);
      }
    },
  });

  const labels = useMemo(() => values.map(label), [values, label]);

  return (
    <View style={{ height, width }}>
      {band ? <View pointerEvents="none" style={[s.band, { top: half * ROW }]} /> : null}
      <Animated.ScrollView
        ref={ref}
        onScroll={onScroll}
        scrollEventThrottle={16}
        showsVerticalScrollIndicator={false}
        snapToInterval={ROW}
        decelerationRate="fast"
        contentOffset={{ x: 0, y: start * ROW }}
        contentContainerStyle={{ paddingVertical: pad }}
      >
        {labels.map((l, i) => (
          <Row key={values[i]} index={i} y={y} text={plain(l)} />
        ))}
      </Animated.ScrollView>
      <Lens y={y} labels={labels} bigSize={bigSize} top={half * ROW} />
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
  lens: {
    position: 'absolute',
    left: INSET,
    right: INSET,
    height: CENTER - 2 * INSET,
    overflow: 'hidden',
    borderRadius: 14 - INSET,
    backgroundColor: C.surface,
  },
  lensRow: { height: SLOT, flexDirection: 'row', alignItems: 'center', justifyContent: 'center' },
  edge: { position: 'absolute', left: 0, right: 0 },
  big: { fontFamily: F.serif, lineHeight: 40, color: C.ink, fontVariant: ['tabular-nums'] },
  unit: { fontFamily: F.sans, fontSize: 15, color: C.muted, marginLeft: 6 },
});
