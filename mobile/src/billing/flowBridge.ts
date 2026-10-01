/**
 * Bridge between Adapty flows (Flow & Paywall Builder, rendered by the SDK)
 * and the app's own state and analytics.
 *
 * The contract with the flow designed in the dashboard lives here and nowhere
 * else. A flow can be swapped, re-ordered or A/B-tested without a release as
 * long as it keeps these ids:
 *
 *   Quiz inputs (element / group `customId` → intro draft field)
 *     goal          single choice: lose | maintain | gain | just_track
 *     gender        single choice: male | female
 *     age           number input, years (14–99)
 *     height_cm     number input                ┐ metric pair
 *     weight_kg     number input                ┘
 *     height_ft + height_in, weight_lb          imperial pair (optional)
 *     activity      single choice: sedentary | light | moderate | active | very_active
 *     pain_points   multi choice: too_long | gave_up | accuracy | eating_out | first_time
 *
 *   Custom actions (button "Custom action" → Action ID)
 *     quiz_done     the quiz is over; the app takes over (target & pace, plan)
 *     sign_in       "Already have an account?" → native sign-in
 *     request_att   ask App Tracking Transparency now (also reachable through
 *                   the builder's own "request permission: tracking" action)
 *
 *   Custom tags the app fills in (`<TAG/>` tokens in flow text)
 *     HERO_LINE (resolved per goal), TARGET_WEIGHT, TARGET_DATE, DAILY_KCAL,
 *     RATING, USERS, GOAL
 *
 * Screen ids should follow the native funnel naming (`S2_goal`, `N3_plan_reveal`)
 * so PostHog funnels keep reading the same event names either way.
 */
import type { AdaptyPermission, FlowPermissionResponse } from 'react-native-adapty';

import { track } from '@/analytics/posthog';
import { requestTrackingConsent } from '@/analytics/attribution';
import { requestPermission as requestPushPermission } from '@/notifications/scheduler';
import type { IntroDraft } from '@/state/introDraft';
import type { ActivityLevel, Gender, GoalType } from '@/utils/calories';

export const FLOW_ACTION_QUIZ_DONE = 'quiz_done';
export const FLOW_ACTION_SIGN_IN = 'sign_in';
export const FLOW_ACTION_REQUEST_ATT = 'request_att';

const GOALS: readonly GoalType[] = ['lose', 'maintain', 'gain', 'just_track'];
const GENDERS: readonly Gender[] = ['male', 'female'];
const ACTIVITY: readonly ActivityLevel[] = ['sedentary', 'light', 'moderate', 'active', 'very_active'];
const PAIN_POINTS = ['too_long', 'gave_up', 'accuracy', 'eating_out', 'first_time'] as const;

const AGE_RANGE = [14, 99] as const;
const HEIGHT_CM_RANGE = [120, 230] as const;
const WEIGHT_KG_RANGE = [30, 250] as const;

/** Shape of an Adapty `flow_user_input` analytics event (see docs "Process data from flows"). */
interface FlowUserInput {
  element_id?: unknown;
  element_type?: unknown;
  instanceId?: unknown;
  value?: unknown;
  item_ids?: unknown;
  item_titles?: unknown;
}

function asString(v: unknown): string | null {
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  return null;
}

function asNumber(v: unknown): number | null {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string') {
    const n = Number(v.replace(',', '.').replace(/[^\d.-]/g, ''));
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function clamp(n: number, [lo, hi]: readonly [number, number]): number {
  return Math.min(hi, Math.max(lo, Math.round(n)));
}

/** First selected option id of a choice group, or the scalar value. */
function pickOne(input: FlowUserInput): string | null {
  if (Array.isArray(input.item_ids) && input.item_ids.length > 0) {
    return asString(input.item_ids[0]);
  }
  return asString(input.value);
}

function pickMany(input: FlowUserInput): string[] {
  if (Array.isArray(input.item_ids)) {
    return input.item_ids.map(asString).filter((s): s is string => s !== null);
  }
  const one = asString(input.value);
  return one ? one.split(',').map((s) => s.trim()).filter(Boolean) : [];
}

function oneOf<T extends string>(value: string | null, allowed: readonly T[]): T | null {
  return value && (allowed as readonly string[]).includes(value) ? (value as T) : null;
}

/**
 * Imperial inputs arrive as three separate fields, and the flow cannot do the
 * arithmetic, so the app keeps the raw parts here until both halves exist.
 */
export interface FlowImperialScratch {
  height_ft?: number;
  height_in?: number;
  weight_lb?: number;
}

/**
 * Translate one `flow_user_input` event into an intro-draft patch.
 *
 * Returns an empty patch for inputs this app does not know — a flow is free to
 * ask extra questions for its own branching without touching the draft.
 * Unknown option ids are dropped rather than stored, so a typo in the
 * dashboard degrades to "unanswered", never to a corrupt profile.
 */
export function flowInputToDraftPatch(
  params: Record<string, unknown>,
  scratch: FlowImperialScratch,
): Partial<IntroDraft> {
  const input = params as FlowUserInput;
  const id = asString(input.element_id);
  if (!id) return {};

  switch (id) {
    case 'goal': {
      const goal = oneOf(pickOne(input), GOALS);
      return goal ? { goal_type: goal } : {};
    }
    case 'gender': {
      const gender = oneOf(pickOne(input), GENDERS);
      return gender ? { gender } : {};
    }
    case 'activity': {
      const level = oneOf(pickOne(input), ACTIVITY);
      return level ? { activity_level: level } : {};
    }
    case 'pain_points': {
      const ids = pickMany(input).filter((p) => (PAIN_POINTS as readonly string[]).includes(p));
      return { pain_points: ids };
    }
    case 'age': {
      const n = asNumber(input.value);
      return n === null ? {} : { age: clamp(n, AGE_RANGE) };
    }
    case 'height_cm': {
      const n = asNumber(input.value);
      return n === null ? {} : { height_cm: clamp(n, HEIGHT_CM_RANGE) };
    }
    case 'weight_kg': {
      const n = asNumber(input.value);
      return n === null ? {} : { weight_kg: clamp(n, WEIGHT_KG_RANGE) };
    }
    case 'height_ft':
    case 'height_in': {
      const n = asNumber(input.value);
      if (n === null) return {};
      scratch[id] = n;
      if (scratch.height_ft === undefined) return {};
      const inches = scratch.height_ft * 12 + (scratch.height_in ?? 0);
      return { height_cm: clamp(inches * 2.54, HEIGHT_CM_RANGE) };
    }
    case 'weight_lb': {
      const n = asNumber(input.value);
      if (n === null) return {};
      scratch.weight_lb = n;
      return { weight_kg: clamp(n / 2.2046, WEIGHT_KG_RANGE) };
    }
    default:
      return {};
  }
}

/** The quiz answered enough for the plan math (N1 / loader) to run. */
export function draftIsComplete(draft: IntroDraft): boolean {
  return Boolean(draft.goal_type && draft.gender && draft.activity_level);
}

/**
 * Forward a flow analytics event to PostHog under the names the native funnel
 * already uses, so dashboards built on `onboarding_screen_viewed` keep working
 * when a screen moves from code into the builder.
 */
export function trackFlowAnalytics(
  context: { placement: string; variation?: string; variationName?: string },
  name: string,
  params: Record<string, unknown>,
): void {
  const screen = asString(params.instanceId) ?? asString(params.screen_id) ?? undefined;
  const base = {
    placement: context.placement,
    variation_id: context.variation,
    variation_name: context.variationName,
    renderer: 'adapty_flow',
  };
  if (name === 'flow_screen_showed') {
    track('onboarding_screen_viewed', {
      ...base,
      screen,
      screen_order: params.screen_order,
      is_last_screen: params.is_last_screen,
    });
    return;
  }
  if (name === 'flow_user_input') {
    track('onboarding_screen_completed', {
      ...base,
      screen,
      element_id: asString(params.element_id) ?? undefined,
      element_type: asString(params.element_type) ?? undefined,
      // answers are kept out of PostHog event props except the ids, which are
      // what the funnels split on (goal, activity, pain points)
      item_ids: Array.isArray(params.item_ids) ? params.item_ids : undefined,
    });
    return;
  }
  track(`adapty_flow_${name}`, { ...base, ...params });
}

/**
 * Answer an OS-permission request raised from inside a flow ("Request
 * permission" action in the builder). ATT and push are the two we can grant;
 * everything else is reported as denied so the flow's own branching decides.
 */
export async function handleFlowPermissionRequest(
  permission: AdaptyPermission,
): Promise<FlowPermissionResponse> {
  try {
    if (permission === 'tracking') {
      const granted = await requestTrackingConsent();
      track('att_prompt_answered', { granted, source: 'adapty_flow' });
      return { status: granted ? 'granted' : 'denied' };
    }
    if (permission === 'push') {
      const granted = await requestPushPermission();
      return { status: granted ? 'granted' : 'denied' };
    }
  } catch {
    // fall through — a prompt that failed is a denial for routing purposes
  }
  return { status: 'denied', detail: `unsupported permission: ${permission}` };
}
