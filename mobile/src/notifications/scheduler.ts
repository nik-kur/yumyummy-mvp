import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Notifications from 'expo-notifications';

import { loadPrefs, type NotificationPrefs, type ReminderPref } from './prefs';
import { loadJourney, rawDay } from '@/state/journey';

/**
 * Local notification scheduling. Everything here is on-device: we schedule
 * repeating daily triggers with the OS and never talk to a push server. The
 * single source of truth is `NotificationPrefs`; `syncFromPrefs` is idempotent
 * (it cancels everything we own, then re-schedules), so callers can fire it
 * after any pref change or on app launch.
 *
 * First-week activation (Задача from build-38 feedback): while the journey is
 * in days 1–7 we additionally schedule one-off MORNING pushes for the
 * remaining days — different copy each day — pointing at the daily quests.
 * The evening check-in ("did you log everything?") is a regular repeating
 * reminder that stays on after week one, alongside the weekly recap.
 *
 * One notification outlives prefs changes: the trial-ending nudge. Its fire
 * time is stored at purchase and re-armed on every sync, because the purchase
 * happens before the user has been asked for push permission.
 */

const ANDROID_CHANNEL_ID = 'reminders';
const IDENTIFIER_PREFIX = 'yum.reminder.';
const WEEKLY_RECAP_ID = 'yum.weekly.recap';
const QUEST_NUDGE_PREFIX = 'yum.quest.morning.';
const TRIAL_REMINDER_ID = 'yum.trial.ending';
const TRIAL_REMINDER_KEY = '@yy_trial_reminder_at';

/**
 * The one-off nudge before a free trial converts. Kept as data so the copy and
 * the timing can be changed over the air without a new binary.
 *
 * 48 hours after the trial starts is 24 hours before the first charge on the
 * 3-day trials we sell — early enough to be a courtesy rather than a surprise,
 * late enough that the user has had a real day with the app.
 */
export const TRIAL_ENDING_REMINDER = {
  delayHours: 48,
  title: 'Your free trial',
  body: 'You have 1 more day of your free trial. Have you tried photo logging yet?',
  route: '/capture?mode=photo',
} as const;

/** Per-reminder copy. Falls back to a generic nudge for unknown ids so adding a
 *  reminder to prefs never ships an empty notification. */
const CONTENT: Record<string, { title: string; body: string }> = {
  breakfast: { title: 'Breakfast time', body: 'Log what you’re having to start the day on track.' },
  lunch: { title: 'Lunch break?', body: 'Tap to log your meal — it takes a few seconds.' },
  dinner: { title: 'Dinner time', body: 'Log it now so your day stays accurate.' },
  evening: {
    title: 'How did today go?',
    body: 'The day’s almost over — add any meals you haven’t logged yet so today counts.',
  },
};

/** Morning quest nudges for journey days 2–7 — habit framing, varied wording
 *  so the first week never sends the same push twice. Fired at 10:30 local. */
const MORNING_HOUR = 10;
const MORNING_MINUTE = 30;
const MORNING_NUDGES: Record<number, { title: string; body: string }> = {
  2: {
    title: 'Day 2 is ready 🌱',
    body: 'Two small quests today. Two minutes now — that’s how the habit starts.',
  },
  3: {
    title: 'Faster ways to log 📷',
    body: 'Today: try a photo and a voice log, and tidy up your diary.',
  },
  4: {
    title: 'Eating out? We’ve got it 🍽️',
    body: 'Today’s quest: log a meal from a cafe or restaurant.',
  },
  5: {
    title: 'Fix any meal ✏️',
    body: 'Today’s quest: edit a logged meal to get its numbers just right.',
  },
  6: {
    title: 'Almost there ⚡',
    body: 'Day 6 of 7 — check your Week trends and keep the streak alive.',
  },
  7: {
    title: 'Final day — meet your advisor 💬',
    body: 'Today’s quest: ask your AI advisor anything. It knows your plan.',
  },
};

function contentFor(r: ReminderPref): { title: string; body: string } {
  return CONTENT[r.id] ?? { title: r.label, body: 'Tap to log a meal in YumYummy.' };
}

let handlerConfigured = false;

/** Show banners + play sound even when the app is foregrounded. Idempotent. */
export function configureNotificationHandler(): void {
  if (handlerConfigured) return;
  handlerConfigured = true;
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  });
}

export async function getPermissionGranted(): Promise<boolean> {
  try {
    const { granted } = await Notifications.getPermissionsAsync();
    return granted;
  } catch {
    return false;
  }
}

/** Ask the OS for permission. Returns whether it ended up granted. */
export async function requestPermission(): Promise<boolean> {
  try {
    const existing = await Notifications.getPermissionsAsync();
    if (existing.granted) return true;
    const req = await Notifications.requestPermissionsAsync();
    return req.granted;
  } catch {
    return false;
  }
}

async function ensureAndroidChannel(): Promise<void> {
  if (Platform.OS !== 'android') return;
  try {
    await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL_ID, {
      name: 'Meal reminders',
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  } catch {
    // Non-fatal: channel may already exist or platform unsupported.
  }
}

async function cancelOurNotifications(): Promise<void> {
  try {
    await Notifications.cancelAllScheduledNotificationsAsync();
  } catch {
    // ignore
  }
}

/**
 * Put the stored trial nudge back on the OS schedule. Separate from the
 * scheduling call because `syncFromPrefs` wipes everything we own before
 * re-scheduling, and because at purchase time the user usually hasn't granted
 * push permission yet — the intent is stored then and honoured here, the first
 * time both the master switch and permission are in place.
 *
 * No-op when nothing is stored or the moment has already passed.
 */
async function scheduleStoredTrialReminder(): Promise<void> {
  let iso: string | null = null;
  try {
    iso = await AsyncStorage.getItem(TRIAL_REMINDER_KEY);
  } catch {
    return;
  }
  if (!iso) return;

  const fireAt = new Date(iso);
  if (Number.isNaN(fireAt.getTime()) || fireAt.getTime() <= Date.now()) return;

  try {
    await Notifications.scheduleNotificationAsync({
      identifier: TRIAL_REMINDER_ID,
      content: {
        title: TRIAL_ENDING_REMINDER.title,
        body: TRIAL_ENDING_REMINDER.body,
        data: { route: TRIAL_ENDING_REMINDER.route },
      },
      trigger: {
        type: Notifications.SchedulableTriggerInputTypes.DATE,
        date: fireAt,
        channelId: ANDROID_CHANNEL_ID,
      },
    });
  } catch {
    // non-fatal
  }
}

/**
 * Arm the pre-conversion nudge for a trial that started at `trialStartedAt`.
 * Call this only for purchases that actually carry a free-trial phase —
 * customers who already used their one introductory offer are charged straight
 * away and would find the message untrue.
 */
export async function scheduleTrialEndingReminder(trialStartedAt: Date): Promise<void> {
  const fireAt = new Date(
    trialStartedAt.getTime() + TRIAL_ENDING_REMINDER.delayHours * 60 * 60 * 1000,
  );
  try {
    await AsyncStorage.setItem(TRIAL_REMINDER_KEY, fireAt.toISOString());
  } catch {
    // The nudge is a nicety; losing it must never fail a purchase.
    return;
  }

  const prefs = await loadPrefs();
  if (!prefs.enabled) return;
  if (!(await getPermissionGranted())) return;
  await ensureAndroidChannel();
  await scheduleStoredTrialReminder();
}

/**
 * Reconcile the OS schedule with `prefs`. No-ops gracefully when notifications
 * are off or permission is missing (we still clear anything we'd scheduled, so
 * turning the master switch off immediately stops reminders).
 */
export async function syncFromPrefs(prefs: NotificationPrefs): Promise<void> {
  await cancelOurNotifications();
  if (!prefs.enabled) return;
  const granted = await getPermissionGranted();
  if (!granted) return;

  await ensureAndroidChannel();
  for (const r of prefs.reminders) {
    if (!r.enabled) continue;
    const { title, body } = contentFor(r);
    try {
      await Notifications.scheduleNotificationAsync({
        identifier: `${IDENTIFIER_PREFIX}${r.id}`,
        content: { title, body, data: { route: '/capture' } },
        trigger: {
          type: Notifications.SchedulableTriggerInputTypes.DAILY,
          hour: r.hour,
          minute: r.minute,
          channelId: ANDROID_CHANNEL_ID,
        },
      });
    } catch {
      // Skip a single bad reminder rather than aborting the whole sync.
    }
  }

  // First-week activation: one-off morning pushes for the remaining journey
  // days (2–7), each with its own wording. Nothing is scheduled past day 7 —
  // after the first week the user keeps only the evening check-in + recap.
  try {
    const journey = await loadJourney();
    if (journey.started_at && !journey.dismissed) {
      const today = rawDay(journey.started_at);
      const start = new Date(journey.started_at);
      for (let day = Math.max(2, today); day <= 7; day++) {
        const nudge = MORNING_NUDGES[day];
        if (!nudge) continue;
        const fireAt = new Date(
          start.getFullYear(),
          start.getMonth(),
          start.getDate() + (day - 1),
          MORNING_HOUR,
          MORNING_MINUTE,
          0,
        );
        if (fireAt.getTime() <= Date.now()) continue; // today's slot already passed
        await Notifications.scheduleNotificationAsync({
          identifier: `${QUEST_NUDGE_PREFIX}${day}`,
          content: { title: nudge.title, body: nudge.body, data: { route: '/' } },
          trigger: {
            type: Notifications.SchedulableTriggerInputTypes.DATE,
            date: fireAt,
            channelId: ANDROID_CHANNEL_ID,
          },
        });
      }
    }
  } catch {
    // non-fatal
  }

  await scheduleStoredTrialReminder();

  // Weekly "Week in Recap" nudge → opens the Recap screen when tapped.
  if (prefs.weeklyRecap?.enabled) {
    try {
      await Notifications.scheduleNotificationAsync({
        identifier: WEEKLY_RECAP_ID,
        content: {
          title: 'Your weekly recap is ready',
          body: 'See how your week went — tap to open your recap.',
          data: { route: '/recap' },
        },
        trigger: {
          type: Notifications.SchedulableTriggerInputTypes.WEEKLY,
          weekday: prefs.weeklyRecap.weekday,
          hour: prefs.weeklyRecap.hour,
          minute: prefs.weeklyRecap.minute,
          channelId: ANDROID_CHANNEL_ID,
        },
      });
    } catch {
      // Non-fatal: keep daily reminders even if the weekly trigger fails.
    }
  }
}
