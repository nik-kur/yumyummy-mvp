import { type ReactNode } from 'react';
import { View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

import { colors } from '@/theme/tokens';

interface RingProps {
  size?: number;
  stroke?: number;
  /** 0..1 */
  progress: number;
  color?: string;
  track?: string;
  children?: ReactNode;
}

/**
 * The de-gamified calorie hero (v2 §10): a thin, single-color arc — not a thick
 * multicolor donut. Track is a hairline; the arc deepens (terracottaText) only
 * when the caller signals over-budget via `color`.
 */
export function Ring({
  size = 168,
  stroke = 5,
  progress,
  color = colors.terracotta,
  track = colors.hairline,
  children,
}: RingProps) {
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(1, progress));
  const offset = circumference * (1 - clamped);

  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg
        width={size}
        height={size}
        style={{ position: 'absolute', transform: [{ rotate: '-90deg' }] }}
      >
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={track} strokeWidth={stroke} fill="none" />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={offset}
        />
      </Svg>
      {children}
    </View>
  );
}
