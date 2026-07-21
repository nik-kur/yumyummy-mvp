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
  | 'delete_meal'
  | 'restaurant_log'
  | 'edit_meal'
  | 'week_trends'
  | 'ai_question'
  | 'weigh_in'
  // Daily "log from My Menu" habit quest, one per day from Day 3 onward.
  | 'menu_log_3'
  | 'menu_log_4'
  | 'menu_log_5'
  | 'menu_log_6'
  | 'menu_log_7';

/** menu_log ids in day order — the daily "log from My Menu" habit quests. */
export const MENU_LOG_IDS: QuestId[] = [
  'menu_log_3',
  'menu_log_4',
  'menu_log_5',
  'menu_log_6',
  'menu_log_7',
];

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

// A "log from My Menu" quest for the given day (Days 3–7 each get one).
function menuLogQuest(day: number): QuestDef {
  return { id: `menu_log_${day}` as QuestId, day, title: 'Log a meal from My Menu 🍱' };
}

export const LADDER: DayDef[] = [
  {
    day: 1,
    title: 'Start',
    unlock: 'Log your first meal to get going.',
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
    unlock: 'Close a full day and save your go-to meals.',
    quests: [
      { id: 'full_day', day: 2, title: 'Close a full day', target: 3 },
      { id: 'menu', day: 2, title: 'Build your menu', target: 2 },
    ],
  },
  {
    day: 3,
    title: 'Faster ways to log',
    unlock: 'Photo, voice, and cleaning up your diary.',
    quests: [
      { id: 'photo_log', day: 3, title: 'Try a photo log 📷' },
      { id: 'voice_log', day: 3, title: 'Try a voice log 🎤' },
      { id: 'delete_meal', day: 3, title: 'Delete a meal you didn’t eat 🗑️' },
      menuLogQuest(3),
    ],
  },
  {
    day: 4,
    title: 'Eating out — handled',
    unlock: 'Log a cafe or restaurant meal.',
    quests: [
      { id: 'restaurant_log', day: 4, title: 'Log a meal from cafe/restaurant 🍽️' },
      menuLogQuest(4),
    ],
  },
  {
    day: 5,
    title: 'Fix a meal',
    unlock: 'Edit a logged meal to fix its numbers.',
    quests: [
      { id: 'edit_meal', day: 5, title: 'Edit a logged meal ✏️' },
      menuLogQuest(5),
    ],
  },
  {
    day: 6,
    title: 'Explore your Week trends',
    unlock: 'See how your first week is shaping up.',
    quests: [
      { id: 'week_trends', day: 6, title: 'Explore your Week trends 📊' },
      menuLogQuest(6),
    ],
  },
  {
    day: 7,
    title: 'Meet your AI advisor',
    unlock: 'Ask your advisor anything — it knows your plan.',
    quests: [
      { id: 'ai_question', day: 7, title: 'Ask your AI advisor anything 💬' },
      menuLogQuest(7),
    ],
  },
];

export const ALL_QUESTS: QuestDef[] = LADDER.flatMap((d) => d.quests);

const MENU_LOG_WHY = {
  title: 'Logged from your menu',
  why: 'Re-logging a saved meal is the fastest way to track — one tap, no waiting, no new search. Do it daily and tracking stops feeling like work.',
};

/** Why-it-matters copy for completion popups (spec §3, final EN).
 *  `sourceUrl` links the cited study when the copy makes a health claim
 *  (App Review Guideline 1.4.1). */
export const QUEST_WHY: Record<QuestId, { title: string; why: string; sourceUrl?: string }> = {
  plan_built: { title: 'Plan built', why: 'Your targets are set — everything you log now counts against them.' },
  first_log: {
    title: 'First log',
    why: 'That was the single highest-impact habit in nutrition. People who log consistently lose about 2× more weight — and your first one took seconds.',
    sourceUrl: 'https://pubmed.ncbi.nlm.nih.gov/18617080/',
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
  delete_meal: {
    title: 'Diary cleaned up',
    why: 'Logged something by mistake? Deleting it keeps your day honest — your numbers should always match what you actually ate.',
  },
  restaurant_log: {
    title: 'Eating out — handled',
    why: 'Eating out is where most trackers break — and most diets stall. YumYummy matched your meal to official restaurant data, so your numbers stayed right.',
  },
  edit_meal: {
    title: 'Meal fine-tuned',
    why: 'Portions vary — a bigger bowl, an extra spoon. Editing an entry keeps your calorie math accurate, and it takes two seconds.',
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
  menu_log_3: MENU_LOG_WHY,
  menu_log_4: MENU_LOG_WHY,
  menu_log_5: MENU_LOG_WHY,
  menu_log_6: MENU_LOG_WHY,
  menu_log_7: MENU_LOG_WHY,
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

/** First incomplete quest, today's day first, then earlier (overdue) days. */
export function nextQuest(state: JourneyState, day: number): QuestDef | null {
  const unlocked = ALL_QUESTS.filter((q) => isDayUnlocked(state, q.day));
  const ordered = [
    ...unlocked.filter((q) => q.day < day), // overdue catch-up first
    ...unlocked.filter((q) => q.day === day),
    ...unlocked.filter((q) => q.day > day),
  ];
  return ordered.find((q) => !isCompleted(state, q.id)) ?? null;
}

// ---------------------------------------------------------------------------
// Day progression (calendar-based, with catch-up)
// ---------------------------------------------------------------------------
//
// Days advance by the CALENDAR, not by completion: Day N's quests appear on the
// N-th calendar day whether or not earlier days are done. Unfinished quests
// from earlier days stay open as "catch-up"; while any are open the user is
// "behind" (shown with an amber ring). Doing a thing early still counts —
// state.actions is remembered and the quest completes the moment its day
// arrives (see settle()).

/** The calendar day the card is centred on (1..7); 0 when not started. */
export function activeDay(state: JourneyState): number {
  return state.started_at ? currentDay(state.started_at) : 0;
}

/** All quests of `day` completed? */
export function dayCompleted(state: JourneyState, day: number): boolean {
  const def = LADDER.find((d) => d.day === day);
  if (!def) return false;
  return def.quests.every((q) => isCompleted(state, q.id));
}

/** Day is unlocked once the calendar reaches it (no completion gate). */
export function isDayUnlocked(state: JourneyState, day: number): boolean {
  if (!state.started_at) return false;
  return rawDay(state.started_at) >= day;
}

/** Incomplete quests from days strictly before today — the catch-up backlog. */
export function overdueQuests(state: JourneyState): QuestDef[] {
  const today = activeDay(state);
  return ALL_QUESTS.filter((q) => q.day < today && !isCompleted(state, q.id));
}

/** User is behind when earlier-day quests are still open. */
export function isBehind(state: JourneyState): boolean {
  return overdueQuests(state).length > 0;
}

export type DayStatus = 'complete' | 'active' | 'overdue' | 'preview';

/**
 * Status for the week-path overlay:
 * - complete — every quest done;
 * - active   — today's day (calendar), in progress;
 * - overdue  — a past day with quests still open (catch-up);
 * - preview  — a future day not reached yet.
 */
export function dayStatus(state: JourneyState, day: number): DayStatus {
  if (dayCompleted(state, day)) return 'complete';
  const today = activeDay(state);
  if (day < today) return 'overdue';
  if (day === today) return 'active';
  return 'preview';
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
  | { type: 'meal_deleted' }
  | { type: 'meal_edited' }
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

  // Doing the thing counts, whenever and however it happened — a day not yet
  // reached just defers the completion until it opens (see settle()).
  const record = (id: QuestId) => {
    if (!actions[id]) actions[id] = new Date().toISOString();
  };

  // A "log from My Menu" clears the oldest still-open daily menu quest (up to
  // today). This makes the daily habit catch-up-able: one saved re-log always
  // moves the backlog forward instead of stranding a past day forever.
  const recordMenuLog = () => {
    const today = activeDay(s);
    for (const id of MENU_LOG_IDS) {
      const day = Number(id.split('_')[2]);
      if (day > today) break;
      if (!s.quests[id] && !actions[id]) {
        record(id);
        return;
      }
    }
  };

  switch (event.type) {
    case 'log_created':
      record('first_log');
      if (event.source === 'photo') record('photo_log');
      if (event.source === 'voice') record('voice_log');
      if (event.origin === 'brand') record('restaurant_log');
      if (event.source === 'saved') recordMenuLog();
      if ((event.todayCount ?? 0) >= 3) record('full_day');
      break;
    case 'menu_item_created':
      counters.menu += 1;
      if (counters.menu >= 2) record('menu');
      break;
    case 'meal_deleted':
      record('delete_meal');
      break;
    case 'meal_edited':
      record('edit_meal');
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
