/**
 * Copy and photo data of the V3 paywall (17–19) and offer (20).
 *
 * Every visible line has a key in the arm's remote config `copy` map, so a
 * test can reword a screen without a release:
 *   b1_title, b1_today, b1_cta, b2_title, b2_cta, p1_title, p1_cta,
 *   plans_title, plans_today, plans_cta; offer: badge, headline, cta, footnote.
 * A remote title is plain text (no terracotta accent).
 */
import { direction, fmtKg, fmtStLb, planMode } from '@/onb/plan';
import { PW, PW_VIDEO } from '@/onb/assets';
import type { IntroDraft } from '@/state/introDraft';

/** Headline with an optional terracotta accent in the middle ("Reach |66 kg| by 31 Dec."). */
export interface Hero {
  pre: string;
  accent?: string;
  post?: string;
}

/** "31 Dec"; the year too when the date is ~a year or more away. */
function shortDate(d: Date, now: Date = new Date()): string {
  const opts: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' };
  if (d.getTime() - now.getTime() > 300 * 24 * 3600 * 1000) opts.year = 'numeric';
  return d.toLocaleDateString('en-GB', opts);
}

function goalDate(draft: IntroDraft): Date | null {
  if (draft.target_date) return new Date(`${draft.target_date}T12:00:00`);
  if (draft.target_weeks) {
    const d = new Date();
    d.setDate(d.getDate() + draft.target_weeks * 7);
    return d;
  }
  return null;
}

/**
 * B1 / P1 plans headline from the plan the person just saw (screen 15).
 * `draft` is null for signed-in entries, whose old intro answers may be stale.
 */
export function heroTitle(draft: IntroDraft | null, hasTrial: boolean): Hero {
  const start = hasTrial ? 'Start for free today.' : 'Start today.';
  if (!draft || !draft.goal_type) return { pre: `Reach your goal. ${start}` };
  const target = draft.target_weight_kg ?? draft.weight_kg;
  const mode = planMode(draft.goal_type, direction(draft.weight_kg, target));
  const show = (kg: number) => (draft.units === 'imperial' ? fmtStLb(kg) : `${fmtKg(kg)} kg`);
  const date = goalDate(draft);
  if ((mode === 'lose' || mode === 'cut' || mode === 'gain') && date) {
    return { pre: 'Reach ', accent: show(target), post: ` by ${shortDate(date)}. ${start}` };
  }
  if (mode === 'recomp') return { pre: 'Build muscle at ', accent: show(draft.weight_kg), post: `. ${start}` };
  if (draft.goal_type === 'just_track') return { pre: `Know what you eat, choose better. ${start}` };
  if (mode === 'zone') return { pre: `Feel better while you keep your shape. ${start}` };
  return { pre: `Reach your goal. ${start}` };
}

export interface BadgeSpec {
  /** Artboard coordinates (390 pt wide); scaled with the photo. */
  top: number;
  right?: number;
  left?: number;
  width: number;
  title: string;
  kcal: string;
  source: string;
}

const HOME_BADGE = { title: 'Chicken, rice and greens', kcal: '535', source: 'USDA FOODDATA' };
const JOE_SOURCE = 'JOEANDTHEJUICE.COM';

/** B3 photo per `pw_main` variant (19). */
export const B3_PHOTOS: Record<string, { photo: number; badge: BadgeSpec }> = {
  b3_joe: {
    photo: PW.b3_joe,
    badge: { right: 16, top: 60, width: 160, title: 'Joe & The Juice smoothie', kcal: '412', source: JOE_SOURCE },
  },
  b3_home: { photo: PW.b3_home, badge: { right: 24, top: 64, width: 168, ...HOME_BADGE } },
  b3_office: {
    photo: PW.b3_office,
    badge: { right: 10, top: 84, width: 148, title: 'Meal deal lunch', kcal: '480', source: 'USDA FOODDATA' },
  },
  b3_wide: {
    photo: PW.b3_wide,
    badge: { left: 24, top: 336, width: 176, title: 'Joe & The Juice', kcal: '412', source: JOE_SOURCE },
  },
};

/** Offer photo per `pw_after_cancel` variant (20). The Costa photo has its scan bubble baked in. */
export const OFFER_PHOTOS: Record<string, { photo: number; badge: BadgeSpec | null }> = {
  costa: { photo: PW.offer_costa, badge: null },
  closeup: { photo: PW.b3_home, badge: { right: 24, top: 98, width: 168, ...HOME_BADGE } },
};

/** P1 demo clip per variant, with its first frame as the poster. */
export const P1_CLIPS: Record<string, { video: number; poster: number }> = {
  p1_photo: { video: PW_VIDEO.p1_photo, poster: PW.p1_photo_poster },
  p1_text: { video: PW_VIDEO.p1_text, poster: PW.p1_text_poster },
  p1_voice: { video: PW_VIDEO.p1_voice, poster: PW.p1_voice_poster },
};
