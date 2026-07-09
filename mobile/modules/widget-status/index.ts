import { Platform } from 'react-native';

let nativeModule: { getInstalledWidgets: () => Promise<string[]> } | null = null;

try {
  if (Platform.OS === 'ios') {
    const { requireNativeModule } = require('expo-modules-core');
    nativeModule = requireNativeModule('WidgetStatus');
  }
} catch {
  // Native module unavailable (Expo Go / Android)
}

/**
 * Returns an array of widget `kind` strings currently installed on the user's
 * home or lock screen. Returns `[]` on Android, in Expo Go, or if the native
 * module is not available.
 *
 * Known kinds from `Widgets.swift`:
 *  - `YumYummyBalance`
 *  - `YumYummyQuick`
 *  - `YumYummyCombo`
 */
export async function getInstalledWidgets(): Promise<string[]> {
  if (!nativeModule) return [];
  try {
    return await nativeModule.getInstalledWidgets();
  } catch {
    return [];
  }
}

export async function isAnyWidgetInstalled(): Promise<boolean> {
  const widgets = await getInstalledWidgets();
  return widgets.length > 0;
}
