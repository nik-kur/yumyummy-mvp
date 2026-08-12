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
import type { AdaptyProfile } from 'react-native-adapty';

import { captureException } from '@/analytics/sentry';

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

let identifyPromise: Promise<boolean> | null = null;

/**
 * Tie the current Adapty profile to our account id (idempotent).
 *
 * Callers must await this before any other Adapty call: racing `identify()`
 * either fails with #3006 profileWasChanged or lands the call on the anonymous
 * profile created at activation, which loses the purchase and its attribution.
 */
export async function identifyAdapty(accountId: number | string): Promise<boolean> {
  const run = (async () => {
    if (!(await activateAdapty())) return false;
    try {
      await adapty.identify(String(accountId));
      return true;
    } catch (e) {
      // Non-fatal: the purchase still exists on the anonymous profile, and
      // `/billing/sync` can find it by profile id. Report it so we notice if
      // this starts happening at scale.
      captureException(e);
      return false;
    }
  })();
  identifyPromise = run;
  return run;
}

/**
 * Wait for an in-flight `identifyAdapty` to settle.
 *
 * Sign-in runs identify() in the background so no screen blocks on the network.
 * Anything that must not touch the anonymous profile — a purchase above all,
 * whose receipt would otherwise arrive at our webhook with no account behind
 * it — awaits this first. Resolves at once when nothing is in flight, and gives
 * up after `timeoutMs` rather than trapping the buyer behind a slow network.
 */
export async function waitForAdaptyIdentify(timeoutMs = 4000): Promise<void> {
  const pending = identifyPromise;
  if (!pending) return;
  await Promise.race([
    pending.catch(() => undefined),
    new Promise((resolve) => setTimeout(resolve, timeoutMs)),
  ]);
}

/**
 * Id of the Adapty profile this device is currently using. Before sign-in this
 * is an anonymous profile — the one a purchase actually lands on — so we hand
 * it to the backend to reconcile entitlements that the webhook couldn't map.
 */
export async function getAdaptyProfileId(): Promise<string | null> {
  if (!(await activateAdapty())) return null;
  try {
    const profile = await adapty.getProfile();
    return profile.profileId ?? null;
  } catch {
    return null;
  }
}

/**
 * Attach the account's email to the Adapty profile.
 *
 * Adapty Mail can only address a profile that carries an `email` attribute, and
 * nothing sets one implicitly — not `identify()`, not the purchase. Must run
 * *after* `identifyAdapty`, or the address lands on the anonymous profile that
 * the campaign audience never looks at.
 */
export async function setAdaptyEmail(email: string | null | undefined): Promise<void> {
  if (!email) return;
  if (!(await activateAdapty())) return;
  try {
    await adapty.updateProfile({ email });
  } catch (e) {
    // Lifecycle email only — never block sign-in on it. The backend pushes the
    // same value from /billing/sync, so a failure here self-heals.
    captureException(e);
  }
}

/**
 * Link a third-party id to the Adapty profile (`posthog_distinct_user_id`,
 * `appsflyer_id`, …) so Adapty's server-side events land on the same person
 * instead of creating a second one keyed by its own profile id.
 */
export async function setAdaptyIntegrationIdentifier(
  key: string,
  value: string,
): Promise<void> {
  if (!value) return;
  if (!(await activateAdapty())) return;
  try {
    await adapty.setIntegrationIdentifier(key, value);
  } catch {
    // analytics stitching only — never block the app on it
  }
}

const APPLE_ADS_SOURCE = 'apple_search_ads';

function hasAppleAdsAttribution(profile: AdaptyProfile): boolean {
  return profile.appliedAttributionSources?.includes(APPLE_ADS_SOURCE) ?? false;
}

/**
 * Resolves once Apple Ads attribution has been applied to the profile, or
 * `false` if it hasn't within `timeoutMs`.
 *
 * Apple Ads attribution lands asynchronously after `activate()`, so the first
 * `getPaywall()` on a cold launch resolves against the default audience. Rather
 * than delay the paywall, callers show it immediately and use this to re-fetch
 * the Apple-Ads-targeted variant when attribution arrives. From the second
 * launch on the cached profile already carries it and this resolves at once.
 */
export async function waitForAppleAdsAttribution(timeoutMs: number): Promise<boolean> {
  if (!(await activateAdapty())) return false;

  try {
    const current = await adapty.getProfile();
    if (hasAppleAdsAttribution(current)) return true;
  } catch {
    // fall through to the listener
  }

  return new Promise((resolve) => {
    let settled = false;
    let subscription: { remove: () => void } | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const finish = (value: boolean) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      subscription?.remove();
      resolve(value);
    };

    subscription = adapty.addEventListener('onLatestProfileLoad', (profile) => {
      if (hasAppleAdsAttribution(profile)) finish(true);
    });
    timer = setTimeout(() => finish(false), timeoutMs);

    // A listener that fired during registration would have left the
    // subscription dangling — drop it now that we hold the handle.
    if (settled) subscription.remove();
  });
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
