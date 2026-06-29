/**
 * Local mock data + a tiny mutable store so the app is fully navigable with no
 * backend. Onboarding starts incomplete, and `updateMe`/`agentRun`/`createMeal`
 * mutate this state so the flows feel real in Expo Go.
 */
import type {
  AccountProfile,
  AccountProfileUpdate,
  BillingSnapshot,
  DaySummary,
  MealRead,
  SavedMealListItem,
  SavedMealsListResponse,
  TrialStartResponse,
  WorkflowItem,
  WorkflowRunResponse,
} from './types';

export const MOCK_TOKEN = 'mock.jwt.token';

export const DEFAULT_TARGETS = {
  calories: 2340,
  protein: 175,
  fat: 78,
  carbs: 234,
};

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}
function isoMinusHours(h: number): string {
  return new Date(Date.now() - h * 3_600_000).toISOString();
}
function capitalize(s: string): string {
  return s.length ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

interface MockState {
  profile: AccountProfile;
  meals: MealRead[];
  savedMeals: SavedMealsListResponse;
}

function seedBilling(): BillingSnapshot {
  return {
    access_status: 'trial',
    trial_started_at: isoMinusHours(20),
    trial_ends_at: new Date(Date.now() + 2.2 * 86_400_000).toISOString(),
    trial_days_remaining: 2.2,
    subscription_plan_id: null,
    subscription_ends_at: null,
    subscription_auto_renew: null,
    subscription_provider: null,
    usage_cost_current_period: 0.42,
    usage_cap_usd: 2,
    usage_exceeded: false,
  };
}

function seedProfile(): AccountProfile {
  return {
    account_id: 1,
    user_id: 1,
    telegram_id: null,
    linked_providers: ['email'],
    goal_type: null,
    gender: null,
    age: null,
    height_cm: null,
    weight_kg: null,
    activity_level: null,
    target_calories: null,
    target_protein_g: null,
    target_fat_g: null,
    target_carbs_g: null,
    onboarding_completed: false,
    timezone: 'Europe/Moscow',
    billing: seedBilling(),
  };
}

function seedMeals(): MealRead[] {
  return [
    { id: 101, eaten_at: isoMinusHours(6), description_user: 'Greek yogurt, berries & honey', calories: 320, protein_g: 22, fat_g: 9, carbs_g: 41, accuracy_level: 'EXACT', source: 'USDA' },
    { id: 102, eaten_at: isoMinusHours(3), description_user: 'Chicken & avocado bowl, Sweetgreen', calories: 640, protein_g: 43, fat_g: 28, carbs_g: 52, accuracy_level: 'ESTIMATE', source: 'Restaurant' },
    { id: 103, eaten_at: isoMinusHours(1), description_user: 'Flat white', calories: 120, protein_g: 7, fat_g: 6, carbs_g: 10, accuracy_level: 'APPROX', source: 'Brand' },
  ];
}

function seedSaved(): SavedMealsListResponse {
  const items = [
    { id: 1, name: 'Sourdough avocado toast', total_calories: 380, total_protein_g: 12, total_fat_g: 18, total_carbs_g: 42, use_count: 14 },
    { id: 2, name: 'Protein oats & banana', total_calories: 450, total_protein_g: 32, total_fat_g: 11, total_carbs_g: 58, use_count: 11 },
    { id: 3, name: 'Chicken rice bowl', total_calories: 620, total_protein_g: 48, total_fat_g: 16, total_carbs_g: 70, use_count: 9 },
    { id: 4, name: 'Trader Joe\u2019s burrata salad', total_calories: 410, total_protein_g: 19, total_fat_g: 30, total_carbs_g: 14, use_count: 6 },
  ];
  return { items, total: items.length, page: 1, per_page: items.length };
}

const state: MockState = {
  profile: seedProfile(),
  meals: seedMeals(),
  savedMeals: seedSaved(),
};

let nextMealId = 1000;

export function getMockProfile(): AccountProfile {
  return { ...state.profile, billing: { ...state.profile.billing } };
}

export function patchMockProfile(update: AccountProfileUpdate): AccountProfile {
  const clean: Partial<AccountProfile> = {};
  (Object.keys(update) as (keyof AccountProfileUpdate)[]).forEach((k) => {
    const v = update[k];
    if (v !== null && v !== undefined) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (clean as any)[k] = v;
    }
  });
  state.profile = { ...state.profile, ...clean };
  return getMockProfile();
}

function sum(meals: MealRead[], key: 'calories' | 'protein_g' | 'fat_g' | 'carbs_g'): number {
  return Math.round(meals.reduce((acc, m) => acc + (m[key] ?? 0), 0));
}

export function getMockDay(date?: string): DaySummary {
  return {
    user_id: 1,
    date: date ?? todayISO(),
    total_calories: sum(state.meals, 'calories'),
    total_protein_g: sum(state.meals, 'protein_g'),
    total_fat_g: sum(state.meals, 'fat_g'),
    total_carbs_g: sum(state.meals, 'carbs_g'),
    meals: [...state.meals],
  };
}

export function addMockMeal(input: {
  description_user: string;
  calories: number;
  protein_g: number;
  fat_g: number;
  carbs_g: number;
  accuracy_level?: MealRead['accuracy_level'];
  source?: string;
}): MealRead {
  const meal: MealRead = {
    id: ++nextMealId,
    eaten_at: new Date().toISOString(),
    description_user: input.description_user,
    calories: input.calories,
    protein_g: input.protein_g,
    fat_g: input.fat_g,
    carbs_g: input.carbs_g,
    accuracy_level: input.accuracy_level ?? 'ESTIMATE',
    source: input.source,
  };
  state.meals = [...state.meals, meal];
  return meal;
}

export function removeMockMeal(id: number): void {
  state.meals = state.meals.filter((m) => m.id !== id);
}

export function getMockSaved(): SavedMealsListResponse {
  return { ...state.savedMeals, items: [...state.savedMeals.items] };
}

let nextSavedId = 100;

export function addMockSaved(input: {
  name: string;
  total_calories: number;
  total_protein_g: number;
  total_fat_g: number;
  total_carbs_g: number;
}): SavedMealListItem {
  const saved: SavedMealListItem = { id: ++nextSavedId, use_count: 1, ...input };
  state.savedMeals = {
    ...state.savedMeals,
    items: [saved, ...state.savedMeals.items],
    total: state.savedMeals.total + 1,
    per_page: state.savedMeals.per_page + 1,
  };
  return saved;
}

export function startMockTrial(trialDays?: number): TrialStartResponse {
  return {
    access_status: 'trial',
    trial_started_at: state.profile.billing.trial_started_at,
    trial_ends_at: state.profile.billing.trial_ends_at,
    trial_days: trialDays ?? 3,
    already_started: true,
  };
}

export function markMockTelegramLinked(): void {
  // A returning bot user already has a profile + targets in the diary.
  state.profile = {
    ...state.profile,
    telegram_id: '123456789',
    linked_providers: Array.from(new Set([...state.profile.linked_providers, 'telegram'])),
    onboarding_completed: true,
    goal_type: state.profile.goal_type ?? 'maintain',
    target_calories: state.profile.target_calories ?? DEFAULT_TARGETS.calories,
    target_protein_g: state.profile.target_protein_g ?? DEFAULT_TARGETS.protein,
    target_fat_g: state.profile.target_fat_g ?? DEFAULT_TARGETS.fat,
    target_carbs_g: state.profile.target_carbs_g ?? DEFAULT_TARGETS.carbs,
  };
}

export function mockAgentRun(text: string, hasPhoto: boolean): WorkflowRunResponse {
  const parts = text
    .split(/,| and | with |\+/i)
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 4);
  const names = parts.length ? parts : [hasPhoto ? 'Pictured meal' : 'Logged item'];
  const items: WorkflowItem[] = names.map((name, i) => {
    const base = 120 + ((name.length * 17 + i * 53) % 320);
    return {
      name: capitalize(name),
      grams: 80 + ((name.length * 7) % 180),
      calories_kcal: base,
      protein_g: Math.round((base * 0.18) / 4),
      fat_g: Math.round((base * 0.3) / 9),
      carbs_g: Math.round((base * 0.52) / 4),
      source_url: 'https://fdc.nal.usda.gov/',
    };
  });
  const totals = {
    calories_kcal: items.reduce((a, b) => a + b.calories_kcal, 0),
    protein_g: items.reduce((a, b) => a + b.protein_g, 0),
    fat_g: items.reduce((a, b) => a + b.fat_g, 0),
    carbs_g: items.reduce((a, b) => a + b.carbs_g, 0),
  };
  return {
    intent: 'log_meal',
    message_text: hasPhoto
      ? 'Here\u2019s what I see on your plate. Adjust anything before logging.'
      : 'Got it \u2014 here\u2019s my estimate. Tweak portions if needed.',
    confidence: 'ESTIMATE',
    totals,
    items,
    source_url: 'https://fdc.nal.usda.gov/',
  };
}

export function mockAdvisorReply(_text: string): WorkflowRunResponse {
  return {
    intent: 'advice',
    message_text:
      'You have room for a balanced dinner. Based on your remaining budget, aim for ~40g protein and keep it around 600 kcal — a salmon bowl with greens and rice would fit nicely.',
    confidence: null,
    totals: { calories_kcal: 0, protein_g: 0, fat_g: 0, carbs_g: 0 },
    items: [],
    source_url: 'https://fdc.nal.usda.gov/',
  };
}
