/**
 * V3 screen 1 — Welcome (test O3). A: photo + calorie badge (control, App
 * Review default), B: + laurel rating, C: mascot + laurels, D: demo video in a
 * phone. Headline/subline can be overridden from `onb_main.welcome`.
 *
 * Slot: `welcome.render: "flow"` shows the flow published on `onb_welcome`
 * instead (custom actions `next` / `sign_in`); no flow within 1.5 s → A.
 * ATT is asked here only when the arm says `att: "welcome"` (test O6).
 */
import { useEffect, useRef, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Image as ExpoImage } from 'expo-image';
import { getTrackingPermissionsAsync } from 'expo-tracking-transparency';
import { useVideoPlayer, VideoView } from 'expo-video';
import { AdaptyFlowView } from 'react-native-adapty';
import type { AdaptyFlow } from 'react-native-adapty';

import { requestTrackingConsent } from '@/analytics/attribution';
import { track } from '@/analytics/posthog';
import { captureException } from '@/analytics/sentry';
import { ADAPTY_PLACEMENT_WELCOME_SLOT } from '@/billing/adapty';
import { handleFlowPermissionRequest, trackFlowAnalytics } from '@/billing/flowBridge';
import { OnbButton } from '@/components/onb/OnbButton';
import { Sticker } from '@/components/onb/Sticker';
import { getFlowQuiet, getOnboardingConfig } from '@/config/onboardingConfig';
import { IMG, VIDEO } from '@/onb/assets';
import { C, F, SHADOW } from '@/onb/theme';
import { useOnbScreen } from '@/onb/useOnbScreen';

const SLOT_TIMEOUT_MS = 1500;
const DEFAULT_HEADLINE = 'Calorie tracking\nmade easy';

function SignInLink({ onPress }: { onPress: () => void }) {
  return (
    <Pressable onPress={onPress} hitSlop={8} style={s.linkWrap}>
      <Text style={s.link}>
        Already have an account? <Text style={s.linkStrong}>Sign in</Text>
      </Text>
    </Pressable>
  );
}

function CalorieBadge() {
  return (
    <View style={[s.badge, SHADOW]}>
      <Text style={s.badgeTitle}>Butter Croissant</Text>
      <View style={s.badgeRow}>
        <Text style={s.badgeKcal}>280</Text>
        <Text style={s.badgeUnit}>kcal</Text>
      </View>
      <View style={s.source}>
        <Text style={s.sourceText}>◎ COSTA.CO.UK</Text>
      </View>
    </View>
  );
}

function LaurelStat({ value, label, big }: { value: string; label: string; big?: boolean }) {
  const lw = big ? 40 : 34;
  const lh = big ? 78 : 66;
  return (
    <View style={[s.laurelRow, { gap: big ? 14 : 10 }]}>
      <Image source={IMG.laurel_left} style={{ width: lw, height: lh }} />
      <View style={[s.laurelText, big && { width: 170 }]}>
        <Text style={big ? s.statBig : s.stat}>{value}</Text>
        <Text style={big ? s.statLabelBig : s.statLabel}>{label}</Text>
      </View>
      <Image source={IMG.laurel_right} style={{ width: lw, height: lh }} />
    </View>
  );
}

/** `scale` fits the 246 × 506 mockup on short screens (the button must stay in view). */
function PhoneDemo({ scale = 1 }: { scale?: number }) {
  const player = useVideoPlayer(VIDEO.welcome_d, (p) => {
    p.loop = true;
    p.muted = true;
    p.play();
  });
  return (
    <View
      style={[
        s.phone,
        SHADOW,
        { width: 246 * scale, height: 506 * scale, padding: 9 * scale, borderRadius: 46 * scale },
      ]}
    >
      <View style={[s.phoneScreen, { borderRadius: 38 * scale }]}>
        <Image source={IMG.welcome_d_poster} style={StyleSheet.absoluteFill} />
        <VideoView player={player} style={StyleSheet.absoluteFill} contentFit="cover" nativeControls={false} />
      </View>
      <View
        style={[
          s.island,
          { left: 89 * scale, top: 18 * scale, width: 68 * scale, height: 20 * scale, borderRadius: 10 * scale },
        ]}
      />
    </View>
  );
}

export default function WelcomeScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { height } = useWindowDimensions();
  const initial = getOnboardingConfig().welcome;
  const { config, content, next } = useOnbScreen('S1_welcome', initial.render === 'flow' ? 'flow' : initial.variant);
  const welcome = config.welcome;
  const [slotFlow, setSlotFlow] = useState<AdaptyFlow | null>(null);
  const [slotDone, setSlotDone] = useState(welcome.render !== 'flow');
  const busy = useRef(false);

  // Slot: try the Flow Builder welcome; fall back to ours.
  useEffect(() => {
    if (welcome.render !== 'flow') return;
    let alive = true;
    void getFlowQuiet(ADAPTY_PLACEMENT_WELCOME_SLOT, SLOT_TIMEOUT_MS).then((flow) => {
      if (!alive) return;
      if (flow?.hasViewConfiguration) setSlotFlow(flow);
      else track('onboarding_slot_fallback', { slot: 'welcome', reason: flow ? 'no_view' : 'no_flow' });
      setSlotDone(true);
    });
    return () => {
      alive = false;
    };
  }, [welcome.render]);

  const headline = welcome.headline ?? content.texts['welcome.headline'] ?? DEFAULT_HEADLINE;
  const subline = welcome.subline ?? content.texts['welcome.subline'] ?? null;

  const start = async () => {
    if (busy.current) return;
    busy.current = true;
    if (config.att === 'welcome') {
      const current = await getTrackingPermissionsAsync().catch(() => null);
      if (current?.status === 'undetermined' && current.canAskAgain) {
        track('att_prompt_shown', { source: 'v3_welcome' });
        const granted = await requestTrackingConsent();
        track('att_prompt_answered', { granted, source: 'v3_welcome' });
      }
    }
    busy.current = false;
    next({}, { action: 'start' });
  };
  const signIn = () => {
    track('onboarding_screen_completed', { screen: 'S1_welcome', action: 'sign_in' });
    router.replace('/(auth)/sign-in');
  };

  const variant = welcome.variant;
  const bottomPad = Math.max(insets.bottom - 4, 16);

  if (!slotDone) return <View style={s.fill} />;

  if (slotFlow) {
    const ctx = { placement: ADAPTY_PLACEMENT_WELCOME_SLOT, variation: slotFlow.variationId, variationName: slotFlow.variationName };
    return (
      <AdaptyFlowView
        flow={slotFlow}
        style={s.fill}
        onAnalytics={(name, params) => {
          trackFlowAnalytics(ctx, name, params);
          return false;
        }}
        onCustomAction={(actionId) => {
          if (actionId === 'sign_in') signIn();
          else if (actionId === 'next') void start();
          return false;
        }}
        onCloseButtonPress={() => {
          void start();
          return false;
        }}
        onRequestPermission={handleFlowPermissionRequest}
        onError={(error) => {
          captureException(error, { placement: ADAPTY_PLACEMENT_WELCOME_SLOT });
          setSlotFlow(null);
          return false;
        }}
      />
    );
  }

  // A and B set the headline bigger and centred in the sheet (phone test, 18 Oct:
  // a small left-aligned line left an empty band above the button). Both arms
  // share it, so the O3 test still differs by the rating laurel only.
  const Headline = (
    <Text style={[variant === 'C' ? s.h1C : variant === 'D' ? s.h1 : s.h1Sheet, (variant === 'C' || variant === 'D') && s.centerText]}>
      {headline}
    </Text>
  );
  const Sub = subline ? <Text style={[s.sub, s.centerText]}>{subline}</Text> : null;

  if (variant === 'C') {
    return (
      <View style={[s.fill, s.colCenter, { paddingTop: insets.top + 25, paddingBottom: bottomPad }]}>
        <View style={s.brandRow}>
          <Sticker source={IMG.mascot_great} size={64} motion="bob" />
          <Text style={s.brand}>YumYummy</Text>
        </View>
        <View style={{ flex: 1 }} />
        {Headline}
        {Sub}
        <View style={s.statsC}>
          <LaurelStat value={`${content.rating} ★`} label="App Store rating" big />
          <LaurelStat value={content.users} label="people already tracking" big />
        </View>
        <View style={{ flex: 1.2 }} />
        <OnbButton label="Get started" variant="brand" onPress={() => void start()} style={s.stretch} />
        <SignInLink onPress={signIn} />
      </View>
    );
  }

  if (variant === 'D') {
    return (
      <View style={[s.fill, s.colCenter, { paddingTop: insets.top + 9, paddingBottom: bottomPad }]}>
        <PhoneDemo scale={Math.min(1, Math.max(0.55, (height - insets.top - bottomPad - 250) / 506))} />
        <View style={{ flex: 1 }} />
        {Headline}
        {Sub}
        <View style={{ flex: 1 }} />
        <OnbButton label="Get started" variant="brand" onPress={() => void start()} style={s.stretch} />
        <SignInLink onPress={signIn} />
      </View>
    );
  }

  // A and B: full-bleed photo, badge, bottom sheet.
  const sheetH = variant === 'B' ? 376 : 316;
  const photoOverlap = variant === 'B' ? 58 : 89;
  return (
    <View style={s.fill}>
      <ExpoImage
        source={IMG.bg_costa}
        style={[s.photo, { bottom: sheetH - photoOverlap }]}
        contentFit="cover"
        contentPosition="top"
      />
      <View style={[s.badgeWrap, { bottom: sheetH + 32 }, variant === 'B' && { right: 17 }]}>
        <CalorieBadge />
      </View>
      <View style={[s.sheet, { height: sheetH + Math.max(0, bottomPad - 30), paddingTop: variant === 'B' ? 32 : 12, paddingBottom: bottomPad }]}>
        {/* A: the headline sits midway between the sheet's top and the button. */}
        {variant === 'B' ? null : <View style={{ flex: 1 }} />}
        {Headline}
        {Sub}
        <View style={{ flex: 1 }} />
        {variant === 'B' ? (
          <>
            <View style={s.center}>
              <LaurelStat value={`${content.rating} ★`} label="App Store rating" />
            </View>
            <View style={{ flex: 1 }} />
          </>
        ) : null}
        <OnbButton label="Get started" variant="brand" onPress={() => void start()} />
        <SignInLink onPress={signIn} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  fill: { flex: 1, backgroundColor: C.paper },
  colCenter: { alignItems: 'center', paddingHorizontal: 24 },
  stretch: { alignSelf: 'stretch' },
  center: { alignItems: 'center' },
  centerText: { textAlign: 'center' },
  photo: { position: 'absolute', top: 0, left: 0, right: 0, width: '100%' },
  badgeWrap: { position: 'absolute', right: 13, width: 176 },
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
  badgeKcal: { fontFamily: F.serif, fontSize: 30, lineHeight: 32, color: C.ink, fontVariant: ['tabular-nums'] },
  badgeUnit: { fontFamily: F.sans, fontSize: 14, color: C.muted },
  source: { alignSelf: 'flex-start', backgroundColor: C.infoSoft, borderRadius: 999, paddingVertical: 3, paddingHorizontal: 8 },
  sourceText: { fontFamily: F.mono, fontSize: 10, letterSpacing: 0.8, lineHeight: 14, color: C.info },
  sheet: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: C.paper,
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    paddingHorizontal: 24,
  },
  h1: { fontFamily: F.serif, fontSize: 34, lineHeight: 39, letterSpacing: -0.34, color: C.ink },
  h1Sheet: { fontFamily: F.serif, fontSize: 40, lineHeight: 45, letterSpacing: -0.4, color: C.ink, textAlign: 'center' },
  h1C: { fontFamily: F.serif, fontSize: 36, lineHeight: 41, letterSpacing: -0.36, color: C.terra },
  sub: { marginTop: 10, fontFamily: F.sans, fontSize: 17, lineHeight: 25, color: C.muted },
  linkWrap: { marginTop: 16, alignSelf: 'center' },
  link: { fontFamily: F.sans, fontSize: 15, lineHeight: 22, color: C.muted, textAlign: 'center' },
  linkStrong: { fontFamily: F.sansSemibold, color: C.ink },
  laurelRow: { flexDirection: 'row', alignItems: 'center' },
  laurelText: { alignItems: 'center', gap: 2 },
  stat: { fontFamily: F.serif, fontSize: 30, lineHeight: 32, color: C.ink, fontVariant: ['tabular-nums'] },
  statLabel: { fontFamily: F.sans, fontSize: 14, lineHeight: 18, color: C.muted },
  statBig: { fontFamily: F.serif, fontSize: 36, lineHeight: 38, color: C.ink, fontVariant: ['tabular-nums'] },
  statLabelBig: { fontFamily: F.sans, fontSize: 15, lineHeight: 20, color: C.muted },
  statsC: { marginTop: 48, gap: 28, alignItems: 'center' },
  brandRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  brand: { fontFamily: F.serif, fontSize: 26, lineHeight: 30, color: C.ink },
  phone: { width: 246, height: 506, padding: 9, backgroundColor: C.ink, borderRadius: 46 },
  phoneScreen: { flex: 1, borderRadius: 38, overflow: 'hidden', backgroundColor: C.ink },
  island: { position: 'absolute', left: 89, top: 18, width: 68, height: 20, borderRadius: 10, backgroundColor: C.ink },
});
