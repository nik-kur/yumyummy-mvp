/**
 * Preview mode (V3 screen 21) in one place: is this a preview session, is the
 * free AI log still there, and the way to Last offer. Used by the tab bar, the
 * tabs layout and Today, so the "+", the hint and the empty state agree.
 */
import { useCallback, useRef } from 'react';
import { useRouter } from 'expo-router';

import { track } from '@/analytics/posthog';
import { getOnboardingConfig } from '@/config/onboardingConfig';
import { useAuth } from '@/state/auth';
import { usePendingMeals } from '@/state/pendingMeals';

/** Two taps (or a tap and a 402) within this window open Last offer once. */
const GATE_DEBOUNCE_MS = 1500;
let lastGateAt = 0;

export function usePreview(): {
  preview: boolean;
  freeLogLeft: boolean;
  openLastOffer: (from: string) => void;
} {
  const router = useRouter();
  const { status, profile } = useAuth();
  const { pending } = usePendingMeals();
  const routerRef = useRef(router);
  routerRef.current = router;
  const preview = status === 'preview';
  // A log still analysing holds the free log; a failed one does not (the
  // backend gives it back), so error rows do not count.
  const freeLogLeft =
    preview &&
    Boolean(profile?.preview_free_log_available) &&
    getOnboardingConfig().free_first_log &&
    !pending.some((p) => p.status === 'processing');
  const openLastOffer = useCallback((from: string) => {
    if (Date.now() - lastGateAt < GATE_DEBOUNCE_MS) return;
    lastGateAt = Date.now();
    track('preview_gate', { from });
    routerRef.current.push('/paywall?last_offer=1');
  }, []);
  return { preview, freeLogLeft, openLastOffer };
}
