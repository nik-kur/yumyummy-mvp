import { View, StyleSheet } from 'react-native';
import { AppText } from './AppText';
import { Button } from './Button';
import { MascotBadge, type MascotVariant } from './MascotBadge';
import { colors, radius, space } from '@/theme/tokens';

interface EmptyStateProps {
  glyph?: string;
  /** When set, renders the animated mascot instead of the emoji medallion. */
  mascot?: MascotVariant;
  title: string;
  subtitle?: string;
  ctaLabel?: string;
  onCta?: () => void;
}

/**
 * Friendly empty state with a soft illustrative medallion (Variant C flavor).
 * Used for the day-0 home and an empty My Menu.
 */
export function EmptyState({ glyph = '\u{1F957}', mascot, title, subtitle, ctaLabel, onCta }: EmptyStateProps) {
  return (
    <View style={styles.wrap}>
      {mascot ? (
        <MascotBadge variant={mascot} size={110} style={styles.mascot} />
      ) : (
        <View style={styles.medallion}>
          <AppText style={styles.glyph}>{glyph}</AppText>
        </View>
      )}
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
  mascot: { marginBottom: space.sm },
  glyph: { fontSize: 44 },
  subtitle: { maxWidth: 300 },
  cta: { marginTop: space.md, paddingHorizontal: space.xxl },
});
