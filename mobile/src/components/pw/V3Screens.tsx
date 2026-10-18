/**
 * The V3 paywall screens, presentational only (state lives in `V3Paywall`):
 *   17 PW_B1        — trial timeline, "Try for free";
 *   18 PW_B2        — reminder bell (the push prompt is asked over it);
 *   19 PW_B3*       — photo + dark plan cards;
 *   P1 PW_P1_*      — demo clip in an iPhone frame;
 *   P1 PW_P1_plans  — light plan cards under the timeline.
 */
import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import type { AdaptyPaywallProduct } from 'react-native-adapty';
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

import { OnbButton } from '@/components/onb/OnbButton';
import { OnbLayout } from '@/components/onb/OnbLayout';
import { PW } from '@/onb/assets';
import { C, F } from '@/onb/theme';

import { B3_PHOTOS, P1_CLIPS, type Hero } from './copy';
import { PhotoStage } from './PhotoStage';
import { PlanCards } from './PlanCards';
import { LaurelRating, LegalRow, NoPayment, PhoneVideo, TrialTimeline } from './PwParts';

export function HeroText({
  hero,
  size,
  line,
  top,
  color = C.ink,
  lines,
}: {
  hero: Hero;
  size: number;
  line: number;
  top: number;
  color?: string;
  /** Keep to this many lines, shrinking the type a little if needed (P1's two drawn lines). */
  lines?: number;
}) {
  return (
    <Text
      style={[s.h1, { fontSize: size, lineHeight: line, marginTop: top, color }]}
      accessibilityRole="header"
      numberOfLines={lines}
      adjustsFontSizeToFit={lines !== undefined}
      minimumFontScale={0.85}
    >
      {hero.pre}
      {hero.accent ? <Text style={{ color: C.terra }}>{hero.accent}</Text> : null}
      {hero.post ?? ''}
    </Text>
  );
}

/** Footer of the light screens: "✓ No payment for now" (trial only), CTA, an optional line, legal links. */
function LightFooter({
  cta,
  onPress,
  disabled,
  hasTrial,
  note,
  onRestore,
}: {
  cta: string;
  onPress: () => void;
  disabled?: boolean;
  hasTrial: boolean;
  note?: string | null;
  onRestore: () => void;
}) {
  return (
    <View>
      {hasTrial ? <NoPayment /> : null}
      <OnbButton label={cta} onPress={onPress} variant="brand" disabled={disabled} style={{ marginTop: 14 }} />
      {note ? <Text style={s.note}>{note}</Text> : null}
      <LegalRow onRestore={onRestore} />
    </View>
  );
}

// ---- 17 · B1 ----------------------------------------------------------------

export function TrialIntro({
  hero,
  trialDays,
  todayLine,
  cta,
  onNext,
  onRestore,
}: {
  hero: Hero;
  trialDays: number;
  todayLine: string;
  cta: string;
  onNext: () => void;
  onRestore: () => void;
}) {
  // The timeline sits on a card and grows on tall iPhones: on its own it left
  // half the screen empty (phone test, 18 Oct).
  const { height } = useWindowDimensions();
  const tall = height >= 800;
  return (
    <OnbLayout
      progress={null}
      title={<HeroText hero={hero} size={tall ? 34 : 32} line={tall ? 40 : 38} top={44} />}
      footer={<LightFooter cta={cta} onPress={onNext} hasTrial onRestore={onRestore} />}
    >
      <View style={{ flex: 0.8 }} />
      <View style={[s.timelineCard, tall && s.timelineCardTall]}>
        <TrialTimeline trialDays={trialDays} todayLine={todayLine} large={tall} />
      </View>
      <View style={{ flex: 1 }} />
    </OnbLayout>
  );
}

// ---- 18 · B2 ----------------------------------------------------------------

/** A ring 14° → −12° → 8° → −5° → 0, then still for 1.5 s, on a loop (canvas `yy-ring`). */
function RingingBell() {
  const rot = useSharedValue(0);
  useEffect(() => {
    const e = Easing.inOut(Easing.ease);
    const ring = () =>
      withSequence(
        withTiming(14, { duration: 196, easing: e }),
        withTiming(-12, { duration: 224, easing: e }),
        withTiming(8, { duration: 224, easing: e }),
        withTiming(-5, { duration: 224, easing: e }),
        withTiming(0, { duration: 392, easing: e }),
      );
    // First ring right away (the canvas loop starts still for 1.5 s, and
    // people tap on before it moves), then the canvas rhythm.
    rot.value = withSequence(withDelay(250, ring()), withRepeat(withDelay(1540, ring()), -1));
    return () => cancelAnimation(rot);
  }, [rot]);
  const ring = useAnimatedStyle(() => ({ transform: [{ rotate: `${rot.value}deg` }] }));
  return (
    <View style={s.bellBox} accessibilityLabel="A bell" accessible>
      <Animated.Image source={PW.bell} style={[s.bell, ring]} />
      <View style={s.bellBadge}>
        <Text style={s.bellBadgeText}>1</Text>
      </View>
    </View>
  );
}

export function Reminder({
  title,
  cta,
  onBack,
  onNext,
  onRestore,
}: {
  title: string;
  cta: string;
  onBack: () => void;
  onNext: () => void;
  onRestore: () => void;
}) {
  return (
    <OnbLayout
      progress={null}
      backOnly
      onBack={onBack}
      title={<HeroText hero={{ pre: title }} size={30} line={37} top={28} />}
      footer={<LightFooter cta={cta} onPress={onNext} hasTrial onRestore={onRestore} />}
    >
      <View style={{ flex: 1 }} />
      <RingingBell />
      <View style={{ flex: 1.3 }} />
    </OnbLayout>
  );
}

// ---- P1 · demo clip ---------------------------------------------------------

/** The 216 × 444 phone, scaled down when a short screen has less room. */
function FittedPhone({ variant }: { variant: string }) {
  const clip = P1_CLIPS[variant] ?? P1_CLIPS.p1_photo;
  const [room, setRoom] = useState(0);
  const scale = room > 0 ? Math.min(1, (room - 8) / 444) : 1;
  return (
    <View style={s.phoneRoom} onLayout={(e) => setRoom(e.nativeEvent.layout.height)}>
      {room > 0 ? (
        <View style={{ width: 216 * scale, height: 444 * scale }}>
          <View
            style={{
              position: 'absolute',
              left: (216 * scale - 216) / 2,
              top: (444 * scale - 444) / 2,
              transform: [{ scale }],
            }}
          >
            <PhoneVideo video={clip.video} poster={clip.poster} />
          </View>
        </View>
      ) : null}
    </View>
  );
}

export function VideoIntro({
  variant,
  title,
  cta,
  priceLine,
  onNext,
  onRestore,
}: {
  variant: string;
  title: string;
  cta: string;
  priceLine: string | null;
  onNext: () => void;
  onRestore: () => void;
}) {
  return (
    <OnbLayout
      progress={null}
      title={<HeroText hero={{ pre: title }} size={30} line={36} top={20} lines={title.includes('\n') ? 2 : undefined} />}
      footer={<LightFooter cta={cta} onPress={onNext} hasTrial note={priceLine} onRestore={onRestore} />}
    >
      <FittedPhone variant={variant} />
    </OnbLayout>
  );
}

// ---- plans (shared) -----------------------------------------------------------

interface PlansProps {
  hero: Hero;
  products: AdaptyPaywallProduct[];
  selectedId: string | null;
  onSelect: (p: AdaptyPaywallProduct) => void;
  emphasis: 'design' | 'billed' | 'weekly';
  showRating: boolean;
  hasTrial: boolean;
  trialDays: number;
  /** "3 days free, then £49.99 per year" — shown only with `price_emphasis: billed`. */
  terms: string | null;
  cta: string;
  purchasing: boolean;
  onBuy: () => void;
  onRestore: () => void;
  onRetry: () => void;
}

function NoPlans({ onRetry, dark }: { onRetry: () => void; dark?: boolean }) {
  return (
    <View style={s.noPlans}>
      <Text style={[s.noPlansText, dark && { color: 'rgba(255,255,255,0.75)' }]}>
        We couldn’t load the plans. Check your connection and try again.
      </Text>
      <OnbButton label="Try again" onPress={onRetry} variant="brand" style={{ alignSelf: 'stretch', marginTop: 14 }} />
    </View>
  );
}

// ---- P1 · light plans ---------------------------------------------------------

export function LightPlans({
  canGoBack,
  onBack,
  todayLine,
  rating,
  users,
  ...p
}: PlansProps & { canGoBack: boolean; onBack: () => void; todayLine: string; rating: string; users: string }) {
  const none = p.products.length === 0;
  // iPhone SE and other short screens: the plan cards must stay in view.
  // Tall ones get the big timeline. Spare height is shared out between the
  // blocks (phone test, build 64: everything sat at the top over an empty band).
  const { height } = useWindowDimensions();
  const short = height < 700;
  const tall = height >= 840;
  return (
    <OnbLayout
      progress={null}
      backOnly
      canGoBack={canGoBack}
      onBack={onBack}
      title={<HeroText hero={p.hero} size={28} line={34} top={8} />}
      footer={
        none ? (
          <LegalRow onRestore={p.onRestore} />
        ) : (
          <LightFooter
            cta={p.cta}
            onPress={p.onBuy}
            disabled={p.purchasing}
            hasTrial={p.hasTrial}
            note={p.terms}
            onRestore={p.onRestore}
          />
        )
      }
    >
      <View style={s.chips}>
        {[...(p.showRating ? [`★ ${rating}`] : []), `${users} trackers`, '✓ Verified data'].map((c) => (
          <Text key={c} style={s.chip}>
            {c}
          </Text>
        ))}
      </View>
      <View style={{ flex: 1, minHeight: short ? 12 : 18 }} />
      {p.hasTrial ? <TrialTimeline trialDays={p.trialDays} todayLine={todayLine} compact={short} large={tall} /> : null}
      <View style={{ flex: 1, minHeight: 14 }} />
      <View>
        {none ? (
          <NoPlans onRetry={p.onRetry} />
        ) : (
          <PlanCards
            products={p.products}
            selectedId={p.selectedId}
            onSelect={p.onSelect}
            tone="light"
            emphasis={p.emphasis}
          />
        )}
      </View>
      <View style={{ flex: 1, minHeight: 16 }} />
    </OnbLayout>
  );
}

// ---- 19 · B3 photo plans ------------------------------------------------------

export function PhotoPlans({
  variant,
  title,
  rating,
  ...p
}: PlansProps & { variant: string; title: string; rating: string }) {
  const spec = B3_PHOTOS[variant] ?? B3_PHOTOS.b3_joe;
  const none = p.products.length === 0;
  return (
    <PhotoStage
      photo={spec.photo}
      badge={spec.badge}
      // Dark well before the headline (phone test, build 64: it sat on the bright photo).
      fade={{ top: 300, above: 190, below: 180, atBlock: 0.8 }}
      label={`A phone scanning a meal: ${spec.badge.title}, ${spec.badge.kcal} kcal`}
    >
      <Text style={s.darkH1} accessibilityRole="header">
        {title}
      </Text>
      {none ? (
        <NoPlans onRetry={p.onRetry} dark />
      ) : (
        <>
          <View style={{ marginTop: 20 }}>
            <PlanCards
              products={p.products}
              selectedId={p.selectedId}
              onSelect={p.onSelect}
              tone="dark"
              emphasis={p.emphasis}
            />
          </View>
          {p.terms ? <Text style={s.darkTerms}>{p.terms}</Text> : null}
          <OnbButton
            label={p.cta}
            onPress={p.onBuy}
            variant="brand"
            disabled={p.purchasing}
            style={{ marginTop: p.terms ? 10 : 16 }}
          />
        </>
      )}
      {p.showRating ? <LaurelRating rating={rating} /> : null}
      <LegalRow onRestore={p.onRestore} color="rgba(255,255,255,0.6)" style={p.showRating ? undefined : { marginTop: 14 }} />
    </PhotoStage>
  );
}

/** Spinner on the paywall's own background while a step needs products. */
export function PwLoading({ dark }: { dark?: boolean }) {
  return (
    <View style={[s.loading, { backgroundColor: dark ? C.ink : C.paper }]}>
      <ActivityIndicator color={dark ? C.white : C.terra} />
    </View>
  );
}

const s = StyleSheet.create({
  h1: { textAlign: 'center', fontFamily: F.serif, letterSpacing: -0.3, color: C.ink },
  note: { marginTop: 10, textAlign: 'center', fontFamily: F.sans, fontSize: 13, lineHeight: 18, color: C.muted },
  timelineCard: {
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.hair,
    borderRadius: 20,
    paddingTop: 18,
    paddingBottom: 4,
    paddingHorizontal: 12,
  },
  timelineCardTall: { paddingTop: 22, paddingBottom: 8, paddingHorizontal: 14 },
  bellBox: { alignSelf: 'center', width: 150, height: 150 },
  bell: { width: 150, height: 150, transformOrigin: '50% 12%' },
  // 30 pt + a 2 pt border outside it (CSS content-box), radius 15: a squircle.
  bellBadge: {
    position: 'absolute',
    right: 2,
    top: 4,
    width: 34,
    height: 34,
    borderRadius: 15,
    backgroundColor: C.terra,
    borderWidth: 2,
    borderColor: C.paper,
    alignItems: 'center',
    justifyContent: 'center',
  },
  bellBadgeText: { fontFamily: F.sansSemibold, fontSize: 15, lineHeight: 18, color: C.white },
  phoneRoom: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  chips: { marginTop: 14, flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 6 },
  chip: {
    borderWidth: 1,
    borderColor: C.hair,
    backgroundColor: C.surface,
    borderRadius: 999,
    overflow: 'hidden',
    paddingVertical: 4,
    paddingHorizontal: 10,
    fontFamily: F.sans,
    fontSize: 13,
    lineHeight: 18,
    color: C.muted,
  },
  noPlans: { alignItems: 'center', paddingVertical: 8 },
  noPlansText: { textAlign: 'center', fontFamily: F.sans, fontSize: 15, lineHeight: 21, color: C.muted },
  darkH1: {
    textAlign: 'center',
    fontFamily: F.serif,
    fontSize: 30,
    lineHeight: 36,
    letterSpacing: -0.3,
    color: C.white,
  },
  darkTerms: {
    marginTop: 12,
    textAlign: 'center',
    fontFamily: F.sans,
    fontSize: 13,
    lineHeight: 18,
    color: 'rgba(255,255,255,0.75)',
  },
  loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
});
