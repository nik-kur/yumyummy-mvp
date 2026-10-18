/**
 * QA overrides: force any remote-config key in a QA build, without touching
 * Adapty. Stored on the device and applied on top of whatever Adapty sent.
 * In a production build `IS_QA_BUILD` is false and every reader here returns
 * "no overrides".
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

import { IS_QA_BUILD } from './buildFlags';
import type { OnboardingConfig, PaywallArmConfig } from './types';

const KEY = '@yy_qa_overrides';

export interface QaOverrides {
  onboarding?: {
    [K in keyof OnboardingConfig]?: OnboardingConfig[K] extends object
      ? Partial<OnboardingConfig[K]>
      : OnboardingConfig[K];
  };
  paywall?: Partial<PaywallArmConfig>;
  offer?: Partial<PaywallArmConfig>;
  /** `demo`: the bundled demo reviews (QA builds only) instead of `onb_content`. */
  content?: 'adapty' | 'demo';
  /** Pretend Adapty never answered: exercises the code defaults. */
  simulate_timeout?: boolean;
  /** Skip StoreKit: a tap on "buy" succeeds at once (post-purchase screens in the simulator). */
  mock_purchase?: boolean;
  /** Walk every V3 screen on its own for screenshots (`components/qa/QaAutoTour`). */
  auto_tour?: boolean;
  /** Only these auto-tour steps, by name (a targeted re-check). */
  auto_tour_only?: string[];
}

let cache: QaOverrides = {};
let loaded = false;
const listeners = new Set<() => void>();

export async function loadQaOverrides(): Promise<QaOverrides> {
  if (!IS_QA_BUILD) return {};
  if (loaded) return cache;
  try {
    const raw = await AsyncStorage.getItem(KEY);
    cache = raw ? (JSON.parse(raw) as QaOverrides) : {};
  } catch {
    cache = {};
  }
  loaded = true;
  return cache;
}

/** Synchronous read; call `loadQaOverrides()` once at launch first. */
export function qaOverrides(): QaOverrides {
  return IS_QA_BUILD ? cache : {};
}

export async function saveQaOverrides(next: QaOverrides): Promise<void> {
  if (!IS_QA_BUILD) return;
  cache = next;
  loaded = true;
  await AsyncStorage.setItem(KEY, JSON.stringify(next)).catch(() => {});
  listeners.forEach((l) => l());
}

export function subscribeQa(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** `true` when any override is set — the assignment is then reported as `qa`. */
export function hasQaOverrides(o: QaOverrides = qaOverrides()): boolean {
  return Object.keys(o).length > 0;
}
