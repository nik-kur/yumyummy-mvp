/**
 * Pace slider (screen 7, Pace): 6 pt track, terracotta fill, 28 pt thumb with
 * a terracotta ring. Drag or tap; snaps to `steps`. Haptics: a light tick per
 * step, a firmer impact when the zone changes (Gentle → Recommended → Fast).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { runOnJS, useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';

import { C, SHADOW } from '@/onb/theme';

const THUMB = 28;

interface Props {
  steps: number[];
  index: number;
  onChange: (index: number) => void;
  /** Zone of a step; a change fires the firmer haptic. */
  zoneOf: (index: number) => string;
}

export function PaceSlider({ steps, index, onChange, zoneOf }: Props) {
  const [w, setW] = useState(0);
  const x = useSharedValue(0);
  const last = useRef(index);
  const n = steps.length - 1;

  useEffect(() => {
    if (w > 0) x.value = withTiming((index / n) * w, { duration: 120 });
  }, [index, n, w, x]);

  const step = useCallback(
    (i: number) => {
      if (i === last.current) return;
      const zoneChanged = zoneOf(i) !== zoneOf(last.current);
      last.current = i;
      if (zoneChanged) void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
      else void Haptics.selectionAsync().catch(() => {});
      onChange(i);
    },
    [onChange, zoneOf],
  );

  const toIndex = (px: number) => {
    'worklet';
    if (w <= 0) return 0;
    return Math.max(0, Math.min(n, Math.round((px / w) * n)));
  };

  const pan = Gesture.Pan()
    .minDistance(0)
    .onBegin((e) => {
      const i = toIndex(e.x - THUMB / 2);
      x.value = (i / n) * w;
      runOnJS(step)(i);
    })
    .onUpdate((e) => {
      const px = Math.max(0, Math.min(w, e.x - THUMB / 2));
      x.value = px;
      runOnJS(step)(toIndex(px));
    })
    .onFinalize(() => {
      x.value = withTiming((toIndex(x.value) / n) * w, { duration: 120 });
    });

  const thumb = useAnimatedStyle(() => ({ transform: [{ translateX: x.value }] }));
  const fill = useAnimatedStyle(() => ({ width: x.value + THUMB / 2 }));

  const onLayout = (e: LayoutChangeEvent) => {
    const width = e.nativeEvent.layout.width - THUMB;
    setW(width);
    x.value = (index / n) * width;
  };

  return (
    <GestureDetector gesture={pan}>
      <View style={s.wrap} onLayout={onLayout} hitSlop={{ top: 12, bottom: 12 }}>
        <View style={s.track} />
        <Animated.View style={[s.fill, fill]} />
        <Animated.View style={[s.thumb, SHADOW, thumb]} />
      </View>
    </GestureDetector>
  );
}

const s = StyleSheet.create({
  wrap: { height: THUMB, justifyContent: 'center' },
  track: { position: 'absolute', left: 0, right: 0, top: 11, height: 6, borderRadius: 3, backgroundColor: C.hair },
  fill: { position: 'absolute', left: 0, top: 11, height: 6, borderRadius: 3, backgroundColor: C.terra },
  thumb: {
    position: 'absolute',
    left: 0,
    top: 0,
    width: THUMB,
    height: THUMB,
    borderRadius: THUMB / 2,
    backgroundColor: C.surface,
    borderWidth: 2,
    borderColor: C.terra,
  },
});
