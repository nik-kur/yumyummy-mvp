import { View, StyleSheet } from 'react-native';
import { AppText } from './AppText';
import { ProgressBar } from './ProgressBar';
import { colors, space } from '@/theme/tokens';
import type { MacroKey } from '@/theme/tokens';

interface MacroBarProps {
  label: string;
  macro: MacroKey;
  value: number;
  target?: number | null;
  unit?: string;
}

/** Macro indicator: muted P/C/F color, thin bar, label in inkMuted, tabular value (v2 §10). */
export function MacroBar({ label, macro, value, target, unit = 'g' }: MacroBarProps) {
  const color = colors[macro];
  const progress = target && target > 0 ? value / target : 0;
  return (
    <View style={styles.wrap}>
      <View style={styles.row}>
        <AppText variant="eyebrow" color={colors.inkMuted}>
          {label}
        </AppText>
        <AppText variant="macroValue" color={colors.ink}>
          {Math.round(value)}
          {unit}
          {target ? ` / ${Math.round(target)}${unit}` : ''}
        </AppText>
      </View>
      <ProgressBar progress={progress} color={color} track={colors.hairline} height={6} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, gap: space.xs },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' },
});
