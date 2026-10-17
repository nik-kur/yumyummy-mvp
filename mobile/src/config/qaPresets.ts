/**
 * QA builds only: ready-made quiz answers, so any V3 screen can be opened
 * with a known path (goal × weight direction × tracked before) in one tap.
 */
import { DEFAULT_DRAFT, type IntroDraft } from '@/state/introDraft';

import type { QaOverrides } from './qa';

const BASE: IntroDraft = {
  ...DEFAULT_DRAFT,
  goal_type: 'lose',
  gender: 'female',
  age: 32,
  height_cm: 165,
  weight_kg: 72,
  activity_level: 'light',
  source: 'instagram',
  units: 'metric',
  tracked_before: true,
  barrier: 'too_long',
  pain_points: ['too_long'],
  target_weight_kg: 66,
  pace_kg_week: 0.5,
};

export const QA_PRESETS: { key: string; label: string; draft: IntroDraft }[] = [
  { key: 'lose', label: 'lose 72→66, tracked: too long', draft: BASE },
  { key: 'lose_amb', label: 'lose 72→57 ambitious, no', draft: { ...BASE, target_weight_kg: 57, tracked_before: false, barrier: null, pain_points: [] } },
  { key: 'lose_low', label: 'lose 72→49 (BMI < 18.5)', draft: { ...BASE, target_weight_kg: 49 } },
  { key: 'gain', label: 'gain 75→79, no', draft: { ...BASE, goal_type: 'gain', gender: 'male', weight_kg: 75, height_cm: 180, target_weight_kg: 79, pace_kg_week: 0.25, tracked_before: false, barrier: null, pain_points: [] } },
  { key: 'recomp', label: 'gain, same weight (recomp)', draft: { ...BASE, goal_type: 'gain', gender: 'male', weight_kg: 75, height_cm: 180, target_weight_kg: 75, pace_kg_week: null, tracked_before: false, barrier: null, pain_points: [] } },
  { key: 'maintain', label: 'maintain, same weight', draft: { ...BASE, goal_type: 'maintain', target_weight_kg: 72, pace_kg_week: null, tracked_before: false, barrier: null, pain_points: [] } },
  { key: 'track', label: 'just track, yes: eating out', draft: { ...BASE, goal_type: 'just_track', target_weight_kg: 72, pace_kg_week: null, barrier: 'eating_out', pain_points: ['eating_out'] } },
  { key: 'imperial', label: 'lose, imperial units', draft: { ...BASE, units: 'imperial' } },
];

/** One-tap scenarios: a screen plus the overrides it needs. */
export const QA_SCENARIOS: { label: string; route: string; overrides: QaOverrides }[] = [
  { label: 'Welcome B', route: '/(intro)/v3', overrides: { onboarding: { welcome: { variant: 'B' } } } },
  { label: 'Welcome C', route: '/(intro)/v3', overrides: { onboarding: { welcome: { variant: 'C' } } } },
  { label: 'Welcome D', route: '/(intro)/v3', overrides: { onboarding: { welcome: { variant: 'D' } } } },
  { label: 'Loader + review', route: '/(intro)/v3/loader', overrides: { onboarding: { loader_review: true }, content: 'demo' } },
  { label: 'Plan ahead', route: '/(intro)/v3/plan', overrides: { onboarding: { plan: 'ahead' } } },
  { label: 'Social (demo)', route: '/(intro)/v3/social', overrides: { onboarding: { social_proof: { show: true } }, content: 'demo' } },
  { label: 'Social text hero', route: '/(intro)/v3/social', overrides: { onboarding: { social_proof: { show: true, hero: 'text' } }, content: 'demo' } },
];

export const QA_SCREENS: { label: string; route: string }[] = [
  { label: 'Welcome', route: '/(intro)/v3' },
  { label: 'Target', route: '/(intro)/v3/target' },
  { label: 'Goal check', route: '/(intro)/v3/goal-check' },
  { label: 'Pace', route: '/(intro)/v3/pace' },
  { label: 'Features', route: '/(intro)/v3/features' },
  { label: 'Loader', route: '/(intro)/v3/loader' },
  { label: 'Plan', route: '/(intro)/v3/plan' },
  { label: 'Social', route: '/(intro)/v3/social' },
  { label: 'Paywall', route: '/paywall' },
  { label: 'Offer', route: '/paywall?qa_offer=1' },
  { label: 'Success', route: '/success' },
  { label: 'Save plan', route: '/save-plan' },
];
