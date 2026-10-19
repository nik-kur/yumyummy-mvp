/**
 * QA builds only: walk every V3 screen and state on its own, so screenshots
 * can be taken on several simulator sizes without anyone tapping.
 *
 * Switched on by the QA override `auto_tour: true` (written into the app's
 * storage before launch). Each step applies its overrides and setup, opens
 * its screen, and records `{ i, name }` under `@yy_qa_autotour`; a script
 * outside watches that key and takes the screenshot. `auto_tour_only` runs
 * just the named steps.
 */
import { useEffect, useRef } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { router } from 'expo-router';

import * as api from '@/api/endpoints';
import { loadQaOverrides, saveQaOverrides, type QaOverrides } from '@/config/qa';
import { grantAIConsent } from '@/state/aiConsent';
import { useAuth } from '@/state/auth';
import { loadDraft, notifyDraftReplaced, saveDraft, type IntroDraft } from '@/state/introDraft';
import { startJourney } from '@/state/journey';
import { resetTour, setTourStep, startPostPurchase, type TourStep } from '@/state/tour';

const STATE_KEY = '@yy_qa_autotour';
const START_DELAY_MS = 7000;
const HOLD_MS = 4500;

/** `draft` swaps answers in (on top of the draft the tour started with); `draft_reset` puts that draft back. */
type Setup =
  | 'preview'
  | 'signin'
  | 'consent'
  | 'meal'
  | 'payoff'
  | 'draft_reset'
  | { tour: TourStep }
  | { draft: Partial<IntroDraft> };

interface Step {
  name: string;
  route: string;
  overrides?: QaOverrides;
  setup?: Setup[];
  push?: boolean;
  hold?: number;
}

const STEPS: Step[] = [
  { name: 'welcome_A', route: '/(intro)/v3', overrides: { onboarding: { welcome: { variant: 'A' } } } },
  { name: 'welcome_B', route: '/(intro)/v3', overrides: { onboarding: { welcome: { variant: 'B' } } } },
  { name: 'welcome_C', route: '/(intro)/v3', overrides: { onboarding: { welcome: { variant: 'C' } } } },
  { name: 'welcome_D', route: '/(intro)/v3', overrides: { onboarding: { welcome: { variant: 'D' } } }, hold: 5000 },
  { name: 'goal', route: '/(intro)/v3/goal' },
  { name: 'reflect', route: '/(intro)/v3/reflect' },
  { name: 'source', route: '/(intro)/v3/source' },
  { name: 'gender', route: '/(intro)/v3/gender' },
  { name: 'age', route: '/(intro)/v3/age' },
  { name: 'body', route: '/(intro)/v3/body' },
  { name: 'activity', route: '/(intro)/v3/activity' },
  { name: 'target', route: '/(intro)/v3/target' },
  { name: 'goal_check', route: '/(intro)/v3/goal-check' },
  { name: 'pace', route: '/(intro)/v3/pace' },
  // Thumb asked past the fastest pace the calorie floor allows: it stops there.
  { name: 'pace_limit', route: '/(intro)/v3/pace', setup: [{ draft: { pace_kg_week: 0.9 } }] },
  // A small, older, sedentary body: even 0.1 kg a week is under the floor.
  {
    name: 'pace_capped',
    route: '/(intro)/v3/pace',
    setup: [{ draft: { gender: 'female', age: 62, height_cm: 155, weight_kg: 52, activity_level: 'sedentary', target_weight_kg: 49 } }],
  },
  { name: 'proof', route: '/(intro)/v3/proof', setup: ['draft_reset'] },
  { name: 'tracked', route: '/(intro)/v3/tracked' },
  { name: 'barriers', route: '/(intro)/v3/barriers' },
  { name: 'features', route: '/(intro)/v3/features' },
  { name: 'loader', route: '/(intro)/v3/loader', hold: 3000 },
  { name: 'loader_review', route: '/(intro)/v3/loader', overrides: { onboarding: { loader_review: true }, content: 'demo' }, hold: 3000 },
  { name: 'plan', route: '/(intro)/v3/plan' },
  { name: 'plan_ahead', route: '/(intro)/v3/plan', overrides: { onboarding: { plan: 'ahead' } } },
  { name: 'social', route: '/(intro)/v3/social', overrides: { onboarding: { social_proof: { show: true } }, content: 'demo' } },
  { name: 'social_text', route: '/(intro)/v3/social', overrides: { onboarding: { social_proof: { show: true, hero: 'text' } }, content: 'demo' } },
  { name: 'pw_b1', route: '/paywall', hold: 5000 },
  { name: 'pw_b2', route: '/paywall?qa_step=b2', hold: 5000 },
  { name: 'pw_plans', route: '/paywall?qa_step=plans', hold: 5000 },
  { name: 'pw_plans_wide_design', route: '/paywall?qa_step=plans', overrides: { paywall: { render: 'native', variant: 'b3_wide', price_emphasis: 'design' } }, hold: 5000 },
  { name: 'pw_p1', route: '/paywall', overrides: { paywall: { render: 'native', variant: 'p1_photo' } }, hold: 5000 },
  { name: 'pw_p1_plans', route: '/paywall?qa_step=plans', overrides: { paywall: { render: 'native', variant: 'p1_photo' } }, hold: 5000 },
  // P1's video first, the photo plans third (`plans` key).
  { name: 'pw_p1_b3_plans', route: '/paywall?qa_step=plans', overrides: { paywall: { render: 'native', variant: 'p1_photo', plans: 'b3_joe' } }, hold: 5000 },
  { name: 'offer', route: '/paywall?qa_offer=1', hold: 6000 },
  { name: 'offer_closeup_design', route: '/paywall?qa_offer=1', overrides: { offer: { render: 'native', variant: 'closeup', price_emphasis: 'design' } }, hold: 6000 },
  { name: 'success', route: '/success' },
  { name: 'save_plan', route: '/save-plan' },
  { name: 'preview_today', route: '/(tabs)', setup: ['preview'], hold: 5000 },
  { name: 'last_offer', route: '/paywall?last_offer=1', hold: 6000 },
  { name: 'tour_1', route: '/(tabs)', setup: ['signin', 'consent', { tour: 1 }], hold: 5000 },
  { name: 'tour_2', route: '/(tabs)', setup: [{ tour: 2 }], hold: 5000 },
  { name: 'tour_3', route: '/capture', setup: [{ tour: 3 }], push: true, hold: 5000 },
  { name: 'tour_4', route: '/(tabs)', setup: [{ tour: 4 }, 'meal'], hold: 6000 },
  { name: 'tour_5', route: '/(tabs)', setup: [{ tour: 5 }], hold: 5000 },
  { name: 'tour_6', route: '/(tabs)', setup: [{ tour: 6 }], hold: 5000 },
  { name: 'payoff', route: '/(tabs)', setup: ['payoff'], hold: 5000 },
];

/** What every step starts from: V3 screens in code, no system prompts, no StoreKit. */
const BASE: QaOverrides = {
  auto_tour: true,
  mock_purchase: true,
  onboarding: { att: 'welcome' },
  paywall: { render: 'native' },
  offer: { render: 'native' },
};

function withBase(o: QaOverrides = {}): QaOverrides {
  return {
    ...BASE,
    ...o,
    onboarding: { ...BASE.onboarding, ...(o.onboarding ?? {}) },
    paywall: { ...BASE.paywall, ...(o.paywall ?? {}) },
    offer: { ...BASE.offer, ...(o.offer ?? {}) },
  };
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function QaAutoTour() {
  const { startPreview, signInWithProvider } = useAuth();
  const auth = useRef({ startPreview, signInWithProvider });
  auth.current = { startPreview, signInWithProvider };

  useEffect(() => {
    let alive = true;
    void (async () => {
      const qa = await loadQaOverrides();
      if (!qa.auto_tour) return;
      const only = qa.auto_tour_only;
      const original = await loadDraft();
      await wait(START_DELAY_MS);
      for (let i = 0; i < STEPS.length && alive; i += 1) {
        const step = STEPS[i];
        if (only && !only.includes(step.name)) continue;
        try {
          await saveQaOverrides({ ...withBase(step.overrides), auto_tour_only: only });
          for (const s of step.setup ?? []) {
            if (s === 'preview') await auth.current.startPreview();
            else if (s === 'signin') {
              await auth.current.signInWithProvider('apple');
              // The first-week card (step 6) exists from the purchase on.
              await startJourney();
            }
            else if (s === 'consent') await grantAIConsent();
            else if (s === 'meal') await api.agentRun({ text: 'Greek salad' });
            else if (s === 'payoff') await startPostPurchase(false);
            else if (s === 'draft_reset' || 'draft' in s) {
              await saveDraft(s === 'draft_reset' ? original : { ...original, ...s.draft });
              notifyDraftReplaced();
              // Screens read the draft from context: let the reload land first.
              await wait(400);
            } else {
              if (s.tour === 1) await resetTour(true);
              await setTourStep(s.tour);
            }
          }
          if (router.canDismiss()) router.dismissAll();
          if (step.push) router.push(step.route as never);
          else router.replace(step.route as never);
        } catch {
          // A step that cannot be reached still gets its (failed) screenshot.
        }
        await AsyncStorage.setItem(STATE_KEY, JSON.stringify({ i, name: step.name, at: Date.now() })).catch(() => {});
        await wait(step.hold ?? HOLD_MS);
      }
      await AsyncStorage.setItem(STATE_KEY, JSON.stringify({ i: -1, name: 'done', at: Date.now() })).catch(() => {});
    })();
    return () => {
      alive = false;
    };
  }, []);

  return null;
}
