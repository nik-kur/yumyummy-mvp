/**
 * V3 paywall in code (17–19), one `pw_main` arm:
 *   b3_*  → B1 (trial timeline) → B2 (reminder + push prompt) → B3 photo plans;
 *   p1_*  → P1 (demo clip)      → B2                          → light plans.
 *
 * B1, P1 and B2 only make sense with a free trial, so the first plan with no
 * trial for this customer (already used it), a signed-in entry or no products
 * at all go straight to the plans. The plan cards are whatever products the
 * arm's flow carries (1–3), so price and trial tests need no release.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { View } from 'react-native';
import type { AdaptyPaywallProduct } from 'react-native-adapty';
import Animated, { FadeIn } from 'react-native-reanimated';

import { track } from '@/analytics/posthog';
import { defaultPlan, justPerYear, periodOf, trialDays, trialThenPrice } from '@/billing/v3Pricing';
import { getOnboardingContent } from '@/config/onboardingConfig';
import type { PaywallArmConfig } from '@/config/types';
import { requestPermission as requestPushPermission } from '@/notifications/scheduler';
import { C } from '@/onb/theme';
import type { IntroDraft } from '@/state/introDraft';

import { heroTitle, type Hero } from './copy';
import { LightPlans, PhotoPlans, Reminder, TrialIntro, VideoIntro } from './V3Screens';

export type PwStep = 'b1' | 'p1' | 'b2' | 'plans';

/** Wait a beat so B2 is on screen before the system alert covers it. */
const PUSH_PROMPT_DELAY_MS = 600;

interface Props {
  config: PaywallArmConfig;
  /** Sorted shortest period first; empty = the plans step offers a retry. */
  products: AdaptyPaywallProduct[];
  /** Intro answers for the headline; `null` for signed-in entries. */
  draft: IntroDraft | null;
  /** Profile / signed-in gate: straight to the plans. */
  plansOnly: boolean;
  purchasing: boolean;
  onPurchase: (p: AdaptyPaywallProduct) => void;
  onRestore: () => void;
  onRetry: () => void;
}

export function V3Paywall({ config, products, draft, plansOnly, purchasing, onPurchase, onRestore, onRetry }: Props) {
  const isP1 = config.variant.startsWith('p1_');
  const copy = config.copy;
  const content = getOnboardingContent();

  const [selectedId, setSelectedId] = useState<string | null>(() => defaultPlan(products)?.vendorProductId ?? null);
  useEffect(() => {
    setSelectedId((cur) =>
      cur && products.some((p) => p.vendorProductId === cur) ? cur : defaultPlan(products)?.vendorProductId ?? null,
    );
  }, [products]);
  const selected = products.find((p) => p.vendorProductId === selectedId) ?? defaultPlan(products);
  const days = trialDays(selected);
  const hasTrial = days > 0;

  // Decided once per visit from the default plan, so picking a card later
  // never changes which screens were shown.
  const [steps] = useState<PwStep[]>(() => {
    const introTrial = trialDays(defaultPlan(products)) > 0;
    if (plansOnly || products.length === 0 || !introTrial) return ['plans'];
    return isP1 ? ['p1', 'b2', 'plans'] : ['b1', 'b2', 'plans'];
  });
  const [index, setIndex] = useState(0);
  const step = steps[index];
  // B1 / P1 and B2 put their button in the same place: a double tap must not
  // skip B2 (and its push prompt), so a step ignores taps for its first beat.
  const stepShownAt = useRef(Date.now());
  useEffect(() => {
    stepShownAt.current = Date.now();
  }, [index]);
  const next = useCallback(() => setIndex((i) => Math.min(i + 1, steps.length - 1)), [steps.length]);
  const back = useCallback(() => setIndex((i) => Math.max(i - 1, 0)), []);

  // Once per step shown (products loading later must not log it again).
  const productCount = useRef(products.length);
  productCount.current = products.length;
  useEffect(() => {
    track('paywall_step_viewed', {
      step,
      variant: config.variant,
      step_index: index,
      steps: steps.join('>'),
      products: productCount.current,
    });
  }, [step, index, steps, config.variant]);

  // B2: ask for push on arrival, once per visit — the reminder it promises
  // only fires with permission. Declined before = iOS answers without a prompt.
  // If B2's button wins the race, the button asks first.
  const pushAsked = useRef(false);
  const askPush = useCallback(async () => {
    if (pushAsked.current) return;
    pushAsked.current = true;
    const granted = await requestPushPermission();
    track('paywall_push_permission', { granted, variant: config.variant });
  }, [config.variant]);
  useEffect(() => {
    if (step !== 'b2') return;
    const t = setTimeout(() => void askPush(), PUSH_PROMPT_DELAY_MS);
    return () => clearTimeout(t);
  }, [step, askPush]);

  const hero: Hero = useMemo(() => {
    if (copy.b1_title) return { pre: copy.b1_title };
    return heroTitle(draft, hasTrial);
  }, [copy.b1_title, draft, hasTrial]);

  const onSelect = useCallback(
    (p: AdaptyPaywallProduct) => {
      setSelectedId(p.vendorProductId);
      track('paywall_plan_selected', { product: p.vendorProductId, variant: config.variant, renderer: 'v3', step });
    },
    [config.variant, step],
  );

  const onBuy = useCallback(() => {
    if (selected) onPurchase(selected);
  }, [onPurchase, selected]);

  const onIntroCta = useCallback(async () => {
    if (Date.now() - stepShownAt.current < 450) return;
    track('paywall_cta_tapped', { step, variant: config.variant });
    if (step === 'b2') await askPush();
    next();
  }, [askPush, config.variant, next, step]);

  // Trial terms with the billed amount (`billed`, the default; App Review 3.1.2(c)).
  const terms = config.price_emphasis === 'billed' && selected && hasTrial ? trialThenPrice(selected) : null;

  const plans = {
    hero: copy.plans_title ? { pre: copy.plans_title } : heroTitle(draft, hasTrial),
    products,
    selectedId: selected?.vendorProductId ?? null,
    onSelect,
    emphasis: config.price_emphasis,
    showRating: config.show_rating,
    hasTrial,
    trialDays: days,
    terms,
    cta: copy.plans_cta ?? (isP1 ? (hasTrial ? `Start my ${days}-day free trial` : 'Continue') : 'Continue'),
    purchasing,
    onBuy,
    onRestore,
    onRetry,
  };

  let screen;
  if (step === 'b1') {
    screen = (
      <TrialIntro
        hero={hero}
        trialDays={days}
        todayLine={copy.b1_today ?? 'Unlock AI food calorie tracking'}
        cta={copy.b1_cta ?? 'Try for free'}
        onNext={() => void onIntroCta()}
        onRestore={onRestore}
      />
    );
  } else if (step === 'p1') {
    const yearly = products.find((p) => periodOf(p) === 'year') ?? selected;
    screen = (
      <VideoIntro
        variant={config.variant}
        title={copy.p1_title ?? 'We want you to\ntry YumYummy for free.'}
        cta={copy.p1_cta ?? 'Try for free'}
        priceLine={yearly ? justPerYear(yearly) : null}
        onNext={() => void onIntroCta()}
        onRestore={onRestore}
      />
    );
  } else if (step === 'b2') {
    screen = (
      <Reminder
        title={copy.b2_title ?? 'We’ll send you a reminder before your free trial ends'}
        cta={copy.b2_cta ?? 'Continue for FREE'}
        onBack={back}
        onNext={() => void onIntroCta()}
        onRestore={onRestore}
      />
    );
  } else if (isP1) {
    screen = (
      <LightPlans
        {...plans}
        canGoBack={index > 0}
        onBack={back}
        todayLine={copy.plans_today ?? 'Unlock photo, voice and text logging with verified sources'}
        rating={content.rating}
        users={content.users}
      />
    );
  } else {
    screen = (
      <PhotoPlans
        {...plans}
        variant={config.variant}
        title={copy.plans_title ?? (hasTrial ? 'Reach your goal.\nStart for FREE today.' : 'Reach your goal.\nStart today.')}
        rating={content.rating}
      />
    );
  }

  const dark = step === 'plans' && !isP1;
  return (
    <View style={{ flex: 1, backgroundColor: dark ? C.ink : C.paper }}>
      <Animated.View key={step} entering={FadeIn.duration(220)} style={{ flex: 1 }}>
        {screen}
      </Animated.View>
    </View>
  );
}
