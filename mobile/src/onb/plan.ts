/**
 * V3 plan math: weight direction, goal check (realistic / ambitious / below a
 * healthy BMI), pace, daily calories, goal date and the plan "mode" that picks
 * the Plan reveal, Features and Reflect variants.
 *
 * Rules (Miro "Логика цели", agreed 15 Oct):
 *   - direction = target vs current weight; within ±1 kg counts as "same";
 *   - a change above 10 % of body weight is "ambitious", otherwise "realistic";
 *   - a target below BMI 18.5 is never praised: the app proposes the weight at
 *     BMI 18.5 instead (Goal_healthy), and the pace works from that;
 *   - pace is asked only when the weight should move.
 * The main goal (screen 2) sets the tone; the target weight sets the plan.
 */
import { computePlan, type ActivityLevel, type Gender, type GoalType } from '@/utils/calories';

export const KCAL_PER_KG = 7700;
export const HEALTHY_BMI = 18.5;
export const SAME_WEIGHT_KG = 1;
export const AMBITIOUS_SHARE = 0.1;

export type Direction = 'down' | 'same' | 'up';
/** Which plan the person gets — drives copy and charts downstream. */
export type PlanMode = 'lose' | 'zone' | 'gain' | 'recomp' | 'cut';

export function bmi(weightKg: number, heightCm: number): number {
  const m = heightCm / 100;
  return weightKg / (m * m);
}

/** Lowest weight inside the healthy BMI range, rounded up to 0.2 kg. */
export function healthyFloorKg(heightCm: number): number {
  const m = heightCm / 100;
  return Math.ceil(HEALTHY_BMI * m * m * 5) / 5;
}

export function direction(currentKg: number, targetKg: number): Direction {
  const d = targetKg - currentKg;
  if (Math.abs(d) <= SAME_WEIGHT_KG) return 'same';
  return d < 0 ? 'down' : 'up';
}

export type GoalCheck = 'realistic' | 'ambitious' | 'healthy';

export function goalCheck(currentKg: number, targetKg: number, heightCm: number): GoalCheck {
  if (targetKg < healthyFloorKg(heightCm) - 1e-6) return 'healthy';
  return Math.abs(targetKg - currentKg) > currentKg * AMBITIOUS_SHARE ? 'ambitious' : 'realistic';
}

export function planMode(goal: GoalType, dir: Direction): PlanMode {
  if (goal === 'gain') return dir === 'down' ? 'cut' : dir === 'same' ? 'recomp' : 'gain';
  if (dir === 'down') return 'lose';
  if (dir === 'up') return 'gain';
  return 'zone';
}

/** Pace options in kg per week. Losing tops out at 1 kg/week (CAP 13.10). */
export const PACE = {
  down: { min: 0.1, max: 1.0, step: 0.1, recommended: 0.5, gentleMax: 0.3, fastMin: 0.8 },
  up: { min: 0.1, max: 0.5, step: 0.05, recommended: 0.25, gentleMax: 0.15, fastMin: 0.4 },
} as const;

export type PaceZone = 'gentle' | 'recommended' | 'fast';

export function paceZone(dir: 'down' | 'up', kgPerWeek: number): PaceZone {
  const p = PACE[dir];
  if (kgPerWeek <= p.gentleMax + 1e-6) return 'gentle';
  if (kgPerWeek >= p.fastMin - 1e-6) return 'fast';
  return 'recommended';
}

export interface BodyInput {
  gender: Gender;
  age: number;
  height_cm: number;
  weight_kg: number;
  activity_level: ActivityLevel;
}

/** Maintenance calories (TDEE) for the current body. */
export function maintenanceKcal(body: BodyInput): number {
  return computePlan({ ...body, goal_type: 'maintain' }).tdee;
}

/** A floor no plan goes under, whatever the pace. */
export function minKcal(body: BodyInput): number {
  const sexFloor = body.gender === 'male' ? 1500 : body.gender === 'female' ? 1200 : 1350;
  return Math.max(sexFloor, Math.round(computePlan({ ...body, goal_type: 'maintain' }).bmr / 10) * 10);
}

export interface DailyPlan {
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  /** Weeks to reach the target, or null when the weight should hold. */
  weeks: number | null;
  /** ISO date of the target, or null. */
  target_date: string | null;
}

function round10(n: number): number {
  return Math.round(n / 10) * 10;
}

/**
 * The daily plan for a target and pace. Recomposition keeps maintenance
 * calories with high protein; a "cut" (gain goal, weight down) keeps protein
 * high too. The deficit is capped so calories never go below `minKcal`.
 */
export function dailyPlan(
  body: BodyInput,
  mode: PlanMode,
  targetKg: number,
  kgPerWeek: number | null,
  now: Date = new Date(),
): DailyPlan {
  const tdee = maintenanceKcal(body);
  let calories = tdee;
  let weeks: number | null = null;
  if ((mode === 'lose' || mode === 'cut' || mode === 'gain') && kgPerWeek && kgPerWeek > 0) {
    const daily = (kgPerWeek * KCAL_PER_KG) / 7;
    calories = mode === 'gain' ? tdee + daily : Math.max(minKcal(body), tdee - daily);
    // The real pace when the floor caps the deficit.
    const realDaily = Math.abs(tdee - calories);
    const realPace = realDaily > 0 ? (realDaily * 7) / KCAL_PER_KG : kgPerWeek;
    weeks = Math.max(1, Math.ceil(Math.abs(body.weight_kg - targetKg) / realPace));
  }
  calories = round10(calories);
  const proteinPerKg = mode === 'gain' || mode === 'recomp' || mode === 'cut' ? 2.0 : mode === 'lose' ? 1.6 : 1.4;
  const protein = Math.round(body.weight_kg * proteinPerKg);
  const fat = Math.round((calories * 0.27) / 9);
  const carbs = Math.max(0, Math.round((calories - protein * 4 - fat * 9) / 4));
  let target_date: string | null = null;
  if (weeks !== null) {
    const d = new Date(now);
    d.setDate(d.getDate() + weeks * 7);
    target_date = d.toISOString().slice(0, 10);
  }
  return { calories, protein, fat, carbs, weeks, target_date };
}

/** "31 December" (UK order, no year unless it is not this year's). */
export function formatLongDate(iso: string, now: Date = new Date()): string {
  const d = new Date(`${iso}T12:00:00`);
  const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long' };
  if (d.getFullYear() !== now.getFullYear()) opts.year = 'numeric';
  return d.toLocaleDateString('en-GB', opts);
}

/** "31 Dec". */
export function formatShortDate(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

/** Weight with at most one decimal, no trailing ".0": 66, 65.4. */
export function fmtKg(kg: number): string {
  const r = Math.round(kg * 10) / 10;
  return Number.isInteger(r) ? String(r) : r.toFixed(1);
}

// ---- imperial -------------------------------------------------------------

export const LB_PER_KG = 2.20462;

export function kgToStLb(kg: number): { st: number; lb: number } {
  const totalLb = Math.round(kg * LB_PER_KG);
  return { st: Math.floor(totalLb / 14), lb: totalLb % 14 };
}

export function fmtStLb(kg: number): string {
  const { st, lb } = kgToStLb(kg);
  return lb === 0 ? `${st} st` : `${st} st ${lb} lb`;
}

export function cmToFtIn(cm: number): { ft: number; inch: number } {
  const totalIn = Math.round(cm / 2.54);
  return { ft: Math.floor(totalIn / 12), inch: totalIn % 12 };
}
