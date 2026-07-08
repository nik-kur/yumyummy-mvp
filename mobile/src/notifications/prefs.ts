import * as SecureStore from 'expo-secure-store';

/**
 * On-device notification preferences. These are intentionally LOCAL (stored on
 * the device, scheduled by the OS via expo-notifications) — no server / push
 * token is involved, so reminders work offline and need no APNs setup.
 */
export interface ReminderPref {
  /** Stable id; also the scheduled-notification identifier (see scheduler). */
  id: string;
  label: string;
  hour: number; // 0–23
  minute: number; // 0–59
  enabled: boolean;
}

/** Weekly "Week in Recap" nudge (Задача 6). A single local WEEKLY trigger that
 *  opens the Recap screen when tapped. Weekday uses the expo-notifications
 *  convention: 1 = Sunday … 7 = Saturday. */
export interface WeeklyRecapPref {
  enabled: boolean;
  weekday: number;
  hour: number;
  minute: number;
}

export interface NotificationPrefs {
  /** Master switch. While off, nothing is scheduled regardless of reminders. */
  enabled: boolean;
  reminders: ReminderPref[];
  weeklyRecap: WeeklyRecapPref;
}

const STORAGE_KEY = 'yumyummy.notif.prefs.v1';

/** Built-in reminders. Master defaults OFF so we never schedule (or prompt for
 *  permission) until the user opts in; individual reminders default ON so that
 *  flipping the master switch immediately gives a sensible daily set. */
export const DEFAULT_PREFS: NotificationPrefs = {
  enabled: false,
  reminders: [
    { id: 'breakfast', label: 'Breakfast', hour: 9, minute: 0, enabled: true },
    { id: 'lunch', label: 'Lunch', hour: 13, minute: 0, enabled: true },
    { id: 'dinner', label: 'Dinner', hour: 19, minute: 0, enabled: true },
    { id: 'evening', label: 'Evening check-in', hour: 21, minute: 0, enabled: true },
  ],
  // Sunday 18:00 — "Your weekly recap is ready".
  weeklyRecap: { enabled: true, weekday: 1, hour: 18, minute: 0 },
};

function clampInt(v: unknown, min: number, max: number, fallback: number): number {
  const n = typeof v === 'number' ? Math.round(v) : NaN;
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, n));
}

/** Merge a stored blob onto the current defaults so newly-added built-in
 *  reminders appear for existing users, while keeping their saved times. */
function reconcile(stored: Partial<NotificationPrefs> | null): NotificationPrefs {
  if (!stored || typeof stored !== 'object') return clone(DEFAULT_PREFS);
  const byId = new Map<string, ReminderPref>();
  for (const r of stored.reminders ?? []) {
    if (r && typeof r.id === 'string') {
      byId.set(r.id, {
        id: r.id,
        label: String(r.label ?? r.id),
        hour: clampInt(r.hour, 0, 23, 9),
        minute: clampInt(r.minute, 0, 59, 0),
        enabled: Boolean(r.enabled),
      });
    }
  }
  const reminders = DEFAULT_PREFS.reminders.map((def) => byId.get(def.id) ?? { ...def });
  const sr = stored.weeklyRecap;
  const weeklyRecap: WeeklyRecapPref = sr && typeof sr === 'object'
    ? {
        enabled: Boolean(sr.enabled),
        weekday: clampInt(sr.weekday, 1, 7, DEFAULT_PREFS.weeklyRecap.weekday),
        hour: clampInt(sr.hour, 0, 23, DEFAULT_PREFS.weeklyRecap.hour),
        minute: clampInt(sr.minute, 0, 59, DEFAULT_PREFS.weeklyRecap.minute),
      }
    : { ...DEFAULT_PREFS.weeklyRecap };
  return { enabled: Boolean(stored.enabled), reminders, weeklyRecap };
}

function clone(p: NotificationPrefs): NotificationPrefs {
  return {
    enabled: p.enabled,
    reminders: p.reminders.map((r) => ({ ...r })),
    weeklyRecap: { ...p.weeklyRecap },
  };
}

export async function loadPrefs(): Promise<NotificationPrefs> {
  try {
    const raw = await SecureStore.getItemAsync(STORAGE_KEY);
    if (!raw) return clone(DEFAULT_PREFS);
    return reconcile(JSON.parse(raw));
  } catch {
    return clone(DEFAULT_PREFS);
  }
}

export async function savePrefs(prefs: NotificationPrefs): Promise<void> {
  try {
    await SecureStore.setItemAsync(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // Best-effort; scheduling still happens from the in-memory copy.
  }
}

/** "9:05" / "13:00" — zero-padded minutes, 24h (matches the rest of the app). */
export function formatTime(hour: number, minute: number): string {
  return `${hour}:${String(minute).padStart(2, '0')}`;
}
