import { type ReactNode } from 'react';
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  View,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import * as Haptics from 'expo-haptics';

import { AppText } from './AppText';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';

// `primary` = charcoal (default action). `brand` = terracotta, for the single
// hero/onboarding CTA per screen. `dark` is kept as an alias of primary.
type Variant = 'primary' | 'brand' | 'secondary' | 'ghost' | 'dark';
type Size = 'lg' | 'md';

interface ButtonProps {
  label: string;
  onPress?: () => void;
  variant?: Variant;
  size?: Size;
  disabled?: boolean;
  loading?: boolean;
  haptic?: boolean;
  fullWidth?: boolean;
  icon?: ReactNode;
  style?: StyleProp<ViewStyle>;
}

const BG: Record<Variant, string> = {
  primary: colors.ink,
  brand: colors.terracotta,
  secondary: 'transparent',
  ghost: 'transparent',
  dark: colors.ink,
};
const FG: Record<Variant, string> = {
  primary: colors.bg,
  brand: colors.white,
  secondary: colors.ink,
  ghost: colors.terracottaText,
  dark: colors.bg,
};

export function Button({
  label,
  onPress,
  variant = 'primary',
  size = 'lg',
  disabled = false,
  loading = false,
  haptic = true,
  fullWidth = true,
  icon,
  style,
}: ButtonProps) {
  const handlePress = () => {
    if (disabled || loading) return;
    if (haptic) Haptics.selectionAsync().catch(() => {});
    onPress?.();
  };

  return (
    <Pressable
      onPress={handlePress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.base,
        size === 'lg' ? styles.lg : styles.md,
        { backgroundColor: BG[variant] },
        variant === 'secondary' && styles.bordered,
        fullWidth && styles.fullWidth,
        (disabled || loading) && styles.disabled,
        pressed && styles.pressed,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={FG[variant]} />
      ) : (
        <View style={styles.content}>
          {icon}
          <AppText style={[styles.label, { color: FG[variant], fontFamily: fonts.sansSemibold }]}>
            {label}
          </AppText>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    borderRadius: radius.md, // 12 — never a pill CTA
    alignItems: 'center',
    justifyContent: 'center',
  },
  lg: { minHeight: 54, paddingHorizontal: space.xl },
  md: { minHeight: 44, paddingHorizontal: space.base },
  fullWidth: { alignSelf: 'stretch' },
  bordered: { borderWidth: 1, borderColor: colors.hairlineStrong },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.85 },
  content: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  // Tight lineHeight so the label is truly vertically centered in the button
  // (otherwise it inherits body's 26px lineHeight and rides high).
  label: { fontSize: 16, lineHeight: 20 },
});
