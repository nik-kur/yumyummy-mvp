/**
 * Mobile attribution: App Tracking Transparency (ATT) + AppsFlyer MMP.
 *
 * Why AppsFlyer: one SDK manages install attribution + SKAdNetwork conversion
 * values across Meta, TikTok and Google, which is what we need for day-one
 * paid campaigns. Purchase revenue is additionally sent server-to-server from
 * Adapty (dashboard integrations), so ad networks can optimize toward paid
 * conversions even under iOS privacy limits.
 *
 * Everything is gated on `EXPO_PUBLIC_APPSFLYER_DEV_KEY` and lazy-requires the
 * native module, so with no key (or in Expo Go where the native module is
 * absent) every function is an inert no-op — the app keeps working.
 */
import {
  getTrackingPermissionsAsync,
  requestTrackingPermissionsAsync,
} from 'expo-tracking-transparency';

// AppsFlyer credentials. dev key comes from the AppsFlyer dashboard; appId is
// the numeric Apple App Store id (iOS only). Both injected at build time.
const AF_DEV_KEY = process.env.EXPO_PUBLIC_APPSFLYER_DEV_KEY ?? '';
const AF_APP_ID = process.env.EXPO_PUBLIC_APPSFLYER_APP_ID ?? '';

let started = false;

/** True when an AppsFlyer dev key is configured for this build. */
export function isAppsFlyerConfigured(): boolean {
  return AF_DEV_KEY.length > 0;
}

/**
 * Show the iOS ATT prompt once (no-op if already answered or unsupported).
 * Returns whether tracking is authorized. Safe to call anywhere.
 */
export async function requestTrackingConsent(): Promise<boolean> {
  try {
    const current = await getTrackingPermissionsAsync();
    if (current.status === 'undetermined' && current.canAskAgain) {
      const res = await requestTrackingPermissionsAsync();
      return res.status === 'granted';
    }
    return current.status === 'granted';
  } catch {
    return false;
  }
}

function loadAppsFlyer(): any | null {
  try {
    // Lazy require: native module is absent in Expo Go / when not installed.
    const mod = require('react-native-appsflyer');
    return mod?.default ?? mod ?? null;
  } catch {
    return null;
  }
}

/**
 * Ask for ATT, then start AppsFlyer. Idempotent — the first call wins.
 * Called once at launch from the root layout.
 */
export async function initAttribution(): Promise<void> {
  if (started) return;
  started = true;

  // Prompt for ATT first so the IDFA (if granted) is available to AppsFlyer
  // and SKAdNetwork when the SDK starts.
  await requestTrackingConsent();

  if (!isAppsFlyerConfigured()) return;
  const appsFlyer = loadAppsFlyer();
  if (!appsFlyer) return;

  try {
    appsFlyer.initSdk(
      {
        devKey: AF_DEV_KEY,
        appId: AF_APP_ID,
        isDebug: __DEV__,
        onInstallConversionDataListener: false,
        // Give the user up to 15s to answer ATT before AppsFlyer sends the
        // install postback, so the IDFA is included when granted.
        timeToWaitForATTUserAuthorization: 15,
      },
      () => {},
      () => {},
    );
  } catch {
    // never let attribution setup break app launch
  }
}

/** Bind AppsFlyer's customer id to our account id (matches Adapty/PostHog). */
export function setAttributionCustomerId(accountId: number | string): void {
  if (!isAppsFlyerConfigured()) return;
  const appsFlyer = loadAppsFlyer();
  if (!appsFlyer) return;
  try {
    appsFlyer.setCustomerUserId(String(accountId), () => {});
  } catch {
    // non-fatal
  }
}

/** Log a custom AppsFlyer event (e.g. trial/subscription). No-op if unconfigured. */
export function logAttributionEvent(
  name: string,
  values: Record<string, unknown> = {},
): void {
  if (!isAppsFlyerConfigured()) return;
  const appsFlyer = loadAppsFlyer();
  if (!appsFlyer) return;
  try {
    appsFlyer.logEvent(name, values, () => {}, () => {});
  } catch {
    // non-fatal
  }
}
