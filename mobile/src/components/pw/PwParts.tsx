/**
 * Building blocks of the V3 paywall (17–19) and offer (20), drawn from the
 * canvas artboards PW_B1, PW_B2, PW_B3*, PW_P1_*, Offer_C2*.
 */
import { Image, Linking, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { useVideoPlayer, VideoView } from 'expo-video';
import Svg, { Defs, LinearGradient, Path, Rect, Stop } from 'react-native-svg';

import { IMG, PW } from '@/onb/assets';
import { C, F, SHADOW } from '@/onb/theme';

export const TERMS_URL = 'https://yumyummy.ai/terms.html';
export const PRIVACY_URL = 'https://yumyummy.ai/privacy.html';

function Check({ color, size = 16, width = 2.4 }: { color: string; size?: number; width?: number }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M20 6 9 17l-5-5" stroke={color} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

/** "✓ No payment for now" — only ever shown while a free trial applies. */
export function NoPayment() {
  return (
    <View style={s.noPay}>
      <Check color={C.ink} />
      <Text style={s.noPayText}>No payment for now</Text>
    </View>
  );
}

/** "Terms · Privacy · Restore" (12 pt). Restore is a real button, as App Review requires. */
export function LegalRow({
  onRestore,
  color = C.muted,
  style,
}: {
  onRestore: () => void;
  /** Muted on paper; `rgba(255,255,255,.6)` on B3, `.55` on the offer. */
  color?: string;
  style?: StyleProp<ViewStyle>;
}) {
  const link = [s.legal, { color }];
  return (
    <View style={[s.legalRow, style]}>
      <Pressable hitSlop={8} onPress={() => void Linking.openURL(TERMS_URL)} accessibilityRole="link">
        <Text style={link}>Terms</Text>
      </Pressable>
      <Text style={link}> · </Text>
      <Pressable hitSlop={8} onPress={() => void Linking.openURL(PRIVACY_URL)} accessibilityRole="link">
        <Text style={link}>Privacy</Text>
      </Pressable>
      <Text style={link}> · </Text>
      <Pressable hitSlop={8} onPress={onRestore} accessibilityRole="button">
        <Text style={link}>Restore</Text>
      </Pressable>
    </View>
  );
}

const LOCK = (
  <Svg width={18} height={18} viewBox="0 0 24 24" fill="none">
    <Rect x={4} y={11} width={16} height={10} rx={2} stroke="#FFFFFF" strokeWidth={1.8} />
    <Path d="M8 11V7a4 4 0 0 1 7.8-1.2" stroke="#FFFFFF" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
  </Svg>
);
const BELL = (
  <Svg width={18} height={18} viewBox="0 0 24 24" fill="none">
    <Path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" stroke={C.muted} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
    <Path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" stroke={C.muted} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
  </Svg>
);
const CROWN = (
  <Svg width={18} height={18} viewBox="0 0 24 24" fill="none">
    <Path d="M3 18 2 7l5.5 4L12 4l4.5 7L22 7l-1 11z" stroke={C.muted} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
    <Path d="M5 21h14" stroke={C.muted} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
  </Svg>
);

/** Trial timeline: today → reminder the day before → billing starts. */
/**
 * `compact`: titles only, for the plans screen on short iPhones (the plan cards must stay in view).
 * `large`: bigger dots, type and rows, for B1 on tall iPhones (the timeline is all that screen has).
 */
export function TrialTimeline({
  trialDays,
  todayLine,
  compact,
  large,
}: {
  trialDays: number;
  todayLine: string;
  compact?: boolean;
  large?: boolean;
}) {
  const remind = trialDays - 1;
  const rows = [
    { icon: LOCK, on: true, title: 'Today', sub: todayLine },
    {
      icon: BELL,
      on: false,
      title: remind >= 1 ? `In ${remind} day${remind === 1 ? '' : 's'}: reminder` : 'Before it ends: reminder',
      sub: 'We’ll send you a reminder that your trial is ending soon',
    },
    {
      icon: CROWN,
      on: false,
      title: `In ${trialDays} day${trialDays === 1 ? '' : 's'}: billing starts`,
      sub: 'You’ll be charged unless you cancel before',
    },
  ];
  return (
    <View style={s.timeline}>
      {rows.map((r, i) => (
        <View key={r.title} style={[s.tRow, compact && s.tRowCompact, large && s.tRowLarge]}>
          {i < rows.length - 1 ? <View style={[s.tRail, large && s.tRailLarge]} /> : null}
          <View style={[s.tDot, large && s.tDotLarge, r.on ? s.tDotOn : s.tDotOff]}>
            {large ? <View style={s.tIconLarge}>{r.icon}</View> : r.icon}
          </View>
          <View style={[s.tText, large && s.tTextLarge]}>
            <Text style={[s.tTitle, large && s.tTitleLarge]}>{r.title}</Text>
            {compact ? null : <Text style={[s.tSub, large && s.tSubLarge]}>{r.sub}</Text>}
          </View>
        </View>
      ))}
    </View>
  );
}

/** The calorie badge on the photo screens (B3, offer close-up). */
export function PhotoBadge({
  title,
  kcal,
  source,
  style,
}: {
  title: string;
  kcal: string;
  source: string;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <View style={[s.badge, SHADOW, style]}>
      <Text style={s.badgeTitle}>{title}</Text>
      <View style={s.badgeRow}>
        <Text style={s.badgeKcal}>{kcal}</Text>
        <Text style={s.badgeUnit}>kcal</Text>
      </View>
      <View style={s.badgeSource}>
        {/* One line, shrunk to fit: a long domain wrapped "◎" onto its own row. */}
        <Text style={s.badgeSourceText} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.75}>
          ◎ {source}
        </Text>
      </View>
    </View>
  );
}

/** "5.0 ★ / avg App Store rating" between small laurels (B3). */
export function LaurelRating({ rating }: { rating: string }) {
  return (
    <View style={s.laurels}>
      <Image source={IMG.laurel_left} style={s.laurelImg} />
      <View style={s.laurelText}>
        <Text style={s.laurelBig}>{rating} ★</Text>
        <Text style={s.laurelSmall}>avg App Store rating</Text>
      </View>
      <Image source={IMG.laurel_right} style={s.laurelImg} />
    </View>
  );
}

/** P1: a muted looping demo in the iPhone frame (frame 216 × 444, screen 202 × 430, radius 29). */
export function PhoneVideo({ video, poster }: { video: number; poster: number }) {
  const player = useVideoPlayer(video, (p) => {
    p.loop = true;
    p.muted = true;
    p.play();
  });
  return (
    <View style={s.phone}>
      <View style={s.phoneScreen}>
        <Image source={poster} style={StyleSheet.absoluteFill} />
        <VideoView player={player} style={StyleSheet.absoluteFill} contentFit="cover" nativeControls={false} />
      </View>
      <Image source={PW.phone_frame} style={s.frame} />
    </View>
  );
}

/** Transparent → ink, as `linear-gradient(rgba(25,21,15,0), #19150F)` on B3 and the offer. */
/** Transparent → ink; `mid` adds a stop (e.g. already dark where a headline sits). */
export function InkFade({ top, height, mid }: { top: number; height: number; mid?: { at: number; opacity: number } }) {
  // A middle stop at (0.5, 0.5) is the plain straight ramp.
  const m = mid ?? { at: 0.5, opacity: 0.5 };
  return (
    <Svg style={{ position: 'absolute', left: 0, right: 0, top, height }} width="100%" height={height} pointerEvents="none">
      <Defs>
        <LinearGradient id="inkFade" x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor={C.ink} stopOpacity={0} />
          <Stop offset={m.at} stopColor={C.ink} stopOpacity={m.opacity} />
          <Stop offset="1" stopColor={C.ink} stopOpacity={1} />
        </LinearGradient>
      </Defs>
      <Rect x="0" y="0" width="100%" height={height} fill="url(#inkFade)" />
    </Svg>
  );
}

export { Check };

const s = StyleSheet.create({
  noPay: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  noPayText: { fontFamily: F.sansSemibold, fontSize: 15, lineHeight: 20, color: C.ink },
  legalRow: { marginTop: 12, flexDirection: 'row', justifyContent: 'center' },
  legal: { fontFamily: F.sans, fontSize: 12, lineHeight: 16 },
  timeline: { gap: 4, paddingHorizontal: 6 },
  tRow: { flexDirection: 'row', gap: 14, minHeight: 74 },
  tRowCompact: { minHeight: 44 },
  tRail: { position: 'absolute', left: 17, top: 40, width: 2, height: 34, backgroundColor: C.hair },
  tDot: { width: 36, height: 36, borderRadius: 18, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
  tDotOn: { backgroundColor: C.terra, borderColor: C.terra },
  tDotOff: { backgroundColor: C.surface, borderColor: C.hair2 },
  tText: { flex: 1, gap: 2, paddingTop: 6 },
  tTitle: { fontFamily: F.sansSemibold, fontSize: 16, lineHeight: 21, color: C.ink },
  tSub: { fontFamily: F.sans, fontSize: 14, lineHeight: 20, color: C.muted },
  tRowLarge: { minHeight: 92, gap: 16 },
  tRailLarge: { left: 22, top: 50, height: 42 },
  tDotLarge: { width: 46, height: 46, borderRadius: 23 },
  tIconLarge: { transform: [{ scale: 1.25 }] },
  tTextLarge: { paddingTop: 10, gap: 3 },
  tTitleLarge: { fontSize: 18, lineHeight: 24 },
  tSubLarge: { fontSize: 15, lineHeight: 21 },
  badge: {
    paddingVertical: 12,
    paddingHorizontal: 14,
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.hair,
    borderRadius: 16,
    gap: 6,
  },
  badgeTitle: { fontFamily: F.sansSemibold, fontSize: 14, lineHeight: 18, color: C.ink },
  badgeRow: { flexDirection: 'row', alignItems: 'baseline', gap: 5 },
  badgeKcal: { fontFamily: F.serif, fontSize: 30, lineHeight: 30, color: C.ink, fontVariant: ['tabular-nums'] },
  badgeUnit: { fontFamily: F.sans, fontSize: 14, color: C.muted },
  badgeSource: {
    alignSelf: 'flex-start',
    maxWidth: '100%',
    backgroundColor: C.infoSoft,
    borderRadius: 999,
    paddingVertical: 3,
    paddingHorizontal: 8,
  },
  badgeSourceText: { fontFamily: F.mono, fontSize: 10, letterSpacing: 0.8, lineHeight: 14, color: C.info },
  laurels: { marginTop: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  laurelImg: { width: 20, height: 40 },
  laurelText: { alignItems: 'center' },
  laurelBig: { fontFamily: F.serif, fontSize: 20, lineHeight: 24, color: '#FFFFFF' },
  laurelSmall: { fontFamily: F.sans, fontSize: 11, lineHeight: 14, color: 'rgba(255,255,255,0.7)' },
  phone: { width: 216, height: 444, alignSelf: 'center' },
  phoneScreen: {
    position: 'absolute',
    left: 7,
    top: 7,
    width: 202,
    height: 430,
    borderRadius: 29,
    overflow: 'hidden',
    backgroundColor: C.paper2,
  },
  frame: { position: 'absolute', left: 0, top: 0, width: 216, height: 444 },
});
