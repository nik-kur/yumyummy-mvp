/**
 * Post-purchase tour (V3 screen 24) and the first-log payoff (25).
 *
 * Six steps over the real app: 1 dashboard → 2 the "+" button → 3 the
 * capture bar → 4 the first logged meal → 5 Week and My Menu → 6 the
 * first-week card. Step 2 waits for a tap on "+", step 3 for a logged meal,
 * step 4 for that meal to land on Today. Skip ends the tour at any step.
 *
 * The payoff sheet ("That's your first log!") shows once, after the tour, as
 * soon as Today has a meal. Both start only for a new account made right
 * after a purchase (`startPostPurchase`), never for a returning customer.
 * State survives relaunches.
 */
import { useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { track } from '@/analytics/posthog';

export type TourStep = 1 | 2 | 3 | 4 | 5 | 6;

export interface TourState {
  status: 'off' | 'active' | 'done';
  step: TourStep;
  payoff: 'none' | 'pending' | 'shown';
}

const KEY = '@yy_tour_v3';
const OFF: TourState = { status: 'off', step: 1, payoff: 'none' };

let state: TourState = OFF;
let loaded = false;
let loading: Promise<TourState> | null = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

async function save(next: TourState): Promise<void> {
  state = next;
  loaded = true;
  emit();
  await AsyncStorage.setItem(KEY, JSON.stringify(next)).catch(() => {});
}

export function loadTour(): Promise<TourState> {
  if (loaded) return Promise.resolve(state);
  if (!loading) {
    loading = AsyncStorage.getItem(KEY)
      .then((raw) => {
        if (!loaded) {
          state = raw ? { ...OFF, ...(JSON.parse(raw) as Partial<TourState>) } : OFF;
          // Step 3 lives inside the capture screen, which a relaunch closes.
          if (state.status === 'active' && state.step === 3) state = { ...state, step: 2 };
        }
        loaded = true;
        emit();
        return state;
      })
      .catch(() => {
        loaded = true;
        return state;
      });
  }
  return loading;
}

export function getTour(): TourState {
  return state;
}

/** A new account right after a purchase: tour (if switched on) and the payoff. */
export async function startPostPurchase(tutorial: boolean): Promise<void> {
  await save({ status: tutorial ? 'active' : 'done', step: 1, payoff: 'pending' });
  if (tutorial) track('tour_started');
}

export async function setTourStep(step: TourStep): Promise<void> {
  if (state.status !== 'active' || state.step === step) return;
  await save({ ...state, step });
}

export async function nextTourStep(): Promise<void> {
  if (state.status !== 'active') return;
  if (state.step >= 6) {
    track('tour_completed');
    await save({ ...state, status: 'done' });
    return;
  }
  await save({ ...state, step: (state.step + 1) as TourStep });
}

export async function skipTour(): Promise<void> {
  if (state.status !== 'active') return;
  track('tour_skipped', { step: state.step });
  await save({ ...state, status: 'done' });
}

export async function markPayoffShown(): Promise<void> {
  if (state.payoff !== 'pending') return;
  await save({ ...state, payoff: 'shown' });
}

/** QA menu: start over from step 1. */
export async function resetTour(active: boolean): Promise<void> {
  await save(active ? { status: 'active', step: 1, payoff: 'pending' } : OFF);
}

export function useTour(): TourState {
  const [s, setS] = useState(state);
  useEffect(() => {
    const l = () => setS(state);
    listeners.add(l);
    void loadTour().then(l);
    return () => {
      listeners.delete(l);
    };
  }, []);
  return s;
}
