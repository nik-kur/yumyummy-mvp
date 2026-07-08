import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';

import type { NotificationPrefs, ReminderPref } from './prefs';

/**
 * Local notification scheduling. Everything here is on-device: we schedule
 * repeating daily triggers with the OS and never talk to a push server. The
 * single source of truth is `NotificationPrefs`; `syncFromPrefs` is idempotent
 * (it cancels everything we own, then re-schedules), so callers can fire it
 * after any pref change or on app launch.
 */

const ANDROID_CHANNEL_ID = 'reminders';
const IDENTIFIER_PREFIX = 'yum.reminder.';
const WEEKLY_RECAP_ID = 'yum.weekly.recap';

/** Per-reminder copy. Falls back to a generic nudge for unknown ids so adding a
 *  reminder to prefs never ships an empty notification. */
const CONTENT: Record<string, { title: string; body: string }> = {
  breakfast: { title: 'Breakfast time', body: 'Log what you’re having to start the day on track.' },
  lunch: { title: 'Lunch break?', body: 'Tap to log your meal — it takes a few seconds.' },
  dinner: { title: 'Dinner time', body: 'Log it now so your day stays accurate.' },
  evening: { title: 'How did today go?', body: 'Add any meals you haven’t logged yet before the day ends.' },
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
