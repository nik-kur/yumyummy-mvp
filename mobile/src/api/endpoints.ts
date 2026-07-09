/**
 * Typed endpoint functions matching the Phase 1 backend
 * (`/auth/*`, `/app/*`, `/app/uploads/*`). Read endpoints fall back to mock
 * data when the API is unreachable so the UI keeps rendering in dev.
 */
import { apiFetch, USE_MOCKS } from './client';
import * as mock from './mock';
import type {
  AccountProfile,
  AccountProfileUpdate,
  AppAgentRunRequest,
  AppLinkIssueResponse,
  AppMealCreate,
  AuthTokenResponse,
  BillingSnapshot,
  DaySummary,
  DayTotals,
  EmailCodeRequestResponse,
  MealItem,
  MealRead,
  MealUpdateInput,
  PresignResponse,
  SavedMealUpdateInput,
  SavedMealsListResponse,
  TelegramLinkRedeemResponse,
  TrialStartResponse,
  WeeklyRecap,
  WorkflowRunResponse,
} from './types';

async function readWithFallback<T>(real: () => Promise<T>, fallback: () => T): Promise<T> {
  if (USE_MOCKS) return fallback();
  try {
    return await real();
  } catch {
    return fallback();
  }
}

// ---- Auth ---------------------------------------------------------------

export async function requestEmailCode(email: string): Promise<EmailCodeRequestResponse> {
  if (USE_MOCKS) return { sent: true, debug_code: '123456' };
  return apiFetch<EmailCodeRequestResponse>('/auth/email/request', {
    method: 'POST',
    auth: false,
    body: { email },
  });
}

export async function verifyEmailCode(email: string, code: string): Promise<AuthTokenResponse> {
  if (USE_MOCKS) return { access_token: mock.MOCK_TOKEN, token_type: 'bearer', account_id: 1, created: false };
  return apiFetch<AuthTokenResponse>('/auth/email/verify', {
    method: 'POST',
    auth: false,
    body: { email, code },
  });
}

export async function signInApple(identityToken: string): Promise<AuthTokenResponse> {
  if (USE_MOCKS) return { access_token: mock.MOCK_TOKEN, token_type: 'bearer', account_id: 1, created: true };
  return apiFetch<AuthTokenResponse>('/auth/apple', {
    method: 'POST',
    auth: false,
    body: { identity_token: identityToken },
  });
}

export async function signInGoogle(idToken: string): Promise<AuthTokenResponse> {
  if (USE_MOCKS) return { access_token: mock.MOCK_TOKEN, token_type: 'bearer', account_id: 1, created: true };
  return apiFetch<AuthTokenResponse>('/auth/google', {
    method: 'POST',
    auth: false,
    body: { id_token: idToken },
  });
}

export async function redeemTelegramLink(code: string): Promise<TelegramLinkRedeemResponse> {
  if (USE_MOCKS) {
    mock.markMockTelegramLinked();
    return { status: 'linked', account_id: 1 };
  }
  return apiFetch<TelegramLinkRedeemResponse>('/auth/link/telegram/redeem', {
    method: 'POST',
    body: { code },
  });
}

/** Reverse linking: mint a code + t.me deep link so the user can connect their
 *  Telegram bot from inside the (signed-in) app. */
export async function issueAppTelegramLink(): Promise<AppLinkIssueResponse> {
  if (USE_MOCKS) {
    return {
      code: 'YUM12345',
      expires_in_seconds: 900,
      bot_username: 'yum_yummybot',
      deep_link: 'https://t.me/yum_yummybot?start=link_YUM12345',
    };
  }
  return apiFetch<AppLinkIssueResponse>('/auth/link/app/issue', { method: 'POST' });
}

// ---- Account / diary ----------------------------------------------------

export async function getMe(): Promise<AccountProfile> {
  return readWithFallback(() => apiFetch<AccountProfile>('/app/me'), () => mock.getMockProfile());
}

export async function updateMe(update: AccountProfileUpdate): Promise<AccountProfile> {
  if (USE_MOCKS) return mock.patchMockProfile(update);
  return apiFetch<AccountProfile>('/app/me', { method: 'PATCH', body: update });
}

/**
 * Permanently delete the signed-in account and all its data (App Store Review
 * Guideline 5.1.1(v)). The caller is responsible for signing out afterwards.
 */
export async function deleteAccount(): Promise<void> {
  if (USE_MOCKS) return;
  await apiFetch<{ status: string }>('/app/me', { method: 'DELETE' });
}

export async function getToday(date?: string): Promise<DaySummary> {
  return readWithFallback(
    () => apiFetch<DaySummary>('/app/today', { query: { date } }),
    () => mock.getMockDay(date),
  );
}

/**
 * Like {@link getToday} but WITHOUT the mock-on-error fallback. Background
 * reconciliation (pendingMeals) must see real server state — a silent mock
 * fallback would make its "did a new meal land?" count comparison meaningless.
 */
export async function getTodayStrict(date?: string): Promise<DaySummary> {
  if (USE_MOCKS) return mock.getMockDay(date);
  return apiFetch<DaySummary>('/app/today', { query: { date } });
}

/**
 * Seven consecutive {@link DaySummary} starting at `start` (YYYY-MM-DD, the
 * Monday of the week) in a single round-trip — powers the Week tab's bars,
 * weekly averages and the selected day's meal list. Additive (25(1)+); falls
 * back to mock data so the tab still renders offline / against an old server.
 */
export async function getWeek(start: string): Promise<DaySummary[]> {
  return readWithFallback(
    () => apiFetch<DaySummary[]>('/app/week', { query: { start } }),
    () => mock.getMockWeek(start),
  );
}

/**
 * Lightweight per-day totals over [start, end] (no meal breakdown) for the
 * logging-streak counter. Additive (25(1)+).
 */
export async function getHistory(start: string, end: string): Promise<DayTotals[]> {
  return readWithFallback(
    () => apiFetch<DayTotals[]>('/app/history', { query: { start, end } }),
    () => mock.getMockHistory(start, end),
  );
}

/**
 * "Week in Recap" (Задача 6, 25(1)+): the most recent completed week's
 * shareable summary, or a specific week when `week` (any day inside it) is
 * given. Falls back to mock data so the screen renders offline / against an
 * older server that doesn't have the route yet.
 */
export async function getRecap(week?: string): Promise<WeeklyRecap> {
  return readWithFallback(
    () =>
      apiFetch<WeeklyRecap>(week ? '/app/recap' : '/app/recap/latest', {
        query: week ? { week } : undefined,
      }),
    () => mock.getMockRecap(week),
  );
}

export async function getRecentMeals(limit = 20): Promise<MealRead[]> {
  return readWithFallback(
    () => apiFetch<MealRead[]>('/app/meals/recent', { query: { limit } }),
    () => mock.getMockDay().meals,
  );
}

export async function createMeal(payload: AppMealCreate): Promise<MealRead> {
  if (USE_MOCKS) {
    return mock.addMockMeal({
      description_user: payload.description_user,
      calories: payload.calories,
      protein_g: payload.protein_g ?? 0,
      fat_g: payload.fat_g ?? 0,
      carbs_g: payload.carbs_g ?? 0,
      accuracy_level: payload.accuracy_level,
    });
  }
  return apiFetch<MealRead>('/app/meals', { method: 'POST', body: payload });
}

export async function getMeal(id: number): Promise<MealRead> {
  if (USE_MOCKS) {
    const meals = mock.getMockDay().meals;
    return meals.find((m) => m.id === id) ?? meals[0];
  }
  return apiFetch<MealRead>(`/app/meals/${id}`);
}

/** Edit a logged meal (25(1)+): rename, replace breakdown, or set totals.
 *  The server recomputes meal + day totals and returns the updated meal. */
export async function updateMeal(id: number, update: MealUpdateInput): Promise<MealRead> {
  if (USE_MOCKS) return mock.patchMockMeal(id, update);
  return apiFetch<MealRead>(`/app/meals/${id}`, { method: 'PATCH', body: update });
}

/** Re-log a meal verbatim (server copies macros + breakdown; no AI search). */
export async function repeatMeal(id: number): Promise<MealRead> {
  if (USE_MOCKS) {
    const src = mock.getMockDay().meals.find((m) => m.id === id);
    return mock.addMockMeal({
      description_user: src?.description_user ?? 'Meal',
      calories: src?.calories ?? 0,
      protein_g: src?.protein_g ?? 0,
      fat_g: src?.fat_g ?? 0,
      carbs_g: src?.carbs_g ?? 0,
      accuracy_level: src?.accuracy_level ?? undefined,
    });
  }
  return apiFetch<MealRead>(`/app/meals/${id}/repeat`, { method: 'POST' });
}

export async function deleteMeal(id: number): Promise<void> {
  if (USE_MOCKS) {
    mock.removeMockMeal(id);
    return;
  }
  await apiFetch<{ status: string; meal_id: number }>(`/app/meals/${id}`, { method: 'DELETE' });
}

export async function getSavedMeals(): Promise<SavedMealsListResponse> {
  return readWithFallback(() => apiFetch<SavedMealsListResponse>('/app/saved-meals'), () => mock.getMockSaved());
}

export async function getBillingStatus(): Promise<BillingSnapshot> {
  return readWithFallback(
    () => apiFetch<BillingSnapshot>('/app/billing/status'),
    () => mock.getMockProfile().billing,
  );
}

export async function startTrial(trialDays?: number): Promise<TrialStartResponse> {
  if (USE_MOCKS) return mock.startMockTrial(trialDays);
  return apiFetch<TrialStartResponse>('/app/billing/trial/start', {
    method: 'POST',
    body: { trial_days: trialDays },
  });
}

/**
 * Post-identify billing reconciliation: after `identifyAdapty()` merges the
 * anonymous Adapty profile, the backend pulls the subscription state from the
 * Adapty Server API to close the gap where the initial purchase webhook arrived
 * before the profile was identified. */
export async function syncBilling(): Promise<BillingSnapshot> {
  if (USE_MOCKS) return mock.getMockProfile().billing;
  return apiFetch<BillingSnapshot>('/app/billing/sync', { method: 'POST' });
}

export async function getLatestInsight(): Promise<Record<string, unknown>> {
  return readWithFallback(
    () => apiFetch<Record<string, unknown>>('/app/insights/latest'),
    () => ({
      id: 'motivation',
      icon: 'sparkle',
      title: 'Every meal counts',
      body: 'Keep logging — the more data you have, the smarter your insights become.',
    }),
  );
}

export async function getWeek1Report(): Promise<Record<string, unknown>> {
  return readWithFallback(
    () => apiFetch<Record<string, unknown>>('/app/report/week1'),
    () => ({ has_data: false, days_logged: 0, summary: 'Log meals to unlock your report!' }),
  );
}

export async function agentRun(payload: AppAgentRunRequest): Promise<WorkflowRunResponse> {
  if (USE_MOCKS) {
    return payload.force_intent === 'advice'
      ? mock.mockAdvisorReply(payload.text)
      : mock.mockAgentRun(payload.text, Boolean(payload.image_url));
  }
  // No mock fallback against a real backend: a network/timeout failure must
  // surface as an error so the caller can show a retry chip. Falling back to
  // fabricated mock food here previously made failed logs look successful (and,
  // combined with the now-removed client-side createMeal, produced phantom or
  // wrong-macro entries).
  //
  // 180s timeout: the source-checked workflow (especially photo meals on a
  // reasoning model) can run well past the platform default. Even when the
  // request is dropped, the backend persists the meal — pendingMeals reconciles
  // against Today so a late-finishing log still clears its chip.
  return apiFetch<WorkflowRunResponse>('/app/agent/run', {
    method: 'POST',
    body: payload,
    timeoutMs: 180_000,
  });
}

export async function presignMealPhoto(
  contentType = 'image/jpeg',
  ext?: string,
): Promise<PresignResponse> {
  if (USE_MOCKS) {
    return {
      key: 'mock/key.jpg',
      upload_url: 'https://example.com/upload',
      public_url: 'https://example.com/mock-meal.jpg',
      expires_in_seconds: 600,
    };
  }
  return apiFetch<PresignResponse>('/app/uploads/meal-photo/presign', {
    method: 'POST',
    body: { content_type: contentType, ext },
  });
}

export interface SavedMealCreateInput {
  user_id: number;
  name: string;
  total_calories: number;
  total_protein_g: number;
  total_fat_g: number;
  total_carbs_g: number;
  /** Component breakdown (25(1)+) so the saved meal stays editable per item. */
  items?: MealItem[];
}

export async function createSavedMeal(payload: SavedMealCreateInput): Promise<void> {
  if (USE_MOCKS) {
    mock.addMockSaved({
      name: payload.name,
      total_calories: payload.total_calories,
      total_protein_g: payload.total_protein_g,
      total_fat_g: payload.total_fat_g,
      total_carbs_g: payload.total_carbs_g,
      items: payload.items,
    });
    return;
  }
  // NOTE: backend SavedMealCreate requires `user_id`; the app resolves it from
  // `GET /app/me`.
  await apiFetch<unknown>('/app/saved-meals', {
    method: 'POST',
    body: { items: [], ...payload },
  });
}

/** Edit a saved meal (25(1)+): rename, replace breakdown, or set totals. */
export async function updateSavedMeal(id: number, update: SavedMealUpdateInput): Promise<void> {
  if (USE_MOCKS) {
    mock.patchMockSaved(id, update);
    return;
  }
  await apiFetch<unknown>(`/app/saved-meals/${id}`, { method: 'PATCH', body: update });
}

/** Remove a saved meal from My Menu (25(1)+). */
export async function deleteSavedMeal(id: number): Promise<void> {
  if (USE_MOCKS) {
    mock.removeMockSaved(id);
    return;
  }
  await apiFetch<{ status: string }>(`/app/saved-meals/${id}`, { method: 'DELETE' });
}

/** Log a saved meal onto today server-side (25(1)+): keeps the breakdown and
 *  bumps use_count, unlike the old client-side createMeal copy. */
export async function logSavedMeal(id: number): Promise<MealRead> {
  if (USE_MOCKS) return mock.logMockSaved(id);
  return apiFetch<MealRead>(`/app/saved-meals/${id}/log`, { method: 'POST' });
}
