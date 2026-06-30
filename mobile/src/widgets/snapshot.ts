import { Platform } from 'react-native';

import type { AccountProfile, DaySummary } from '@/api/types';

const APP_GROUP = 'group.ai.yumyummy.app';
const STORAGE_KEY = 'today';

/**
 * Pushes today's calorie/macro totals into the iOS App Group so the home- and
 * lock-screen widgets can render them, then asks WidgetKit to redraw.
 *
 * No-ops on Android and in Expo Go / dev where the native module is absent.
 */
export function updateWidgetSnapshot(
  day: DaySummary | null,
  profile: AccountProfile | null,
): void {
  if (Platform.OS !== 'ios') return;

  try {
    // Lazy require: the native module only exists in dev/production builds that
    // include @bacons/apple-targets, never in Expo Go.
    const { ExtensionStorage } = require('@bacons/apple-targets');

    const snapshot = {
      eaten: Math.round(day?.total_calories ?? 0),
      goal: Math.round(profile?.target_calories ?? 0),
      protein: Math.round(day?.total_protein_g ?? 0),
      proteinGoal: Math.round(profile?.target_protein_g ?? 0),
      carbs: Math.round(day?.total_carbs_g ?? 0),
      carbsGoal: Math.round(profile?.target_carbs_g ?? 0),
      fat: Math.round(day?.total_fat_g ?? 0),
      fatGoal: Math.round(profile?.target_fat_g ?? 0),
      date: day?.date ?? '',
      updatedAt: Date.now() / 1000,
    };

    const storage = new ExtensionStorage(APP_GROUP);
    storage.set(STORAGE_KEY, JSON.stringify(snapshot));
    ExtensionStorage.reloadWidget();
  } catch {
    // Native module unavailable — safe to ignore.
  }
}
