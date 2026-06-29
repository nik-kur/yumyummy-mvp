import { View, StyleSheet } from 'react-native';
import { colors, radius } from '@/theme/tokens';

interface ProgressBarProps {
  progress: number; // 0..1
  color?: string;
  track?: string;
  height?: number;
}

export function ProgressBar({
  progress,
  color = colors.terracotta,
  track = colors.hairline,
  height = 10,
}: ProgressBarProps) {
  const pct = `${Math.max(0, Math.min(1, progress)) * 100}%` as const;
  return (
    <View style={[styles.track, { height, borderRadius: height / 2, backgroundColor: track }]}>
      <View style={{ width: pct, height, borderRadius: height / 2, backgroundColor: color }} />
    </View>
  );
}

const styles = StyleSheet.create({
  track: { width: '100%', overflow: 'hidden' },
});
