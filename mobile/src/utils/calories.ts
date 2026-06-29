/** Mifflin–St Jeor energy + macro split used for the onboarding plan reveal. */

export type GoalType = 'lose' | 'maintain' | 'gain' | 'just_track';
export type Gender = 'male' | 'female';
export type ActivityLevel = 'sedentary' | 'light' | 'moderate' | 'active' | 'very_active';

const ACTIVITY: Record<ActivityLevel, number> = {
  sedentary: 1.2,
  light: 1.375,
  moderate: 1.55,
  active: 1.725,
  very_active: 1.9,
};

const GOAL_DELTA: Record<GoalType, number> = {
  lose: -0.2,
  maintain: 0,
  gain: 0.12,
  just_track: 0,
};

export interface PlanInput {
  gender: Gender;
  age: number;
  height_cm: number;
  weight_kg: number;
  activity_level: ActivityLevel;
  goal_type: GoalType;
}

export interface Plan {
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  bmr: number;
  tdee: number;
}

export function computePlan(input: PlanInput): Plan {
  const bmr =
    10 * input.weight_kg +
    6.25 * input.height_cm -
    5 * input.age +
    (input.gender === 'male' ? 5 : -161);
  const tdee = bmr * (ACTIVITY[input.activity_level] ?? 1.2);
  const calories = Math.round((tdee * (1 + (GOAL_DELTA[input.goal_type] ?? 0))) / 10) * 10;
  const protein = Math.round(input.weight_kg * (input.goal_type === 'lose' ? 2.0 : 1.8));
  const fat = Math.round((calories * 0.27) / 9);
  const carbs = Math.max(0, Math.round((calories - protein * 4 - fat * 9) / 4));
  return { calories, protein, fat, carbs, bmr: Math.round(bmr), tdee: Math.round(tdee) };
}

export const GOAL_LABELS: Record<GoalType, string> = {
  lose: 'Lose weight',
  maintain: 'Eat better',
  gain: 'Build muscle',
  just_track: 'Just track \u2014 no targets',
};

export const ACTIVITY_LABELS: Record<ActivityLevel, string> = {
  sedentary: 'Sedentary',
  light: 'Light',
  moderate: 'Moderate',
  active: 'Active',
  very_active: 'Very active',
};
