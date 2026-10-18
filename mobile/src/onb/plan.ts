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

/** Lowest weight inside the healthy BMI range, rounded up to a whole kilo (as on the canvas). */
export function healthyFloorKg(heightCm: number): number {
  const m = heightCm / 100;
  return Math.ceil(HEALTHY_BMI * m * m);
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

/**
 * Pace options in kg per week. Losing goes up to 1 kg/week — the CAP 13.10
 * ceiling, never more — with 0.4 recommended (Nikita, 18 Oct).
 */
export const PACE = {
  down: { min: 0.1, max: 1.0, step: 0.1, recommended: 0.4, gentleMax: 0.2, fastMin: 0.6 },
  up: { min: 0.1, max: 0.4, step: 0.05, recommended: 0.25, gentleMax: 0.15, fastMin: 0.35 },
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

/**
 * A floor no plan goes under, whatever the pace: the usual 1,200 kcal for
 * women and 1,500 for men (1,350 in between). Not BMR: a deficit below BMR is
 * normal for a sedentary body, and a BMR floor made every pace past 0.4 kg a
 * week land on the same calories and date.
 */
export function minKcal(body: BodyInput): number {
  return body.gender === 'male' ? 1500 : body.gender === 'female' ? 1200 : 1350;
}

/** Fastest weekly loss that keeps calories at or above `minKcal`. */
export function maxLossPace(body: BodyInput): number {
  return Math.max(0, ((maintenanceKcal(body) - minKcal(body)) * 7) / KCAL_PER_KG);
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
  /** The pace asked for would go under `minKcal`: calories sit on the floor, the date follows the slower real pace. */
  capped: boolean;
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
  let capped = false;
  // 5 kg at 0.5 kg a week is 10 weeks, not 11: float noise must not tip the ceil.
  const weeksFor = (kg: number, pace: number) => Math.max(1, Math.ceil(kg / pace - 1e-9));
  if ((mode === 'lose' || mode === 'cut' || mode === 'gain') && kgPerWeek && kgPerWeek > 0) {
    const daily = (kgPerWeek * KCAL_PER_KG) / 7;
    const kg = Math.abs(targetKg - body.weight_kg);
    if (mode === 'gain') {
      calories = tdee + daily;
      weeks = weeksFor(kg, kgPerWeek);
    } else if (tdee - daily >= minKcal(body)) {
      calories = tdee - daily;
      weeks = weeksFor(kg, kgPerWeek);
    } else {
      // The floor caps — or erases — the deficit for small, older bodies.
      capped = true;
      calories = minKcal(body);
      const realDaily = tdee - calories;
      if (realDaily <= 0) calories = tdee;
      else weeks = weeksFor(kg, (realDaily * 7) / KCAL_PER_KG);
    }
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
    // Local calendar date (toISOString would shift a day around midnight BST).
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    target_date = `${d.getFullYear()}-${mm}-${dd}`;
  }
  return { calories, protein, fat, carbs, weeks, target_date, capped };
}

/** "31 December" (UK order; the year only when the date is ~a year or more away). */
export function formatLongDate(iso: string, now: Date = new Date()): string {
  const d = new Date(`${iso}T12:00:00`);
  const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'long' };
  if (d.getTime() - now.getTime() > 300 * 24 * 3600 * 1000) opts.year = 'numeric';
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
