/**
 * V3 screen 16 — Social proof, then the system rating prompt.
 *
 * Hidden by default (`social_proof.show: false`) until real, consented reviews
 * exist; content comes only from `onb_content` (QA builds can use the bundled
 * demo). Hero by goal: before/after photos for lose / gain (test O4 can switch
 * to the text hero), the 5.0 rating for maintain / track. Below, a carousel of
 * reviews for the goal: auto-advances every 4 s, swipeable, the next card
 * peeks, dots show where you are. Continue asks for an App Store rating
 * (SKStoreReviewController — Apple decides whether it shows) and moves on.
 *
 * Slot: `social_proof.render: "flow"` shows the flow on `onb_social` instead
 * (custom actions `request_review` / `next`). No reviews for the goal → skip.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import { Image as ExpoImage } from 'expo-image';
import Svg, { Path } from 'react-native-svg';
import * as StoreReview from 'expo-store-review';
import { AdaptyFlowView } from 'react-native-adapty';
import type { AdaptyFlow } from 'react-native-adapty';

import { track } from '@/analytics/posthog';
import { captureException } from '@/analytics/sentry';
import { ADAPTY_PLACEMENT_SOCIAL_SLOT } from '@/billing/adapty';
import { handleFlowPermissionRequest, trackFlowAnalytics } from '@/billing/flowBridge';
import { OnbButton } from '@/components/onb/OnbButton';
import { OnbLayout } from '@/components/onb/OnbLayout';
import { Sticker } from '@/components/onb/Sticker';
import { getFlowQuiet } from '@/config/onboardingConfig';
import type { BeforeAfter, ContentGoal, Review } from '@/config/types';
import { IMG } from '@/onb/assets';
import { C, F, PAD } from '@/onb/theme';
import { useOnbScreen } from '@/onb/useOnbScreen';
import { useIntro } from '@/state/introContext';

const CARD_W = 318;
const CARD_GAP = 10;
const PAGE = CARD_W + CARD_GAP;
const AUTO_MS = 4000;
const GOAL_KEY: Record<string, ContentGoal> = { lose: 'lose', gain: 'gain', maintain: 'maintain', just_track: 'track' };

function Stars({ size }: { size: number }) {
  return (
    <View style={s.stars}>
      {[0, 1, 2, 3, 4].map((i) => (
        <Svg key={i} width={size} height={size} viewBox="0 0 24 24">
          <Path d="M12 2.5l2.9 6.1 6.6.8-4.9 4.6 1.3 6.6L12 17.3l-5.9 3.3 1.3-6.6-4.9-4.6 6.6-.8z" fill="#D9A441" />
        </Svg>
      ))}
    </View>
  );
}

function Photo({ uri, local, label }: { uri: string; local?: number; label: string }) {
  return (
    <View style={s.photo}>
      <ExpoImage
        source={local ?? { uri }}
        style={StyleSheet.absoluteFill}
        contentFit="cover"
        contentPosition={{ left: '50%', top: '22%' }}
        transition={150}
      />
      <View style={s.tag}>
        <Text style={s.tagText}>{label}</Text>
      </View>
    </View>
  );
}

function HeroBeforeAfter({ ba, photos }: { ba: BeforeAfter; photos: boolean }) {
  return (
    <View style={[s.card, s.baCard]}>
      {photos ? (
        <View style={s.photos}>
          <Photo uri={ba.before_url} local={ba.before_local} label="Before" />
          <Photo uri={ba.after_url} local={ba.after_local} label="After" />
        </View>
      ) : null}
      <View style={[s.baText, !photos && { paddingTop: 4 }]}>
        <Text style={s.baCaption}>{ba.caption}</Text>
        {ba.quote ? <Text style={s.baQuote}>“{ba.quote}”</Text> : null}
      </View>
    </View>
  );
}

function HeroRating({ rating }: { rating: string }) {
  return (
    <View style={[s.card, s.ratingCard]}>
      <View style={s.ratingRow}>
        <View style={s.mascotDisc}>
          <Sticker source={IMG.mascot_great} size={104} motion="bob" />
        </View>
        <View style={s.ratingText}>
          <Text style={s.ratingBig}>{rating}</Text>
          <Stars size={20} />
          <Text style={s.ratingLabel}>Average App Store rating</Text>
        </View>
      </View>
    </View>
  );
}

function ReviewCard({ r }: { r: Review }) {
  return (
    <View style={s.review}>
      <Stars size={16} />
      <Text style={s.reviewText}>“{r.text}”</Text>
      <Text style={s.reviewWho}>
        {r.name}
        {r.city ? `, ${r.city}` : ''}
      </Text>
    </View>
  );
}

function Carousel({ reviews }: { reviews: Review[] }) {
  const ref = useRef<ScrollView>(null);
  const [page, setPage] = useState(0);
  const pageRef = useRef(0);
  const dragging = useRef(false);
  const { width } = useWindowDimensions();
  // The first card is repeated at the end so the loop wraps without a jump back.
  const items = useMemo(() => (reviews.length > 1 ? [...reviews, reviews[0]] : reviews), [reviews]);

  useEffect(() => {
    if (reviews.length < 2) return;
    const id = setInterval(() => {
      if (dragging.current) return;
      const next = pageRef.current + 1;
      ref.current?.scrollTo({ x: next * PAGE, animated: true });
    }, AUTO_MS);
    return () => clearInterval(id);
  }, [reviews.length]);

  const onSettle = (x: number) => {
    let p = Math.round(x / PAGE);
    if (p >= reviews.length) {
      p = 0;
      ref.current?.scrollTo({ x: 0, animated: false });
    }
    pageRef.current = p;
    setPage(p);
  };

  return (
    <View style={{ marginHorizontal: -PAD.side, marginTop: 12 }}>
      <ScrollView
        ref={ref}
        horizontal
        showsHorizontalScrollIndicator={false}
        snapToInterval={PAGE}
        decelerationRate="fast"
        contentContainerStyle={{ paddingHorizontal: PAD.side, gap: CARD_GAP }}
        onScrollBeginDrag={() => {
          dragging.current = true;
        }}
        onScrollEndDrag={() => {
          dragging.current = false;
        }}
        onMomentumScrollEnd={(e) => onSettle(e.nativeEvent.contentOffset.x)}
        style={{ width }}
      >
        {items.map((r, i) => (
          <ReviewCard key={`${r.name}-${i}`} r={r} />
        ))}
      </ScrollView>
      {reviews.length > 1 ? (
        <View style={s.dots}>
          {reviews.map((r, i) => (
            <View key={`${r.name}-${i}`} style={[s.dot, i === page && s.dotOn]} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

export default function SocialScreen() {
  const intro = useIntro();
  const goal = GOAL_KEY[intro.goal_type ?? 'lose'];
  const { config, content, next } = useOnbScreen('S16_social', goal);
  const reviews = content.reviews[goal] ?? [];
  const ba = content.before_after[goal];
  const [slotFlow, setSlotFlow] = useState<AdaptyFlow | null>(null);
  const [slotDone, setSlotDone] = useState(config.social_proof.render !== 'flow');
  const skipped = useRef(false);

  useEffect(() => {
    if (config.social_proof.render !== 'flow') return;
    let alive = true;
    void getFlowQuiet(ADAPTY_PLACEMENT_SOCIAL_SLOT, 3000).then((flow) => {
      if (!alive) return;
      if (flow?.hasViewConfiguration) setSlotFlow(flow);
      else track('onboarding_slot_fallback', { slot: 'social', reason: flow ? 'no_view' : 'no_flow' });
      setSlotDone(true);
    });
    return () => {
      alive = false;
    };
  }, [config.social_proof.render]);

  const asked = useRef(false);
  /**
   * The rating prompt (SKStoreReviewController) comes up over this screen a
   * moment after it opens, as drawn (16 · Rating prompt) and as Cal AI does.
   * Apple decides whether it really shows (3 times a year at most).
   */
  const askForRating = async (source: string) => {
    if (asked.current) return;
    asked.current = true;
    try {
      if (!(await StoreReview.hasAction())) return;
      track('rating_prompt_requested', { source });
      await StoreReview.requestReview();
    } catch (e) {
      captureException(e, { where: 'v3_social_rating' });
    }
  };
  const finish = () => {
    next({}, { reviews: reviews.length, hero: ba ? config.social_proof.hero : 'rating' }, undefined, { replace: true });
  };

  useEffect(() => {
    if (!slotDone || slotFlow || reviews.length === 0) return;
    const t = setTimeout(() => void askForRating('native'), 2000);
    return () => clearTimeout(t);
     
  }, [slotDone, slotFlow, reviews.length]);

  // Nothing real to show for this goal: skip the screen rather than show an empty one.
  useEffect(() => {
    if (slotDone && !slotFlow && reviews.length === 0 && !skipped.current) {
      skipped.current = true;
      track('onboarding_screen_skipped', { screen: 'S16_social', reason: 'no_reviews', goal });
      next({}, {}, undefined, { replace: true });
    }
  }, [goal, next, reviews.length, slotDone, slotFlow]);

  if (!slotDone || (!slotFlow && reviews.length === 0)) return <View style={s.blank} />;

  if (slotFlow) {
    const ctx = { placement: ADAPTY_PLACEMENT_SOCIAL_SLOT, variation: slotFlow.variationId, variationName: slotFlow.variationName };
    return (
      <AdaptyFlowView
        flow={slotFlow}
        style={s.blank}
        onAnalytics={(name, params) => {
          trackFlowAnalytics(ctx, name, params);
          return false;
        }}
        onCustomAction={(actionId) => {
          if (actionId === 'request_review') void askForRating('slot');
          else if (actionId === 'next') next({}, {}, undefined, { replace: true });
          return false;
        }}
        onCloseButtonPress={() => {
          next({}, {}, undefined, { replace: true });
          return false;
        }}
        onRequestPermission={handleFlowPermissionRequest}
        onError={(error) => {
          captureException(error, { placement: ADAPTY_PLACEMENT_SOCIAL_SLOT });
          setSlotFlow(null);
          return false;
        }}
      />
    );
  }

  const photoHero = ba && (goal === 'lose' || goal === 'gain');
  return (
    <OnbLayout
      progress={null}
      backOnly
      title="People like you are already doing it"
      footer={<OnbButton label="Continue" onPress={finish} />}
      contentStyle={{ marginTop: 22 }}
    >
      {photoHero && ba ? (
        <HeroBeforeAfter ba={ba} photos={config.social_proof.hero === 'before_after'} />
      ) : (
        <HeroRating rating={content.rating} />
      )}
      <Carousel reviews={reviews} />
      <View style={{ flex: 1 }} />
    </OnbLayout>
  );
}

const s = StyleSheet.create({
  blank: { flex: 1, backgroundColor: C.paper },
  card: { backgroundColor: C.surface, borderWidth: 1, borderColor: C.hair, borderRadius: 16 },
  baCard: { padding: 12 },
  photos: { flexDirection: 'row', gap: 8 },
  photo: { flex: 1, height: 196, borderRadius: 10, overflow: 'hidden', backgroundColor: C.paper2 },
  tag: {
    position: 'absolute',
    left: 10,
    top: 10,
    backgroundColor: 'rgba(255,253,249,0.92)',
    borderRadius: 999,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  tagText: { fontFamily: F.sansSemibold, fontSize: 12, lineHeight: 16, color: C.ink },
  baText: { paddingTop: 12, paddingHorizontal: 4, paddingBottom: 2, gap: 2 },
  baCaption: { fontFamily: F.sansSemibold, fontSize: 16, lineHeight: 22, color: C.ink },
  baQuote: { fontFamily: F.sans, fontSize: 14, lineHeight: 20, color: C.muted },
  ratingCard: { padding: 20 },
  ratingRow: { flexDirection: 'row', alignItems: 'center', gap: 18 },
  mascotDisc: {
    width: 112,
    height: 112,
    borderRadius: 56,
    backgroundColor: C.terraSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ratingText: { gap: 6 },
  ratingBig: { fontFamily: F.serif, fontSize: 48, lineHeight: 52, color: C.ink, fontVariant: ['tabular-nums'] },
  ratingLabel: { fontFamily: F.sans, fontSize: 14, lineHeight: 20, color: C.muted },
  stars: { flexDirection: 'row', gap: 2 },
  review: {
    width: CARD_W,
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.hair,
    borderRadius: 16,
    padding: 16,
  },
  reviewText: { marginTop: 8, fontFamily: F.sans, fontSize: 15, lineHeight: 22, color: C.ink },
  reviewWho: { marginTop: 'auto', paddingTop: 8, fontFamily: F.sans, fontSize: 13, lineHeight: 18, color: C.muted },
  dots: { marginTop: 12, flexDirection: 'row', justifyContent: 'center', gap: 6 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: C.hair2 },
  dotOn: { width: 18, backgroundColor: C.terra },
});
