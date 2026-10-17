/**
 * Answer card of the V3 quiz: sticker icon + label (+ optional subline),
 * hairline border; selected = terracotta border on the soft terracotta fill.
 * `compact` is the Source screen's denser row (min 44 pt, 30 pt icon).
 */
import type { ReactNode } from 'react';
import { Image, Pressable, StyleSheet, Text, View, type ImageSourcePropType } from 'react-native';
import * as Haptics from 'expo-haptics';

import { C, F } from '@/onb/theme';

interface Props {
  label: string;
  sub?: string;
  icon?: ImageSourcePropType;
  /** Custom icon node (brand logos drawn in SVG). */
  iconNode?: ReactNode;
  iconSize?: number;
  selected: boolean;
  onPress: () => void;
  compact?: boolean;
  center?: boolean;
  /** Per-screen paddings from the artboard (Goal 14/16, Tracked 16/18, Barriers 12/16, Gender 0/20 + min 64). */
  pad?: { v: number; h: number; minHeight?: number };
  /** Label in Inter 600 (cards with a subline). */
  bold?: boolean;
}

export function OptionCard({ label, sub, icon, iconNode, iconSize = 36, selected, onPress, compact, center, pad, bold }: Props) {
  return (
    <Pressable
      onPress={() => {
        void Haptics.selectionAsync().catch(() => {});
        onPress();
      }}
      style={[
        s.card,
        compact ? s.compact : s.regular,
        pad && { paddingVertical: pad.v, paddingHorizontal: pad.h, minHeight: pad.minHeight },
        selected ? s.selected : s.idle,
        center && s.centered,
      ]}
      accessibilityRole="button"
      accessibilityState={{ selected }}
    >
      {iconNode ?? (icon ? <Image source={icon} style={{ width: iconSize, height: iconSize }} /> : null)}
      <View style={center ? undefined : s.text}>
        <Text style={[s.label, bold && s.bold]}>{label}</Text>
        {sub ? <Text style={s.sub}>{sub}</Text> : null}
      </View>
    </Pressable>
  );
}

const s = StyleSheet.create({
  card: { flexDirection: 'row', alignItems: 'center', gap: 14, borderRadius: 16, borderWidth: 1.5 },
  regular: { paddingVertical: 14, paddingHorizontal: 16 },
  compact: { minHeight: 44, paddingVertical: 5, paddingHorizontal: 14 },
  idle: { borderColor: C.hair, backgroundColor: C.surface },
  selected: { borderColor: C.terra, backgroundColor: C.terraSoft },
  centered: { justifyContent: 'center' },
  text: { flex: 1 },
  label: { fontFamily: F.sansMedium, fontSize: 17, lineHeight: 22, color: C.ink },
  bold: { fontFamily: F.sansSemibold },
  sub: { marginTop: 2, fontFamily: F.sans, fontSize: 14, lineHeight: 19, color: C.muted },
});
