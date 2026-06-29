import { View, StyleSheet } from 'react-native';
import { AppText } from './AppText';
import { Button } from './Button';
import { colors, radius, space } from '@/theme/tokens';

interface EmptyStateProps {
  glyph?: string;
  title: string;
  subtitle?: string;
  ctaLabel?: string;
  onCta?: () => void;
}

/**
 * Friendly empty state with a soft illustrative medallion (Variant C flavor).
 * Used for the day-0 home and an empty My Menu.
 */
export function EmptyState({ glyph = '\u{1F957}', title, subtitle, ctaLabel, onCta }: EmptyStateProps) {
  return (
    <View style={styles.wrap}>
      <View style={styles.medallion}>
        <AppText style={styles.glyph}>{glyph}</AppText>
      </View>
      <AppText variant="h2" center>
        {title}
      </AppText>
      {subtitle ? (
        <AppText variant="body" color={colors.inkMuted} center style={styles.subtitle}>
          {subtitle}
        </AppText>
      ) : null}
      {ctaLabel ? (
        <Button label={ctaLabel} onPress={onCta} fullWidth={false} style={styles.cta} />
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', paddingVertical: space.xxl, gap: space.md },
  medallion: {
    width: 96,
    height: 96,
    borderRadius: radius.pill,
    backgroundColor: colors.terracottaSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: space.sm,
  },
  glyph: { fontSize: 44 },
  subtitle: { maxWidth: 300 },
  cta: { marginTop: space.md, paddingHorizontal: space.xxl },
});
