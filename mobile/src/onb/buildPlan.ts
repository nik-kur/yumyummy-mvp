/**
 * The final plan from the quiz answers — run by the loader for every path
 * (Pace already stored one when the weight moves; this recomputes it so a
 * back-and-forth edit can never leave stale numbers).
 */
import type { IntroDraft } from '@/state/introDraft';

import { dailyPlan, direction, planMode, type PlanMode } from './plan';

export function buildPlan(d: IntroDraft): { patch: Partial<IntroDraft>; mode: PlanMode } {
  const target = d.target_weight_kg ?? d.weight_kg;
  const dir = direction(d.weight_kg, target);
  const mode = planMode(d.goal_type ?? 'just_track', dir);
  const body = {
    gender: d.gender ?? 'other',
    age: d.age,
    height_cm: d.height_cm,
    weight_kg: d.weight_kg,
    activity_level: d.activity_level ?? 'light',
  } as const;
  const pace = dir === 'same' ? null : d.pace_kg_week ?? (dir === 'up' ? 0.25 : 0.5);
  const p = dailyPlan(body, mode, target, pace);
  return {
    mode,
    patch: {
      target_weight_kg: target,
      pace_kg_week: pace,
      target_weeks: p.weeks,
      target_date: p.target_date,
      target_calories: p.calories,
      target_protein_g: p.protein,
      target_fat_g: p.fat,
      target_carbs_g: p.carbs,
    },
  };
}
