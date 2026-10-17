/**
 * "A personal start" (plan screen 15 promises it): the first-week card's
 * day lines speak to the person's goal from the intro answers kept on the
 * device. Days 1–2 only — the rest of the ladder is the same for everyone.
 * No draft (an older account) → the ladder's own line.
 */
import type { IntroDraft } from '@/state/introDraft';

import { direction, fmtKg, fmtStLb, planMode } from './plan';

export function personalUnlock(day: number, draft: IntroDraft | null): string | null {
  if (!draft?.goal_type || (day !== 1 && day !== 2)) return null;
  const target = draft.target_weight_kg ?? draft.weight_kg;
  const mode = planMode(draft.goal_type, direction(draft.weight_kg, target));
  const weight = draft.units === 'imperial' ? fmtStLb(target) : `${fmtKg(target)} kg`;
  const kcal = draft.target_calories ? draft.target_calories.toLocaleString('en-GB') : null;
  const track = draft.goal_type === 'just_track';

  if (day === 1) {
    if (track) return 'Log your first meal — just seeing it changes a lot.';
    if (mode === 'lose' || mode === 'cut') return `Log your first meal — step one toward ${weight}.`;
    if (mode === 'gain') return `Log your first meal — every gram of protein counts toward ${weight}.`;
    if (mode === 'recomp') return 'Log your first meal and see your protein for today.';
    return 'Log your first meal and see where today lands.';
  }
  if (track) return null;
  if (mode === 'lose' || mode === 'cut') return 'Close a full day to see your real deficit.';
  if (mode === 'gain' || mode === 'recomp') return 'Close a full day and check you hit your protein.';
  return kcal ? `Close a full day and see how close you stay to ${kcal} kcal.` : null;
}
