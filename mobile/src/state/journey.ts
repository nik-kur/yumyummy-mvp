/**
 * "Your First Week" journey — quest ladder v2.1 (Day0_Activation_Spec_v2.md).
 *
 * 7 days from purchase, ≤3 quests a day, auto-detected from domain events.
 * Nothing blocks and nothing resets: quests from past days stay detectable
 * forever. Completion popups queue up and show one at a time on Today.
 *
 * State persists in AsyncStorage. Screens report domain events through
 * `reportJourneyEvent`; the matcher below turns them into completions.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

import { track } from '@/analytics/posthog';

const KEY = '@yy_journey';

// ---------------------------------------------------------------------------
// Ladder config (v2.1)
// ---------------------------------------------------------------------------

export type QuestId =
  | 'plan_built'
  | 'first_log'
  | 'reminders'
  | 'widget'
  | 'full_day'
  | 'menu'
  | 'insight'
  | 'photo_log'
  | 'voice_log'
  | 'restaurant_log'
  | 'ai_question'
  | 'week_trends'
  | 'weigh_in';

export interface QuestDef {
  id: QuestId;
  day: number;
  title: string;
  /** Numeric goal for progress quests (full_day = 3 logs, menu = 2 saved). */
  target?: number;
  precompleted?: boolean;
}

export interface DayDef {
  day: number;
  title: string;
  unlock: string;
  quests: QuestDef[];
}

export const LADDER: DayDef[] = [
  {
    day: 1,
    title: 'Start',
    unlock: 'Tomorrow: close your first full day',
    quests: [
      { id: 'plan_built', day: 1, title: 'Plan built', precompleted: true },
      { id: 'first_log', day: 1, title: 'Log your first meal' },
      { id: 'reminders', day: 1, title: 'Turn on reminders' },
      { id: 'widget', day: 1, title: 'Add the YumYummy widget 📱' },
    ],
  },
  {
    day: 2,
    title: 'Make it yours',
    unlock: 'Tomorrow unlocks: your first insight ✨',
    quests: [
      { id: 'full_day', day: 2, title: 'Close a full day', target: 3 },
      { id: 'menu', day: 2, title: 'Build your menu', target: 2 },
    ],
  },
  {
    day: 3,
    // The first insight still lands on Day 3 (see Today), it's just not a
    // quest anymore — checking a card felt like a chore, not an achievement.
    title: 'Faster ways to log',
    unlock: 'Your plan is already working — see what we spotted',
    quests: [
      { id: 'photo_log', day: 3, title: 'Try a photo log 📷' },
      { id: 'voice_log', day: 3, title: 'Try a voice log 🎤' },
    ],
  },
  {
    day: 4,
    title: 'Eating out — handled',
    unlock: 'Eating out — handled',
    quests: [{ id: 'restaurant_log', day: 4, title: 'Log a meal you didn’t cook 🍽️' }],
  },
  {
    day: 5,
    title: 'Meet your AI advisor',
    unlock: 'It knows your plan and your day',
    quests: [{ id: 'ai_question', day: 5, title: 'Ask your AI advisor anything' }],
  },
  {
    day: 6,
    title: 'Explore your Week trends',
    unlock: 'Tomorrow: your Week 1 Report',
    quests: [{ id: 'week_trends', day: 6, title: 'Explore your Week trends 📊' }],
  },
  {
    day: 7,
    title: 'Weigh-in + Week 1 Report',
    unlock: 'Week 1 Report is ready',
    quests: [{ id: 'weigh_in', day: 7, title: 'Update your weight ⚖️' }],
  },
];

export const ALL_QUESTS: QuestDef[] = LADDER.flatMap((d) => d.quests);

/** Why-it-matters copy for completion popups (spec §3, final EN). */
export const QUEST_WHY: Record<QuestId, { title: string; why: string }> = {
  plan_built: { title: 'Plan built', why: 'Your targets are set — everything you log now counts against them.' },
  first_log: {
    title: 'First log',
    why: 'That was the single highest-impact habit in nutrition. People who log consistently lose about 2× more weight — and your first one took seconds.',
  },
  reminders: {
    title: 'Reminders on',
    why: 'People who turn on reminders stick with tracking 3× longer. We’ll nudge gently — never nag.',
  },
  widget: {
    title: 'Widget added',
    why: 'Your budget, on your home screen — kcal left without even opening the app. Seeing the number mid-day is what keeps most people on target.',
  },
  full_day: {
    title: 'Full day closed',
    why: 'A full day is when your numbers start meaning something. Your ring now shows the real picture — not a guess.',
  },
  menu: {
    title: 'Menu built',
    why: 'Saved meals log in one tap. Most members log their regulars in under 5 seconds.',
  },
  insight: {
    title: 'First insight',
    why: 'This came from your own two days of data. The longer you log, the sharper your insights get.',
  },
  photo_log: {
    title: 'Photo log',
    why: 'Photo is one of the fastest ways to log — with zero loss in accuracy. YumYummy finds every dish in the shot, detects the brand or restaurant when there is one, and matches it to official nutrition data. All in about 10 seconds.',
  },
  voice_log: {
    title: 'Voice log',
    why: 'Voice is the fastest hands-free log — just say it like you’d tell a friend. YumYummy parses dishes, portions and brands from plain speech, then verifies the numbers.',
  },
  restaurant_log: {
    title: 'Eating out — handled',
    why: 'Eating out is where most trackers break — and most diets stall. YumYummy matched your meal to official restaurant data, so your numbers stayed right.',
  },
  ai_question: {
    title: 'Advisor unlocked',
    why: 'Your AI advisor sees your plan, your day and your habits. The more you ask, the more personal it gets.',
  },
  week_trends: {
    title: 'Trends explored',
    why: 'Single days lie — trends don’t. Six days in, your Week view starts showing the patterns that actually move the scale.',
  },
  weigh_in: {
    title: 'Weigh-in done',
    why: 'Weight closes the loop: your graph now shows plan vs reality — and your targets can adapt to it.',
  },
};

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

export interface JourneyState {
  version: 2;
  /** Purchase timestamp; journey inactive until set. */
  started_at: string | null;
  /** questId → completed_at ISO. */
  quests: Partial<Record<QuestId, string>>;
  /**
   * questId → ISO of the first time the user actually DID the action, even if
   * the quest's day was still locked at that moment. Doing something early is
   * never wasted: the quest auto-completes the moment its day unlocks.
   */
  actions: Partial<Record<QuestId, string>>;
  /** Local counters for multi-step quests (menu ≥2). */
  counters: { menu: number };
  /** Completion popups not yet shown, oldest first. */
  popups_pending: QuestId[];
  /** True once the card is permanently hidden (ignored past Day 10). */
  dismissed: boolean;
}

const DEFAULT_STATE: JourneyState = {
  version: 2,
  started_at: null,
  quests: {},
  actions: {},
  counters: { menu: 0 },
  popups_pending: [],
  dismissed: false,
};

/** v1 (build ≤36) quest keys → v2.1 ids. */
const V1_QUEST_MAP: Record<string, QuestId> = {
  log_first_meal: 'first_log',
  log_3_meals: 'full_day',
  check_insight: 'insight',
  try_photo: 'photo_log',
  save_meal: 'menu',
  add_widget: 'widget',
};

function migrate(raw: Record<string, unknown>): JourneyState {
  if (raw.version === 2) {
    const s = raw as unknown as JourneyState;
    return {
      ...DEFAULT_STATE,
      ...s,
      counters: { ...DEFAULT_STATE.counters, ...(s.counters ?? {}) },
      quests: s.quests ?? {},
      actions: s.actions ?? {},
      popups_pending: s.popups_pending ?? [],
    };
  }
  // v1 → v2: keep started_at, carry over completions under new ids.
  const quests: Partial<Record<QuestId, string>> = {};
  const startedAt = typeof raw.started_at === 'string' ? raw.started_at : null;
  const completed = (raw.completed ?? {}) as Record<string, boolean>;
  for (const [oldId, done] of Object.entries(completed)) {
    const id = V1_QUEST_MAP[oldId];
    if (id && done) quests[id] = startedAt ?? new Date().toISOString();
  }
  if (startedAt) quests.plan_built = startedAt;
  return { ...DEFAULT_STATE, started_at: startedAt, quests };
}

export async function loadJourney(): Promise<JourneyState> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return DEFAULT_STATE;
    return migrate(JSON.parse(raw));
  } catch {
    return DEFAULT_STATE;
  }
}

export async function saveJourney(state: JourneyState): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(state)).catch(() => {});
}

/** Idempotent: marks the journey started (= purchase moment) and pre-completes `plan_built`. */
export async function startJourney(): Promise<void> {
  const s = await loadJourney();
  if (s.started_at) return;
  const now = new Date().toISOString();
  await saveJourney({ ...s, started_at: now, quests: { ...s.quests, plan_built: now } });
  notify();
}

// ---------------------------------------------------------------------------
// Day math
// ---------------------------------------------------------------------------

/** Local midnight for a date — day boundaries follow the user's clock. */
function startOfDay(d: Date): number {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

/**
 * Uncapped journey day (1 = purchase day); 0 when not started.
 * Counted in CALENDAR days, local time: Day 2 begins at the first local
 * midnight after purchase — not 24h later. This is the streak gate: quests
 * of day N can only be done on the N-th calendar day of the journey.
 */
export function rawDay(startedAt: string | null): number {
  if (!startedAt) return 0;
  const start = new Date(startedAt);
  if (Number.isNaN(start.getTime())) return 0;
  const days = Math.floor((startOfDay(new Date()) - startOfDay(start)) / (1000 * 60 * 60 * 24));
  return days + 1;
}

/** Journey day capped to the 7-day ladder. */
export function currentDay(startedAt: string | null): number {
  return Math.min(rawDay(startedAt), 7);
}

export function isCompleted(state: JourneyState, id: QuestId): boolean {
  return Boolean(state.quests[id]);
}

export function completedCount(state: JourneyState): number {
  return ALL_QUESTS.filter((q) => isCompleted(state, q.id)).length;
}

/** Completed anything the user actually did (excludes endowed plan_built)? */
export function hasUserProgress(state: JourneyState): boolean {
  return ALL_QUESTS.some((q) => !q.precompleted && isCompleted(state, q.id));
}

/** First incomplete quest, today's day first, then earlier days (for "Next up"). */
export function nextQuest(state: JourneyState, day: number): QuestDef | null {
  const unlocked = ALL_QUESTS.filter((q) => isDayUnlocked(state, q.day));
  const ordered = [
    ...unlocked.filter((q) => q.day === day),
    ...unlocked.filter((q) => q.day < day),
    ...unlocked.filter((q) => q.day > day),
  ];
  return ordered.find((q) => !isCompleted(state, q.id)) ?? null;
}

// ---------------------------------------------------------------------------
// Day locking (sequential unlock)
// ---------------------------------------------------------------------------
//
// Days unlock strictly in order: day D opens only when the calendar reached it
// AND every quest of days 1..D−1 is done. Actions performed while a quest's
// day is still locked ARE remembered (state.actions) and the quest completes
// automatically the moment its day unlocks — doing the thing "directly",
// outside the checklist, always counts.

/** All quests of `day` completed? */
export function dayCompleted(state: JourneyState, day: number): boolean {
  const def = LADDER.find((d) => d.day === day);
  if (!def) return false;
  return def.quests.every((q) => isCompleted(state, q.id));
}

function prevDaysCompleted(state: JourneyState, day: number): boolean {
  for (let d = 1; d < day; d++) {
    if (!dayCompleted(state, d)) return false;
  }
  return true;
}

/** Day is unlocked: journey started, calendar reached it, all previous days done. */
export function isDayUnlocked(state: JourneyState, day: number): boolean {
  if (!state.started_at) return false;
  if (day === 1) return true;
  return rawDay(state.started_at) >= day && prevDaysCompleted(state, day);
}

/** Highest unlocked day — the day the Today card shows. */
export function activeDay(state: JourneyState): number {
  let active = 1;
  for (let d = 2; d <= 7; d++) {
    if (isDayUnlocked(state, d)) active = d;
  }
  return active;
}

export type DayStatus = 'complete' | 'active' | 'preview' | 'locked';

/**
 * Status for the week-path overlay:
 * - complete — every quest done;
 * - active   — unlocked, in progress;
 * - preview  — all previous days done, only the calendar gate remains
 *              ("opens tomorrow", quests visible but locked);
 * - locked   — previous days unfinished; quest details hidden.
 */
export function dayStatus(state: JourneyState, day: number): DayStatus {
  if (dayCompleted(state, day)) return 'complete';
  if (isDayUnlocked(state, day)) return 'active';
  if (prevDaysCompleted(state, day)) return 'preview';
  return 'locked';
}

// ---------------------------------------------------------------------------
// Event bus → quest matcher
// ---------------------------------------------------------------------------

/** 'saved' = one-tap re-log; 'unknown' = reconciliation from Today's data. */
export type LogSource = 'text' | 'photo' | 'voice' | 'saved' | 'unknown';
/** Where the numbers came from: 'brand' = brand/restaurant official data. */
export type LogOrigin = 'generic' | 'brand';

export type JourneyEvent =
  | { type: 'log_created'; source: LogSource; origin?: LogOrigin; todayCount?: number }
  | { type: 'menu_item_created' }
  | { type: 'ai_message_sent' }
  | { type: 'weight_updated' }
  | { type: 'week_tab_viewed' }
  | { type: 'insight_viewed' }
  | { type: 'push_permission_granted' }
  | { type: 'widget_installed' };

type Listener = () => void;
const listeners = new Set<Listener>();

/** Subscribe to journey changes (Today re-loads state + shows popups). */
export function subscribeJourney(cb: Listener): () => void {
  listeners.add(cb);
  return () => listeners.delete(cb);
}

function notify(): void {
  listeners.forEach((cb) => {
    try {
      cb();
    } catch {
      // listener errors must not break the reporter
    }
  });
}

/**
 * Turn recorded actions into completions. A quest completes once its action
 * was performed AND its day is unlocked. Completing the last quest of a day
 * unlocks the next one, which may hold actions the user already did — so we
 * loop until stable. Mutates `s`, returns newly completed ids in ladder order.
 */
function settle(s: JourneyState): QuestId[] {
  const completed: QuestId[] = [];
  let changed = true;
  while (changed) {
    changed = false;
    for (const def of ALL_QUESTS) {
      if (s.quests[def.id] || !s.actions[def.id]) continue;
      if (!isDayUnlocked(s, def.day)) continue;
      s.quests[def.id] = new Date().toISOString();
      completed.push(def.id);
      changed = true;
    }
  }
  return completed;
}

/** Persist `next` when it differs from `prev`, emit analytics + popups. */
async function commit(
  prev: JourneyState,
  next: JourneyState,
  completed: QuestId[],
): Promise<QuestId[]> {
  const changed =
    completed.length > 0 ||
    next.counters.menu !== prev.counters.menu ||
    Object.keys(next.actions).length !== Object.keys(prev.actions).length;
  if (!changed) return [];

  next.popups_pending = [...prev.popups_pending, ...completed];
  await saveJourney(next);

  const day = currentDay(next.started_at);
  for (const id of completed) {
    const def = ALL_QUESTS.find((q) => q.id === id);
    track('quest_completed', { quest: id, day: def?.day, journey_day: day });
  }
  if (completed.length > 0) notify();
  return completed;
}

/**
 * Re-check recorded actions against today's unlock state without a new event.
 * Call on Today load: a day can unlock overnight (calendar gate) and release
 * quests the user already performed earlier.
 */
export async function reconcileJourney(): Promise<QuestId[]> {
  const s = await loadJourney();
  if (!s.started_at) return [];
  const next: JourneyState = { ...s, quests: { ...s.quests }, actions: { ...s.actions } };
  const completed = settle(next);
  return commit(s, next, completed);
}

/**
 * Report a domain event. Records the action (even if its quest day is still
 * locked), settles completions, queues popups and emits `quest_completed`
 * analytics. No-ops until the journey has started. Returns newly completed ids.
 */
export async function reportJourneyEvent(event: JourneyEvent): Promise<QuestId[]> {
  const s = await loadJourney();
  if (!s.started_at) return [];

  const counters = { ...s.counters };
  const actions = { ...s.actions };

  // Doing the thing counts, whenever and however it happened — locked days
  // just defer the completion until the day opens (see settle()).
  const record = (id: QuestId) => {
    if (!actions[id]) actions[id] = new Date().toISOString();
  };

  switch (event.type) {
    case 'log_created':
      record('first_log');
      if (event.source === 'photo') record('photo_log');
      if (event.source === 'voice') record('voice_log');
      if (event.origin === 'brand') record('restaurant_log');
      if ((event.todayCount ?? 0) >= 3) record('full_day');
      break;
    case 'menu_item_created':
      counters.menu += 1;
      if (counters.menu >= 2) record('menu');
      break;
    case 'ai_message_sent':
      record('ai_question');
      break;
    case 'weight_updated':
      record('weigh_in');
      break;
    case 'week_tab_viewed':
      record('week_trends');
      break;
    case 'insight_viewed':
      // Insights are no longer a quest — they just appear on Today.
      break;
    case 'push_permission_granted':
      record('reminders');
      break;
    case 'widget_installed':
      record('widget');
      break;
  }

  const next: JourneyState = { ...s, counters, actions, quests: { ...s.quests } };
  const completed = settle(next);
  return commit(s, next, completed);
}

// ---------------------------------------------------------------------------
// Popup queue
// ---------------------------------------------------------------------------

// Catch-up popups (queued from a previous session) are limited to 1 per app
// session; popups for quests completed just now always show (spec §3).
let stalePopupShownThisSession = false;
const FRESH_MS = 10 * 60 * 1000;

/**
 * Pop the next pending popup, respecting the 1-stale-per-session rule.
 * Persists the dequeue; returns the quest to show, or null.
 */
export async function takeNextPopup(): Promise<QuestId | null> {
  const s = await loadJourney();
  if (!s.started_at || s.popups_pending.length === 0) return null;

  const id = s.popups_pending[0]!;
  const completedAt = s.quests[id] ? Date.parse(s.quests[id]!) : 0;
  const fresh = Date.now() - completedAt < FRESH_MS;
  if (!fresh && stalePopupShownThisSession) return null;
  if (!fresh) stalePopupShownThisSession = true;

  await saveJourney({ ...s, popups_pending: s.popups_pending.slice(1) });
  track('journey_popup_shown', { quest: id });
  return id;
}
