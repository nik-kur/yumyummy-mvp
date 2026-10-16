/**
 * V3 buttons: `ink` (quiz CTA: charcoal, cream label), `brand` (welcome:
 * terracotta, white label), `text` (secondary 44 pt text button).
 * 54 pt tall, radius 12, Inter 600 16 — as on every artboard.
 */
import { Pressable, StyleSheet, Text, type StyleProp, type ViewStyle } from 'react-native';
import * as Haptics from 'expo-haptics';

import { C, F } from '@/onb/theme';

interface Props {
  label: string;
  onPress: () => void;
  variant?: 'ink' | 'brand' | 'text';
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
}

export function OnbButton({ label, onPress, variant = 'ink', disabled, style }: Props) {
  const isText = variant === 'text';
  return (
    <Pressable
      onPress={() => {
        if (!isText) void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
        onPress();
      }}
      disabled={disabled}
      style={({ pressed }) => [
        isText ? s.text : s.button,
        variant === 'ink' && { backgroundColor: C.ink },
        variant === 'brand' && { backgroundColor: C.terra },
        (pressed || disabled) && !isText && { opacity: disabled ? 0.35 : 0.85 },
        style,
      ]}
      accessibilityRole="button"
    >
      <Text
        style={[
          isText ? s.textLabel : s.label,
          { color: variant === 'ink' ? C.paper : variant === 'brand' ? C.white : C.muted },
        ]}
      >
        {label}
      </Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  button: { height: 54, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  label: { fontFamily: F.sansSemibold, fontSize: 16 },
  text: { marginTop: 4, height: 44, alignItems: 'center', justifyContent: 'center' },
  textLabel: { fontFamily: F.sansMedium, fontSize: 15 },
});
