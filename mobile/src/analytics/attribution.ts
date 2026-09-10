/**
 * Mobile attribution: App Tracking Transparency (ATT) + AppsFlyer MMP.
 *
 * Why AppsFlyer: one SDK manages install attribution + SKAdNetwork conversion
 * values across Meta, TikTok and Google, which is what we need for day-one
 * paid campaigns.
 *
 * Event split (keep it this way or Meta/AppsFlyer double count):
 *   - Client (this file, via `logAttributionEvent`): af_complete_registration,
 *     af_start_trial, af_subscribe. These must come from the SDK because the
 *     SKAN conversion value is computed on-device from SDK events.
 *   - Server (Adapty → AppsFlyer S2S): trial_converted, renewals, refunds,
 *     expirations — things the app never observes. `trial_started` and the
 *     initial purchase stay OFF in that integration.
 *
 * Install conversion data (media source / campaign / ad) is fanned out from
 * `onInstallConversionData` to Adapty (`updateAttribution`) and PostHog, so all
 * three stores agree on where a user came from.
 *
 * Everything is gated on `EXPO_PUBLIC_APPSFLYER_DEV_KEY` and lazy-requires the
 * native module, so with no key (or in Expo Go where the native module is
 * absent) every function is an inert no-op — the app keeps working.
 */
import {
  getTrackingPermissionsAsync,
  requestTrackingPermissionsAsync,
} from 'expo-tracking-transparency';

import { register, setPersonProperties, setPersonPropertiesOnce } from '@/analytics/posthog';
import { setAdaptyIntegrationIdentifier, updateAdaptyAttribution } from '@/billing/adapty';

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

/** Shape of the `onInstallConversionData` payload (see react-native-appsflyer). */
interface ConversionDataEvent {
  status?: string;
  type?: string;
  data?: Record<string, unknown>;
}

/** Normalise AppsFlyer's media source into the `acquisition_source` vocabulary
 *  PostHog already uses (`apple_search_ads` is set by the Adapty path). */
function acquisitionSourceFrom(mediaSource: string): string {
  const ms = mediaSource.toLowerCase();
  if (ms.includes('facebook') || ms.includes('meta') || ms.includes('instagram')) return 'meta';
  if (ms.includes('apple') || ms.includes('search ads')) return 'apple_search_ads';
  if (ms.includes('tiktok') || ms.includes('bytedance')) return 'tiktok';
  if (ms.includes('google')) return 'google_ads';
  if (ms === 'restricted') return 'restricted';
  return mediaSource;
}

let conversionDataHandled = false;

/**
 * Fan install conversion data out to Adapty and PostHog.
 *
 * AppsFlyer delivers this on every launch (cached after the first), so guard
 * with a per-process flag rather than `is_first_launch`: if the first delivery
 * raced Adapty activation, the next launch gets another chance.
 */
async function handleConversionData(event: ConversionDataEvent): Promise<void> {
  if (conversionDataHandled) return;
  const data = event?.data;
  if (!data || typeof data !== 'object') return;
  conversionDataHandled = true;

  const str = (key: string): string => {
    const v = data[key];
    return typeof v === 'string' ? v : v == null ? '' : String(v);
  };
  const afStatus = str('af_status'); // "Organic" | "Non-organic"
  const mediaSource = str('media_source');
  const isNonOrganic = afStatus.toLowerCase() === 'non-organic';

  // 1) Adapty: attribution on the profile → Adapty Analytics can slice
  //    trials/renewals by media source and campaign.
  try {
    const uid = await getAppsFlyerId();
    if (uid) await setAdaptyIntegrationIdentifier('appsflyer_id', uid);
    await updateAdaptyAttribution(data, 'appsflyer');
  } catch {
    // stitching only — never block launch
  }

  // 2) PostHog: super properties on every event from this device + person
  //    properties. `acquisition_source` is set-once so the Apple Ads value
  //    (written by the Adapty path) is never clobbered by "Organic".
  const afProps: Record<string, unknown> = {
    af_status: afStatus || undefined,
    af_media_source: mediaSource || undefined,
    af_campaign: str('campaign') || undefined,
    af_adset: str('af_adset') || str('adset') || undefined,
    af_ad: str('af_ad') || str('ad_name') || undefined,
  };
  for (const k of Object.keys(afProps)) if (afProps[k] === undefined) delete afProps[k];

  if (Object.keys(afProps).length > 0) {
    register(afProps);
    setPersonProperties(afProps);
  }
  if (isNonOrganic && mediaSource) {
    const source = acquisitionSourceFrom(mediaSource);
    register({ acquisition_source: source });
    setPersonPropertiesOnce({ acquisition_source: source });
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
    // Must be registered BEFORE initSdk, or the first (and only uncached)
    // delivery of conversion data is lost.
    appsFlyer.onInstallConversionData((event: ConversionDataEvent) => {
      void handleConversionData(event);
    });
    appsFlyer.initSdk(
      {
        devKey: AF_DEV_KEY,
        appId: AF_APP_ID,
        isDebug: __DEV__,
        onInstallConversionDataListener: true,
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

/**
 * AppsFlyer's device id, once the SDK has one. Adapty needs it to stitch the
 * install to its profile; resolves to null when AppsFlyer isn't configured or
 * doesn't answer within `timeoutMs`, so callers are never blocked.
 */
export function getAppsFlyerId(timeoutMs = 3000): Promise<string | null> {
  if (!isAppsFlyerConfigured()) return Promise.resolve(null);
  const appsFlyer = loadAppsFlyer();
  if (!appsFlyer) return Promise.resolve(null);

  return new Promise((resolve) => {
    let settled = false;
    const finish = (value: string | null) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(value);
    };
    const timer = setTimeout(() => finish(null), timeoutMs);
    try {
      appsFlyer.getAppsFlyerUID((error: unknown, uid: string) => {
        finish(error || !uid ? null : uid);
      });
    } catch {
      finish(null);
    }
  });
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
