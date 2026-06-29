import { View, StyleSheet } from 'react-native';
import { AppText } from './AppText';
import { colors, radius, space } from '@/theme/tokens';
import type { AccuracyLevel } from '@/api/types';

const STAMP = '\u25CE'; // ◎ — the signature "source stamp" glyph

/**
 * SOURCE stamp — *where* a number came from (USDA / EU LABEL / MANUFACTURER).
 * The signature element (v2 §10): an info-blue pill, mono, prefixed with ◎.
 * An "estimate" source falls back to the warning palette. Deliberately distinct
 * from AccuracyBadge ("source ≠ accuracy").
 */
export function SourceBadge({ source }: { source: string }) {
  const isEstimate = source.trim().toLowerCase().includes('estimate');
  const bg = isEstimate ? colors.warningSoft : colors.infoBlueSoft;
  const fg = isEstimate ? colors.warning : colors.infoBlue;
  return (
    <View style={[styles.pill, { backgroundColor: bg }]}>
      <AppText variant="eyebrow" color={fg} style={styles.text}>
        {`${STAMP} ${source.toUpperCase()}`}
      </AppText>
    </View>
  );
}

const ACCURACY: Record<AccuracyLevel, { label: string; color: string }> = {
  EXACT: { label: 'Exact', color: colors.success },
  ESTIMATE: { label: 'Estimate', color: colors.warning },
  APPROX: { label: 'Approx', color: colors.inkFaint },
};

/** ACCURACY badge — *how confident* the estimate is (semantic palette). */
export function AccuracyBadge({ level }: { level: AccuracyLevel }) {
  const meta = ACCURACY[level];
  return (
    <View style={styles.accuracy}>
      <View style={[styles.dot, { backgroundColor: meta.color }]} />
      <AppText variant="eyebrow" color={meta.color} style={styles.text}>
        {meta.label}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  pill: {
    paddingHorizontal: space.sm,
    paddingVertical: 3,
    borderRadius: radius.pill,
    alignSelf: 'flex-start',
  },
  text: { letterSpacing: 1 },
  accuracy: { flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start' },
  dot: { width: 7, height: 7, borderRadius: 4 },
});
