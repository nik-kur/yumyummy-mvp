import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import * as api from '@/api/endpoints';
import { uploadMealPhoto, transcribeAudio } from '@/api/upload';
import type { WorkflowItem } from '@/api/types';

/**
 * Background meal logging.
 *
 * The agent can take 1–2 minutes (it searches the web for accurate numbers), so
 * instead of blocking the capture screen on a "Reading your meal…" spinner we
 * accept the input immediately, close the sheet, and show a "Analyzing…" row on
 * the Today screen. When the agent finishes we log the meal and the row is
 * replaced by the real entry. Failures surface as a tappable error row rather
 * than a silent 0-kcal meal.
 */

export type PendingStatus = 'processing' | 'error';

export interface PendingMeal {
  id: string;
  label: string; // what the user typed, "Photo meal", or "Voice note…"
  kind: 'text' | 'photo' | 'voice';
  status: PendingStatus;
  error?: string;
  createdAt: number;
}

export interface SubmitInput {
  text?: string;
  localImageUri?: string;
  /** Local file:// URI of a recorded voice note. Transcribed in the background. */
  audioUri?: string;
}

interface PendingMealsContextValue {
  pending: PendingMeal[];
  /** Bumped whenever a pending item finishes, so screens can refetch. */
  lastSettledAt: number;
  submit: (input: SubmitInput) => void;
  dismiss: (id: string) => void;
  retry: (id: string) => void;
}

const PendingMealsContext = createContext<PendingMealsContextValue | null>(null);

let _seq = 0;
function nextId(): string {
  _seq += 1;
  return `pending_${Date.now()}_${_seq}`;
}

function sumItems(items: WorkflowItem[]) {
  return items.reduce(
    (acc, it) => ({
      calories: acc.calories + (it.calories_kcal || 0),
      protein: acc.protein + (it.protein_g || 0),
      fat: acc.fat + (it.fat_g || 0),
      carbs: acc.carbs + (it.carbs_g || 0),
    }),
    { calories: 0, protein: 0, fat: 0, carbs: 0 },
  );
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Confirm the backend actually logged the meal even though our request didn't
 * return a clean success. This is the key fix for photo meals: the source-checked
 * workflow can outlive the client request (iOS drops it ~60s in), yet the server
 * finishes and persists the meal. Rather than show a false "Tap to retry" error,
 * we poll Today for ~30s and treat a new meal beyond the pre-submit baseline as
 * success. Returns false when we have no baseline (so the caller errors as before).
 */
async function confirmLoggedSince(baselineCount: number): Promise<boolean> {
  if (baselineCount < 0) return false;
  for (let i = 0; i < 6; i += 1) {
    await delay(5000);
    try {
      const today = await api.getTodayStrict();
      if ((today.meals?.length ?? 0) > baselineCount) return true;
    } catch {
      // Keep polling — a transient failure here shouldn't end reconciliation.
    }
  }
  return false;
}

export function PendingMealsProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<PendingMeal[]>([]);
  const [lastSettledAt, setLastSettledAt] = useState(0);
  // Raw inputs kept so an errored item can be retried.
  const inputsRef = useRef<Record<string, SubmitInput>>({});

  const removeOrPatch = useCallback((id: string, patch?: Partial<PendingMeal>) => {
    setPending((prev) =>
      patch ? prev.map((p) => (p.id === id ? { ...p, ...patch } : p)) : prev.filter((p) => p.id !== id),
    );
    setLastSettledAt(Date.now());
  }, []);

  // Non-terminal patch (does NOT bump lastSettledAt): used to swap a voice note's
  // placeholder label for the real transcript once STT returns.
  const update = useCallback((id: string, patch: Partial<PendingMeal>) => {
    setPending((prev) => prev.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  }, []);

  const run = useCallback(
    async (id: string, input: SubmitInput) => {
      // Snapshot Today's meal count BEFORE we submit. If the request later times
      // out (common for slow photo workflows), we can still detect that the
      // backend logged the meal by watching this count grow.
      let baselineCount = -1;
      try {
        const today = await api.getTodayStrict();
        baselineCount = today.meals?.length ?? -1;
      } catch {
        // No baseline -> reconciliation is disabled and a timeout surfaces as a
        // retryable error (the prior behavior). Best-effort only.
      }

      const clearAsLogged = () => {
        delete inputsRef.current[id];
        removeOrPatch(id); // backend logged it; Today refetches and shows the real meal
      };

      try {
        // Voice notes are fire-and-forget: transcribe here (in the background)
        // so the user never waits on the composer. The transcript replaces the
        // "Voice note…" placeholder and then feeds the normal logging path.
        let voiceText = '';
        if (input.audioUri) {
          try {
            voiceText = (await transcribeAudio(input.audioUri)).trim();
          } catch {
            removeOrPatch(id, {
              status: 'error',
              error: 'Couldn’t transcribe that voice note. Tap to retry.',
            });
            return;
          }
          if (!voiceText) {
            removeOrPatch(id, {
              status: 'error',
              error: 'Didn’t catch that. Tap to retry, or log by text.',
            });
            return;
          }
          if (voiceText) update(id, { label: voiceText });
        }

        let imageUrl: string | null = null;
        if (input.localImageUri) {
          imageUrl = await uploadMealPhoto(input.localImageUri);
        }
        const typed = input.text?.trim() ?? '';
        const combined = [typed, voiceText].filter(Boolean).join(' ');
        const text = combined || (imageUrl ? '(photo)' : '');
        const res = await api.agentRun({ text, image_url: imageUrl });

        // IMPORTANT: `/app/agent/run` already persisted the meal server-side
        // (the same source-checked path the Telegram bot uses). We must NOT
        // create it again here — doing so logged every meal twice (and the
        // second copy only had summary totals, no breakdown/source). On success
        // we just clear the chip and let Today refetch to show the real entry.
        const intent = (res.intent ?? '').toLowerCase();
        if (intent === 'paywall') {
          removeOrPatch(id, {
            status: 'error',
            error: res.message_text || 'Your trial has ended. Subscribe to keep logging meals.',
          });
          return;
        }

        const totals = sumItems(res.items ?? []);
        const loggedFood =
          (res.items?.length ?? 0) > 0 || totals.calories > 0 || (res.totals?.calories_kcal ?? 0) > 0;
        if (loggedFood) {
          clearAsLogged();
          return;
        }

        // 200 but no food in the payload — e.g. the backend persisted the meal
        // then returned a sanitized "help" response (it validates AFTER saving).
        // Confirm against Today before calling it a failure.
        if (await confirmLoggedSince(baselineCount)) {
          clearAsLogged();
          return;
        }
        removeOrPatch(id, {
          status: 'error',
          error: res.message_text || "Couldn't read that one. Tap to try again or add details.",
        });
      } catch (e) {
        // The (slower) photo workflow frequently finishes server-side AFTER the
        // client request is dropped, so the meal IS logged. Reconcile against
        // Today and only show an error if nothing actually landed.
        if (await confirmLoggedSince(baselineCount)) {
          clearAsLogged();
          return;
        }
        removeOrPatch(id, {
          status: 'error',
          error: e instanceof Error ? e.message : 'Something went wrong. Tap to try again.',
        });
      }
    },
    [removeOrPatch, update],
  );

  const submit = useCallback(
    (input: SubmitInput) => {
      const id = nextId();
      const kind: PendingMeal['kind'] = input.audioUri
        ? 'voice'
        : input.localImageUri
          ? 'photo'
          : 'text';
      const label =
        input.text?.trim() ||
        (kind === 'voice' ? 'Voice note…' : kind === 'photo' ? 'Photo meal' : 'Meal');
      inputsRef.current[id] = input;
      setPending((prev) => [
        { id, label, kind, status: 'processing', createdAt: Date.now() },
        ...prev,
      ]);
      void run(id, input);
    },
    [run],
  );

  const retry = useCallback(
    (id: string) => {
      const input = inputsRef.current[id];
      if (!input) {
        removeOrPatch(id);
        return;
      }
      setPending((prev) => prev.map((p) => (p.id === id ? { ...p, status: 'processing', error: undefined } : p)));
      void run(id, input);
    },
    [run, removeOrPatch],
  );

  const dismiss = useCallback((id: string) => {
    delete inputsRef.current[id];
    setPending((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const value = useMemo(
    () => ({ pending, lastSettledAt, submit, dismiss, retry }),
    [pending, lastSettledAt, submit, dismiss, retry],
  );

  return <PendingMealsContext.Provider value={value}>{children}</PendingMealsContext.Provider>;
}

export function usePendingMeals(): PendingMealsContextValue {
  const ctx = useContext(PendingMealsContext);
  if (!ctx) {
    throw new Error('usePendingMeals must be used within PendingMealsProvider');
  }
  return ctx;
}
