/**
 * V3 onboarding path: screen order, branching and the progress bar.
 *
 *   1 Welcome → 2 Goal → 3 Reflect → 4 Source → 5 Gender → Age → Body
 *   → 6 Activity → 7 Target weight → goal check (realistic / ambitious /
 *   healthy) → Pace (only if the weight should move) → 8 Proof 2×
 *   → 9 Tracked before → 10 Barriers (only after "yes") → 12 Features
 *   (unless `features: off`) → 14 Loader (+ ATT) → 15 Plan → 16 Social proof
 *   (only if `social_proof.show`) → paywall.
 *
 * Every screen asks `nextScreen` where to go, so a branch rule lives in one
 * place. Screen ids double as PostHog `screen` values.
 */
import type { ContentGoal, OnboardingConfig, OnboardingContent } from '@/config/types';
import type { IntroDraft } from '@/state/introDraft';

import { direction, goalCheck } from './plan';

export type ScreenId =
  | 'S1_welcome'
  | 'S2_goal'
  | 'S3_reflect'
  | 'S4_source'
  | 'S5_gender'
  | 'S5_age'
  | 'S5_body'
  | 'S6_activity'
  | 'S7_target'
  | 'S7_goal_check'
  | 'S7_pace'
  | 'S8_proof'
  | 'S9_tracked'
  | 'S10_barriers'
  | 'S12_features'
  | 'S14_loader'
  | 'S15_plan'
  | 'S16_social';

const ROUTES: Record<ScreenId, string> = {
  S1_welcome: '/(intro)/v3',
  S2_goal: '/(intro)/v3/goal',
  S3_reflect: '/(intro)/v3/reflect',
  S4_source: '/(intro)/v3/source',
  S5_gender: '/(intro)/v3/gender',
  S5_age: '/(intro)/v3/age',
  S5_body: '/(intro)/v3/body',
  S6_activity: '/(intro)/v3/activity',
  S7_target: '/(intro)/v3/target',
  S7_goal_check: '/(intro)/v3/goal-check',
  S7_pace: '/(intro)/v3/pace',
  S8_proof: '/(intro)/v3/proof',
  S9_tracked: '/(intro)/v3/tracked',
  S10_barriers: '/(intro)/v3/barriers',
  S12_features: '/(intro)/v3/features',
  S14_loader: '/(intro)/v3/loader',
  S15_plan: '/(intro)/v3/plan',
  S16_social: '/(intro)/v3/social',
};

export const PAYWALL_ROUTE = '/paywall';

/** Progress bar fill from the canvas (15 steps of the quiz, ≈ 6.67 % each). */
export const PROGRESS: Partial<Record<ScreenId, number>> = {
  S2_goal: 7,
  S3_reflect: 13,
  S4_source: 20,
  S5_gender: 27,
  S5_age: 33,
  S5_body: 40,
  S6_activity: 47,
  S7_target: 53,
  S7_goal_check: 60,
  S7_pace: 67,
  S8_proof: 73,
  S9_tracked: 80,
  S10_barriers: 87,
  S12_features: 93,
};

export function routeOf(id: ScreenId): string {
  return ROUTES[id];
}

function weightMoves(d: IntroDraft): boolean {
  return d.target_weight_kg !== null && direction(d.weight_kg, d.target_weight_kg) !== 'same';
}

function belowHealthy(d: IntroDraft): boolean {
  return d.target_weight_kg !== null && goalCheck(d.weight_kg, d.target_weight_kg, d.height_cm) === 'healthy';
}

/** Where to go after `current`, given the answers so far and the arm's config. */
const CONTENT_GOAL: Record<string, ContentGoal> = { lose: 'lose', gain: 'gain', maintain: 'maintain', just_track: 'track' };

/** Screen 16 needs reviews for this goal unless a Flow Builder slot draws it. */
function hasSocialContent(d: IntroDraft, c: OnboardingConfig, content?: OnboardingContent): boolean {
  if (c.social_proof.render === 'flow') return true;
  if (!content) return true;
  return (content.reviews[CONTENT_GOAL[d.goal_type ?? 'lose']] ?? []).length > 0;
}

export function nextScreen(current: ScreenId, d: IntroDraft, c: OnboardingConfig, content?: OnboardingContent): string {
  const order: ScreenId[] = [
    'S1_welcome',
    'S2_goal',
    'S3_reflect',
    'S4_source',
    'S5_gender',
    'S5_age',
    'S5_body',
    'S6_activity',
    'S7_target',
    'S7_goal_check',
    'S7_pace',
    'S8_proof',
    'S9_tracked',
    'S10_barriers',
    'S12_features',
    'S14_loader',
    'S15_plan',
    'S16_social',
  ];
  const skip = (id: ScreenId): boolean => {
    switch (id) {
      case 'S7_goal_check':
        // Below a healthy BMI is always caught, even when the weight barely moves.
        return !weightMoves(d) && !belowHealthy(d);
      case 'S7_pace':
        return !weightMoves(d);
      case 'S10_barriers':
        return d.tracked_before !== true;
      case 'S12_features':
        return c.features === 'off';
      case 'S16_social':
        return !c.social_proof.show || !hasSocialContent(d, c, content);
      default:
        return false;
    }
  };
  for (let i = order.indexOf(current) + 1; i < order.length; i += 1) {
    if (!skip(order[i])) return ROUTES[order[i]];
  }
  return PAYWALL_ROUTE;
}
