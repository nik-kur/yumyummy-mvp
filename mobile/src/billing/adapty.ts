/**
 * Adapty SDK lifecycle helpers.
 *
 * Adapty owns App Store / Play purchases. We activate it once at launch and
 * bind it to our account via `identify(account_id)` so the Adapty webhook maps
 * back to the right account (see `app/api/adapty_webhook.py`, which keys on
 * `customer_user_id == account_id`).
 *
 * Everything degrades gracefully: when no public SDK key is configured (Expo
 * Go, or a build before the key is set), these helpers no-op and the paywall
 * falls back to its static UI so the rest of the app stays usable.
 */
import { Platform } from 'react-native';
import { adapty, LogLevel } from 'react-native-adapty';

/** Access level configured in Adapty; both yearly & monthly unlock `premium`. */
export const PREMIUM_ACCESS_LEVEL = 'premium';

/** Placement IDs hardcoded in the app; paywall/A-B routing lives in the dashboard. */
export const ADAPTY_PLACEMENT_MAIN =
  process.env.EXPO_PUBLIC_ADAPTY_PLACEMENT_MAIN ?? 'main';
export const ADAPTY_PLACEMENT_ONBOARDING =
  process.env.EXPO_PUBLIC_ADAPTY_PLACEMENT_ONBOARDING ?? 'onboarding';

function sdkKey(): string {
  const ios = process.env.EXPO_PUBLIC_ADAPTY_IOS_SDK_KEY ?? '';
  const android = process.env.EXPO_PUBLIC_ADAPTY_ANDROID_SDK_KEY ?? '';
  return Platform.OS === 'android' ? android || ios : ios;
}

/** True when a public SDK key is present (i.e. Adapty is wired for this build). */
export function isAdaptyConfigured(): boolean {
  return sdkKey().length > 0;
}

let activationPromise: Promise<boolean> | null = null;

/**
 * Activate the SDK exactly once. Returns whether Adapty is usable. Safe to call
 * from multiple places — the first call wins and the rest await the same result.
 */
export function activateAdapty(): Promise<boolean> {
  if (activationPromise) return activationPromise;
  activationPromise = (async () => {
    const key = sdkKey();
    if (!key) return false;
    try {
      if (__DEV__) {
        await adapty.setLogLevel(LogLevel.VERBOSE);
      }
      await adapty.activate(key, {
        // React Native fast-refresh re-runs activation; ignore the extra calls.
        __ignoreActivationOnFastRefresh: __DEV__,
        // customerUserId is set after login via identifyAdapty().
      });
      return true;
    } catch {
      activationPromise = null; // allow a later retry
      return false;
    }
  })();
  return activationPromise;
}

/** Tie the current Adapty profile to our account id (idempotent). */
export async function identifyAdapty(accountId: number | string): Promise<void> {
  if (!(await activateAdapty())) return;
  try {
    await adapty.identify(String(accountId));
  } catch {
    // non-fatal: purchases still work anonymously and can be linked later
  }
}

/** Detach on sign-out; Adapty creates a fresh anonymous profile. */
export async function logoutAdapty(): Promise<void> {
  if (!isAdaptyConfigured()) return;
  try {
    await adapty.logout();
  } catch {
    // ignore
  }
}

/** Whether the store-side profile currently has an active premium entitlement. */
export async function hasActivePremium(): Promise<boolean> {
  if (!(await activateAdapty())) return false;
  try {
    const profile = await adapty.getProfile();
    return Boolean(profile.accessLevels?.[PREMIUM_ACCESS_LEVEL]?.isActive);
  } catch {
    return false;
  }
}
