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
  AppMealCreate,
  AuthTokenResponse,
  BillingSnapshot,
  DaySummary,
  EmailCodeRequestResponse,
  MealRead,
  PresignResponse,
  SavedMealsListResponse,
  TelegramLinkRedeemResponse,
  TrialStartResponse,
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

// ---- Account / diary ----------------------------------------------------

export async function getMe(): Promise<AccountProfile> {
  return readWithFallback(() => apiFetch<AccountProfile>('/app/me'), () => mock.getMockProfile());
}

export async function updateMe(update: AccountProfileUpdate): Promise<AccountProfile> {
  if (USE_MOCKS) return mock.patchMockProfile(update);
  return apiFetch<AccountProfile>('/app/me', { method: 'PATCH', body: update });
}

export async function getToday(date?: string): Promise<DaySummary> {
  return readWithFallback(
    () => apiFetch<DaySummary>('/app/today', { query: { date } }),
    () => mock.getMockDay(date),
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
  return apiFetch<WorkflowRunResponse>('/app/agent/run', { method: 'POST', body: payload });
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
}

export async function createSavedMeal(payload: SavedMealCreateInput): Promise<void> {
  if (USE_MOCKS) {
    mock.addMockSaved({
      name: payload.name,
      total_calories: payload.total_calories,
      total_protein_g: payload.total_protein_g,
      total_fat_g: payload.total_fat_g,
      total_carbs_g: payload.total_carbs_g,
    });
    return;
  }
  // NOTE: backend SavedMealCreate currently requires `user_id`; the app resolves
  // it from `GET /app/me`. `items` is sent empty for a quick single-meal save.
  await apiFetch<unknown>('/app/saved-meals', { method: 'POST', body: { ...payload, items: [] } });
}
