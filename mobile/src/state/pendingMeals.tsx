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
import type { WorkflowItem, WorkflowRunResponse } from '@/api/types';
import { reportJourneyEvent, type LogOrigin, type LogSource } from '@/state/journey';
import { track } from '@/analytics/posthog';

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
  /** Additional photos of the same meal (25(1)+, max 4 total with the first). */
  localImageUris?: string[];
  /** Local file:// URI of a recorded voice note. Transcribed in the background. */
  audioUri?: string;
}

/** All photo URIs of a submission, deduplicated, in user order. */
function allImageUris(input: SubmitInput): string[] {
  const uris = [input.localImageUri, ...(input.localImageUris ?? [])].filter(
    (u): u is string => Boolean(u),
  );
  return Array.from(new Set(uris));
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

function kindOf(input: SubmitInput): LogSource {
  if (input.audioUri) return 'voice';
  if (allImageUris(input).length > 0) return 'photo';
  return 'text';
}

// Generic nutrition-database hosts. Any other source host means the numbers
// came from a brand or restaurant page — which is what the Day 4 quest
// ("log a meal you didn't cook") detects (spec §5.3 v0 rule).
const GENERIC_SOURCE_HOSTS = [
  'usda.gov',
  'nal.usda.gov',
  'nutritionix.com',
  'fatsecret.com',
  'myfitnesspal.com',
  'wikipedia.org',
  'healthline.com',
  'eatthismuch.com',
  'nutritionvalue.org',
];

function originOf(res: WorkflowRunResponse): LogOrigin | undefined {
  const urls = [res.source_url, ...(res.items ?? []).map((it) => it.source_url)].filter(
    (u): u is string => Boolean(u),
  );
  if (urls.length === 0) return undefined;
  for (const u of urls) {
    try {
      const host = new URL(u).hostname.toLowerCase();
      if (!GENERIC_SOURCE_HOSTS.some((g) => host === g || host.endsWith(`.${g}`))) {
        return 'brand';
      }
    } catch {
      // unparseable URL — ignore
    }
  }
  return 'generic';
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

      const clearAsLogged = (res?: WorkflowRunResponse) => {
        delete inputsRef.current[id];
        removeOrPatch(id); // backend logged it; Today refetches and shows the real meal
        // Activation event — the single funnel step that says the user got
        // real value. Fired once per confirmed log, from both the direct
        // success path and the timeout-reconciliation path.
        const totals = res ? sumItems(res.items ?? []) : null;
        track('meal_logged', {
          source: kindOf(input),
          origin: res ? originOf(res) : undefined,
          calories: res?.totals?.calories_kcal ?? totals?.calories,
          items_count: res?.items?.length,
          day_meal_index: baselineCount >= 0 ? baselineCount + 1 : undefined,
        });
        // First-week journey: a settled log is a quest event (first_log,
        // photo/voice, restaurant, full_day via today's count).
        void reportJourneyEvent({
          type: 'log_created',
          source: kindOf(input),
          origin: res ? originOf(res) : undefined,
          todayCount: baselineCount >= 0 ? baselineCount + 1 : undefined,
        }).catch(() => {});
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

        // Upload every photo in parallel; the first URL doubles as the legacy
        // single `image_url` so the request still works on an older server.
        const uris = allImageUris(input);
        let imageUrls: string[] = [];
        if (uris.length > 0) {
          imageUrls = await Promise.all(uris.map((u) => uploadMealPhoto(u)));
        }
        const imageUrl = imageUrls[0] ?? null;
        const typed = input.text?.trim() ?? '';
        const combined = [typed, voiceText].filter(Boolean).join(' ');
        const text = combined || (imageUrl ? '(photo)' : '');
        const res = await api.agentRun({
          text,
          image_url: imageUrl,
          image_urls: imageUrls.length > 1 ? imageUrls : undefined,
        });

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
          clearAsLogged(res);
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
      const photoCount = allImageUris(input).length;
      const kind: PendingMeal['kind'] = input.audioUri
        ? 'voice'
        : photoCount > 0
          ? 'photo'
          : 'text';
      const label =
        input.text?.trim() ||
        (kind === 'voice'
          ? 'Voice note…'
          : kind === 'photo'
            ? photoCount > 1
              ? `Photo meal (${photoCount} photos)`
              : 'Photo meal'
            : 'Meal');
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
