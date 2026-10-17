/**
 * Sticker images with the canvas's looping micro-animations (`yy-bob`,
 * `yy-hop`, `yy-beat`, `yy-ring`, `yy-float`), transform-origin 50 % 88 %.
 * Static when the system asks for reduced motion.
 */
import { useEffect, useState } from 'react';
import { AccessibilityInfo, type ImageSourcePropType, type ImageStyle, type StyleProp } from 'react-native';
import Animated, {
  Easing,
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

export type StickerMotion = 'bob' | 'hop' | 'beat' | 'ring' | 'float' | 'none';

const DURATION: Record<Exclude<StickerMotion, 'none'>, number> = {
  bob: 2600,
  hop: 1500,
  beat: 1800,
  ring: 2800,
  float: 3200,
};

/** Piecewise-linear keyframes on t ∈ [0, 1] (worklet). */
function kf(t: number, stops: [number, number][]): number {
  'worklet';
  for (let i = 1; i < stops.length; i += 1) {
    const [t1, v1] = stops[i];
    const [t0, v0] = stops[i - 1];
    if (t <= t1) {
      const k = t1 === t0 ? 1 : (t - t0) / (t1 - t0);
      // ease-in-out between keyframes, as CSS `ease-in-out` per segment
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      return v0 + (v1 - v0) * e;
    }
  }
  return stops[stops.length - 1][1];
}

export function Sticker({
  source,
  size,
  motion = 'none',
  style,
}: {
  source: ImageSourcePropType;
  size: number;
  motion?: StickerMotion;
  style?: StyleProp<ImageStyle>;
}) {
  const t = useSharedValue(0);
  const [reduce, setReduce] = useState(false);

  useEffect(() => {
    void AccessibilityInfo.isReduceMotionEnabled().then(setReduce).catch(() => {});
  }, []);

  useEffect(() => {
    if (motion === 'none' || reduce) return;
    t.value = 0;
    t.value = withRepeat(withTiming(1, { duration: DURATION[motion], easing: Easing.linear }), -1, false);
    return () => cancelAnimation(t);
  }, [motion, reduce, t]);

  const anim = useAnimatedStyle(() => {
    const v = t.value;
    switch (motion) {
      case 'bob':
        return {
          transform: [
            { translateY: kf(v, [[0, 0], [0.5, -7], [1, 0]]) },
            { rotate: `${kf(v, [[0, 0], [0.5, -2], [1, 0]])}deg` },
          ],
        };
      case 'hop':
        return {
          transform: [
            { translateY: kf(v, [[0, 0], [0.12, 0], [0.4, -20], [0.62, 0], [0.78, 0], [1, 0]]) },
            { scaleX: kf(v, [[0, 1], [0.12, 1.05], [0.4, 0.97], [0.62, 1.04], [0.78, 1], [1, 1]]) },
            { scaleY: kf(v, [[0, 1], [0.12, 0.95], [0.4, 1.04], [0.62, 0.96], [0.78, 1], [1, 1]]) },
          ],
        };
      case 'beat':
        return {
          transform: [{ scale: kf(v, [[0, 1], [0.14, 1.06], [0.28, 1], [0.42, 1.045], [0.7, 1], [1, 1]]) }],
        };
      case 'ring':
        return {
          transform: [
            { rotate: `${kf(v, [[0, 0], [0.55, 0], [0.62, 14], [0.7, -12], [0.78, 8], [0.86, -5], [1, 0]])}deg` },
          ],
        };
      case 'float':
        return { transform: [{ translateY: kf(v, [[0, 0], [0.5, -8], [1, 0]]) }] };
      default:
        return {};
    }
  });

  return (
    <Animated.Image
      source={source}
      style={[{ width: size, height: size, transformOrigin: '50% 88%' }, style, anim]}
      resizeMode="contain"
    />
  );
}
