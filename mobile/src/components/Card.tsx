import { type ReactNode } from 'react';
import { View, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';
import { colors, radius, shadow, space } from '@/theme/tokens';

interface CardProps {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  /** Back-compat: previously removed the shadow. Cards are now borders-only by default. */
  flat?: boolean;
  padded?: boolean;
  /** Opt-in elevation for things that genuinely float (sheets, popovers). */
  floating?: boolean;
}

/** Editorial card: warm-white surface + 1px hairline border, no shadow by default (v2 §7). */
export function Card({ children, style, flat = false, padded = true, floating = false }: CardProps) {
  return (
    <View style={[styles.card, padded && styles.padded, floating && shadow.float, style]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg, // 16
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
  },
  padded: { padding: space.lg },
});
