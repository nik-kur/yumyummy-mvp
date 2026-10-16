/**
 * Frame of every V3 quiz screen (canvas: padding 52 / 24 / 34, back chevron +
 * 4 px progress bar, Fraunces 32/38 headline, Inter 17/25 subline, content,
 * one CTA pinned to the bottom).
 *
 * The artboards are 390 × 844 with the status bar inside the 52 pt top
 * padding; on a device the safe-area inset replaces the status bar part.
 */
import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Svg, { Path } from 'react-native-svg';

import { C, F, PAD } from '@/onb/theme';

export function OnbProgress({
  pct,
  canGoBack = true,
  onBack,
}: {
  /** `null` = back chevron only (screen 16). */
  pct: number | null;
  canGoBack?: boolean;
  onBack?: () => void;
}) {
  const router = useRouter();
  return (
    <View style={s.header}>
      <Pressable
        onPress={onBack ?? (() => router.back())}
        disabled={!canGoBack}
        style={[s.back, !canGoBack && s.hidden]}
        hitSlop={6}
        accessibilityLabel="Back"
      >
        <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
          <Path d="m15 18-6-6 6-6" stroke={C.ink} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
        </Svg>
      </Pressable>
      {pct !== null ? (
        <View style={s.track}>
          <View style={[s.fill, { width: `${pct}%` }]} />
        </View>
      ) : null}
    </View>
  );
}

interface Props {
  /** Progress bar fill in %, or `null` for screens without the header. */
  progress: number | null;
  title?: ReactNode;
  sub?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  /** Header back button; false on the first quiz screen after a hand-over. */
  canGoBack?: boolean;
  onBack?: () => void;
  center?: boolean;
  contentStyle?: StyleProp<ViewStyle>;
  /** Back chevron without a progress bar. */
  backOnly?: boolean;
}

export function OnbLayout({ progress, title, sub, children, footer, canGoBack, onBack, center, contentStyle, backOnly }: Props) {
  const insets = useSafeAreaInsets();
  return (
    <View
      style={[
        s.screen,
        { paddingTop: insets.top + PAD.topBelowStatus, paddingBottom: Math.max(insets.bottom, 20) },
      ]}
    >
      {progress !== null || backOnly ? (
        <OnbProgress pct={progress} canGoBack={canGoBack} onBack={onBack} />
      ) : null}
      {title ? (
        typeof title === 'string' ? (
          <Text style={[s.title, center && s.center]}>{title}</Text>
        ) : (
          title
        )
      ) : null}
      {sub ? <Text style={[s.sub, center && s.center]}>{sub}</Text> : null}
      <View style={[s.content, contentStyle]}>{children}</View>
      {footer}
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.paper, paddingHorizontal: PAD.side },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  back: { width: 44, height: 44, marginLeft: -10, alignItems: 'center', justifyContent: 'center' },
  hidden: { opacity: 0 },
  track: { flex: 1, height: 4, borderRadius: 2, backgroundColor: C.hair, overflow: 'hidden' },
  fill: { height: 4, borderRadius: 2, backgroundColor: C.ink },
  title: {
    marginTop: 24,
    fontFamily: F.serif,
    fontSize: 32,
    lineHeight: 38,
    letterSpacing: -0.32,
    color: C.ink,
  },
  sub: { marginTop: 10, fontFamily: F.sans, fontSize: 17, lineHeight: 25, color: C.muted },
  center: { textAlign: 'center' },
  content: { flex: 1 },
});
