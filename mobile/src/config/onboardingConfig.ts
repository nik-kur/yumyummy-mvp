/**
 * The onboarding switchboard: `onb_main` (test switches, one flow per arm) and
 * `onb_content` (copy, numbers and reviews shared by all arms).
 *
 * First launch: the splash waits for `onb_main` up to `ONB_CONFIG_TIMEOUT_MS`.
 * No answer in time → the review-safe defaults, reported as
 * `config_source: default`; those people are not the T0 control.
 *
 * The arm is fixed for the rest of the onboarding: the config and Adapty's
 * variation are stored on the device, so a relaunch half-way through the quiz
 * cannot move someone to another arm. The variation goes to PostHog the moment
 * it is assigned — onboarding tests are measured there (the purchase happens on
 * `pw_main`, so Adapty never sees an onboarding arm's revenue).
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';
import { adapty } from 'react-native-adapty';
import type { AdaptyFlow } from 'react-native-adapty';

import { register, setPersonProperties, track } from '@/analytics/posthog';
import { addBreadcrumb } from '@/analytics/sentry';
import {
  ADAPTY_PLACEMENT_ONBOARDING_CONTENT,
  ADAPTY_PLACEMENT_ONBOARDING_FLOW,
  whenAdaptyActivated,
} from '@/billing/adapty';

import { loadDraft } from '@/state/introDraft';

import { DEFAULT_ONBOARDING_CONTENT, DEFAULT_ONBOARDING_CONFIG } from './defaults';
import { parseOnboardingConfig, parseOnboardingContent, remoteConfigData } from './parse';
import { hasQaOverrides, loadQaOverrides, qaOverrides, subscribeQa } from './qa';
import type { AssignmentMeta, OnboardingConfig, OnboardingContent } from './types';

/** Longest the first launch waits for `onb_main` (agreed 2–3 s; Adapty activation alone takes ~2 s on a fresh install). */
export const ONB_CONFIG_TIMEOUT_MS = 3000;
/** How long the launch lets AppsFlyer go first before activating Adapty itself. */
const ACTIVATION_GRACE_MS = 1200;
const CONTENT_TIMEOUT_MS = 8000;

const ASSIGNMENT_KEY = '@yy_onb_assignment';
const CONTENT_KEY = '@yy_onb_content';

export interface OnboardingAssignment {
  config: OnboardingConfig;
  meta: AssignmentMeta;
}

let assignment: OnboardingAssignment | null = null;
/** When `onb_main` answered after the splash gave up: for the QA menu and PostHog. */
let lateFetch: { ms: number; outcome: string } | null = null;
export function getLateFetch(): { ms: number; outcome: string } | null {
  return lateFetch;
}
let resolving: Promise<OnboardingAssignment> | null = null;
/** Bumped by `clearOnboardingAssignment`; a resolve started before it must not write back. */
let generation = 0;
/** After an explicit reset (QA, tester mark) a leftover draft must not pin the arm to v1. */
let explicitlyCleared = false;
let content: OnboardingContent | null = null;
let contentRefresh: Promise<void> | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  listeners.forEach((l) => l());
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T | 'timeout'> {
  return Promise.race([
    promise,
    new Promise<'timeout'>((resolve) => setTimeout(() => resolve('timeout'), ms)),
  ]);
}

/** Fetch a flow quietly: a placement that does not exist yet is not an error. */
export async function getFlowQuiet(placement: string, timeoutMs: number): Promise<AdaptyFlow | null> {
  try {
    return await adapty.getFlow(placement, { loadTimeoutMs: timeoutMs });
  } catch (e) {
    addBreadcrumb('config', 'Flow fetch failed', {
      placement,
      error: e instanceof Error ? e.message : String(e),
    });
    return null;
  }
}

function analyticsProps(a: OnboardingAssignment): Record<string, unknown> {
  const qa = hasQaOverrides();
  return {
    onboarding_version: qa ? mergeOverrides(a.config).onboarding : a.config.onboarding,
    onb_config_source: qa ? 'qa' : a.meta.source,
    onb_variation_id: a.meta.variation_id ?? null,
    onb_variation_name: a.meta.variation_name ?? null,
    onb_ab_test: a.meta.ab_test ?? null,
  };
}

async function fetchAssignment(): Promise<OnboardingAssignment> {
  const started = Date.now();
  const base = { placement: ADAPTY_PLACEMENT_ONBOARDING_FLOW, assigned_at: new Date().toISOString() };
  const fallback = (reason: string): OnboardingAssignment => ({
    config: DEFAULT_ONBOARDING_CONFIG,
    meta: { ...base, source: 'default', default_reason: reason, fetch_ms: Date.now() - started },
  });

  if (qaOverrides().simulate_timeout) {
    await new Promise((resolve) => setTimeout(resolve, ONB_CONFIG_TIMEOUT_MS));
    return fallback('qa_simulated_timeout');
  }

  const attempt = (async () => {
    if (!(await whenAdaptyActivated(ACTIVATION_GRACE_MS))) return 'adapty_unavailable' as const;
    const left = Math.max(500, ONB_CONFIG_TIMEOUT_MS - (Date.now() - started));
    const flow = await getFlowQuiet(ADAPTY_PLACEMENT_ONBOARDING_FLOW, left);
    return flow ?? ('error' as const);
  })();

  const result = await withTimeout(attempt, ONB_CONFIG_TIMEOUT_MS);
  if (result === 'timeout') {
    // How late Adapty really was tells whether the budget fits real networks.
    void attempt.then((late) => {
      lateFetch = {
        ms: Date.now() - started,
        outcome: typeof late === 'string' ? late : 'flow',
      };
      track('onboarding_config_late', { late_ms: lateFetch.ms, outcome: lateFetch.outcome });
      emit();
    });
  }
  if (typeof result === 'string') return fallback(result);
  return {
    config: parseOnboardingConfig(remoteConfigData(result)),
    meta: {
      ...base,
      source: 'adapty',
      variation_id: result.variationId,
      variation_name: result.variationName,
      ab_test: result.placement?.abTestName,
      audience: result.placement?.audienceName,
      fetch_ms: Date.now() - started,
    },
  };
}

async function loadStoredAssignment(): Promise<OnboardingAssignment | null> {
  try {
    const raw = await AsyncStorage.getItem(ASSIGNMENT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as OnboardingAssignment;
    // Re-parse so a stored config from an older build gains new keys' defaults.
    return { config: parseOnboardingConfig(parsed.config as never), meta: parsed.meta };
  } catch {
    return null;
  }
}

/**
 * The onboarding arm for this install: the stored one, or a fresh Adapty
 * assignment (bounded by `ONB_CONFIG_TIMEOUT_MS`). Idempotent per launch.
 * Also starts the `onb_content` refresh in the background.
 */
export function resolveOnboardingAssignment(): Promise<OnboardingAssignment> {
  if (resolving) return resolving;
  const gen = generation;
  const run = (async (): Promise<OnboardingAssignment> => {
    await loadQaOverrides();
    void refreshOnboardingContent();
    const stored = await loadStoredAssignment();
    if (gen !== generation) return resolveOnboardingAssignment();
    if (stored) {
      assignment = stored;
      register(analyticsProps(stored));
      addBreadcrumb('config', 'Onboarding arm reused', { source: stored.meta.source });
      emit();
      return stored;
    }
    // Half-way through the pre-V3 onboarding when this build arrived: finish
    // it as it started rather than jumping into V3 mid-quiz.
    const draft = await loadDraft();
    const fresh: OnboardingAssignment = draft.goal_type && !explicitlyCleared
      ? {
          config: { ...DEFAULT_ONBOARDING_CONFIG, onboarding: 'v1' },
          meta: {
            source: 'default',
            default_reason: 'pre_v3_draft',
            placement: ADAPTY_PLACEMENT_ONBOARDING_FLOW,
            assigned_at: new Date().toISOString(),
          },
        }
      : await fetchAssignment();
    // A QA reset or tester mark cleared the arm while we were fetching.
    if (gen !== generation) return resolveOnboardingAssignment();
    assignment = fresh;
    await AsyncStorage.setItem(ASSIGNMENT_KEY, JSON.stringify(fresh)).catch(() => {});
    const props = analyticsProps(fresh);
    register(props);
    setPersonProperties(props);
    track('onboarding_config_assigned', {
      ...props,
      placement: fresh.meta.placement,
      audience: fresh.meta.audience ?? null,
      default_reason: fresh.meta.default_reason ?? null,
      fetch_ms: fresh.meta.fetch_ms ?? null,
    });
    addBreadcrumb('config', 'Onboarding arm assigned', {
      source: fresh.meta.source,
      variation: fresh.meta.variation_name ?? fresh.meta.variation_id,
      fetch_ms: fresh.meta.fetch_ms,
    });
    emit();
    return fresh;
  })();
  // Never strand the splash: anything unexpected resolves to the defaults.
  resolving = run.catch((e: unknown) => {
    addBreadcrumb('config', 'Onboarding arm resolve crashed', {
      error: e instanceof Error ? e.message : String(e),
    });
    const fallback: OnboardingAssignment = {
      config: DEFAULT_ONBOARDING_CONFIG,
      meta: {
        source: 'default',
        default_reason: 'resolve_error',
        placement: ADAPTY_PLACEMENT_ONBOARDING_FLOW,
        assigned_at: new Date().toISOString(),
      },
    };
    assignment = fallback;
    emit();
    return fallback;
  });
  return resolving;
}

/** Drop the stored arm; the next resolve asks Adapty again (QA reset, tester mark). */
export async function clearOnboardingAssignment(): Promise<void> {
  generation += 1;
  explicitlyCleared = true;
  assignment = null;
  resolving = null;
  await AsyncStorage.removeItem(ASSIGNMENT_KEY).catch(() => {});
  emit();
}

function mergeOverrides(config: OnboardingConfig): OnboardingConfig {
  const o = qaOverrides().onboarding;
  if (!o) return config;
  return {
    ...config,
    ...o,
    welcome: { ...config.welcome, ...(o.welcome ?? {}) },
    social_proof: { ...config.social_proof, ...(o.social_proof ?? {}) },
  } as OnboardingConfig;
}

/** The onboarding config in effect: the arm plus any QA overrides. */
export function getOnboardingConfig(): OnboardingConfig {
  return mergeOverrides(assignment?.config ?? DEFAULT_ONBOARDING_CONFIG);
}

/** The assignment meta, with `source: qa` while QA overrides are active. */
export function getOnboardingAssignmentMeta(): AssignmentMeta | null {
  if (!assignment) return null;
  return hasQaOverrides() ? { ...assignment.meta, source: 'qa' } : assignment.meta;
}

/**
 * Bundled demo content, QA builds only. Metro folds the constant and drops the
 * require in a production bundle, so the invented reviews never ship.
 */
const DEMO_CONTENT: OnboardingContent | null =
  __DEV__ || process.env.EXPO_PUBLIC_QA_BUILD === '1'
    ? // eslint-disable-next-line @typescript-eslint/no-require-imports
      (require('./demoContent') as { DEMO_CONTENT: OnboardingContent }).DEMO_CONTENT
    : null;

function demoContent(): OnboardingContent | null {
  return DEMO_CONTENT && qaOverrides().content === 'demo' ? DEMO_CONTENT : null;
}

export function getOnboardingContent(): OnboardingContent {
  return demoContent() ?? content ?? DEFAULT_ONBOARDING_CONTENT;
}

/**
 * `onb_content` is not on the critical path: screen 16 is ~2 minutes in. Use
 * the cached copy at once and refresh it in the background on every launch.
 */
export function refreshOnboardingContent(): Promise<void> {
  if (contentRefresh) return contentRefresh;
  contentRefresh = (async () => {
    try {
      const raw = await AsyncStorage.getItem(CONTENT_KEY);
      if (raw && !content) {
        content = parseOnboardingContent(JSON.parse(raw));
        emit();
      }
    } catch {
      // cache is a convenience
    }
    if (!(await whenAdaptyActivated(ACTIVATION_GRACE_MS))) return;
    const flow = await getFlowQuiet(ADAPTY_PLACEMENT_ONBOARDING_CONTENT, CONTENT_TIMEOUT_MS);
    const data = remoteConfigData(flow);
    if (!data) return;
    content = parseOnboardingContent(data);
    await AsyncStorage.setItem(CONTENT_KEY, JSON.stringify(data)).catch(() => {});
    emit();
  })();
  return contentRefresh;
}

export function subscribeOnboardingConfig(listener: () => void): () => void {
  listeners.add(listener);
  const unsubQa = subscribeQa(listener);
  return () => {
    listeners.delete(listener);
    unsubQa();
  };
}

/** Re-renders on a new assignment, new content or a QA override change. */
export function useOnboardingConfig(): {
  config: OnboardingConfig;
  content: OnboardingContent;
  meta: AssignmentMeta | null;
} {
  const [, setTick] = useState(0);
  useEffect(() => subscribeOnboardingConfig(() => setTick((t) => t + 1)), []);
  return {
    config: getOnboardingConfig(),
    content: getOnboardingContent(),
    meta: getOnboardingAssignmentMeta(),
  };
}
