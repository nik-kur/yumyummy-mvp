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
import { uploadMealPhoto } from '@/api/upload';
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
  label: string; // what the user typed, or "Photo meal"
  kind: 'text' | 'photo';
  status: PendingStatus;
  error?: string;
  createdAt: number;
}

export interface SubmitInput {
  text?: string;
  localImageUri?: string;
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

  const run = useCallback(
    async (id: string, input: SubmitInput) => {
      try {
        let imageUrl: string | null = null;
        if (input.localImageUri) {
          imageUrl = await uploadMealPhoto(input.localImageUri);
        }
        const text = input.text?.trim() || (imageUrl ? '(photo)' : '');
        const res = await api.agentRun({ text, image_url: imageUrl });

        // IMPORTANT: `/app/agent/run` already persisted the meal server-side
        // (the same source-checked path the Telegram bot uses). We must NOT
        // create it again here — doing so logged every meal twice (and the
        // second copy only had summary totals, no breakdown/source). On success
        // we just clear the chip and let Today refetch to show the real entry.
        const intent = (res.intent ?? '').toLowerCase();
        const totals = sumItems(res.items ?? []);
        const loggedFood = (res.items?.length ?? 0) > 0 || totals.calories > 0;

        if (intent === 'paywall') {
          removeOrPatch(id, {
            status: 'error',
            error: res.message_text || 'Your trial has ended. Subscribe to keep logging meals.',
          });
          return;
        }
        if (!loggedFood) {
          removeOrPatch(id, {
            status: 'error',
            error: res.message_text || "Couldn't read that one. Tap to try again or add details.",
          });
          return;
        }
        delete inputsRef.current[id];
        removeOrPatch(id); // backend logged it; Today refetches and shows the real meal
      } catch (e) {
        removeOrPatch(id, {
          status: 'error',
          error: e instanceof Error ? e.message : 'Something went wrong. Tap to try again.',
        });
      }
    },
    [removeOrPatch],
  );

  const submit = useCallback(
    (input: SubmitInput) => {
      const id = nextId();
      const label = input.text?.trim() || 'Photo meal';
      const kind: PendingMeal['kind'] = input.localImageUri ? 'photo' : 'text';
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
