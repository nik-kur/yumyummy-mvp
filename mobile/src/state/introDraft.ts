/**
 * Intro onboarding draft — persisted in AsyncStorage before auth.
 *
 * After the user completes onboarding and signs in with Apple, this draft
 * is synced to the backend via PATCH /app/me and then cleared.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { ActivityLevel, Gender, GoalType } from '@/utils/calories';

const KEY = '@yy_intro_draft';

export interface IntroDraft {
  // S2 Goal
  goal_type: GoalType | null;
  // S3 Pain points (multi-select)
  pain_points: string[];
  // S4 Gender
  gender: Gender | null;
  // S5 Age
  age: number;
  // S6 Height + Weight
  height_cm: number;
  weight_kg: number;
  // S7 Activity level
  activity_level: ActivityLevel | null;
  // S8 (removed per v3 — target weight now computed on N1)
  // N1 Target & Pace
  target_weight_kg: number | null;
  deficit_pct: number | null;
  target_weeks: number | null;
  // Computed
  target_calories: number | null;
  target_protein_g: number | null;
  target_fat_g: number | null;
  target_carbs_g: number | null;
}

export const DEFAULT_DRAFT: IntroDraft = {
  goal_type: null,
  pain_points: [],
  gender: null,
  age: 30,
  height_cm: 175,
  weight_kg: 75,
  activity_level: null,
  target_weight_kg: null,
  deficit_pct: null,
  target_weeks: null,
  target_calories: null,
  target_protein_g: null,
  target_fat_g: null,
  target_carbs_g: null,
};

export async function loadDraft(): Promise<IntroDraft> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return DEFAULT_DRAFT;
    return { ...DEFAULT_DRAFT, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_DRAFT;
  }
}

export async function saveDraft(draft: IntroDraft): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(draft)).catch(() => {});
}

export async function clearDraft(): Promise<void> {
  await AsyncStorage.removeItem(KEY).catch(() => {});
}
