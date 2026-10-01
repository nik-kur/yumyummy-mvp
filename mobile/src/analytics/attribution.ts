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

import AsyncStorage from '@react-native-async-storage/async-storage';

import { register, setPersonProperties, setPersonPropertiesOnce, track } from '@/analytics/posthog';
import {
  setAdaptyCustomAttributes,
  setAdaptyIntegrationIdentifier,
  updateAdaptyAttribution,
} from '@/billing/adapty';

// AppsFlyer credentials. dev key comes from the AppsFlyer dashboard; appId is
// the numeric Apple App Store id (iOS only). Both injected at build time.
const AF_DEV_KEY = process.env.EXPO_PUBLIC_APPSFLYER_DEV_KEY ?? '';
const AF_APP_ID = process.env.EXPO_PUBLIC_APPSFLYER_APP_ID ?? '';

let started = false;

/**
 * Where the ATT prompt is shown.
 *
 * `false` (current): the prompt is raised from the onboarding — the flow's
 * welcome step, or the native welcome screen's "Get Started" — once the user
 * has seen what the app is. A prompt over the splash screen is the lowest-
 * consent placement there is, and consent is the only thing that gives us
 * user-level Meta attribution on iOS. AppsFlyer holds the install postback for
 * `ATT_WAIT_SECONDS` so a consent given on the welcome step still ships the
 * IDFA with it. Flip to `true` to restore the launch-time prompt.
 */
export const ATT_PROMPT_AT_LAUNCH = false;
const ATT_WAIT_SECONDS = 60;

/** AsyncStorage key for the last deep-link signal (deferred or direct). */
const AD_SIGNAL_KEY = '@yy_ad_signal';

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

  // 1b) The same campaign / ad set / ad as plain custom attributes. Adapty's
  //     own attribution parser decides what it keeps from the AppsFlyer
  //     payload; these are the fields we target audiences on (a flow per ad
  //     angle), so they go on the profile verbatim. Meta reports the ad name
  //     under `adgroup`, hence the fallbacks.
  if (isNonOrganic) {
    void setAdaptyCustomAttributes({
      af_media_source: mediaSource,
      af_campaign: str('campaign'),
      af_adset: str('af_adset') || str('adset'),
      af_ad: str('af_ad') || str('ad_name') || str('adgroup'),
    });
  }

  // 2) PostHog: super properties on every event from this device + person
  //    properties. `acquisition_source` is set-once so the Apple Ads value
  //    (written by the Adapty path) is never clobbered by "Organic".
  //    Meta names the ad `adgroup` in conversion data (not `af_ad`), and the ad
  //    name is where we encode the custom product page, so read it too.
  const afProps: Record<string, unknown> = {
    af_status: afStatus || undefined,
    af_media_source: mediaSource || undefined,
    af_campaign: str('campaign') || undefined,
    af_adset: str('af_adset') || str('adset') || undefined,
    af_ad: str('af_ad') || str('ad_name') || str('adgroup') || undefined,
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

/** Shape of AppsFlyer's Unified Deep Linking callback payload. */
interface UnifiedDeepLinkEvent {
  status?: string;
  deepLinkStatus?: 'FOUND' | 'NOT_FOUND' | 'ERROR';
  isDeferred?: boolean;
  data?: Record<string, unknown>;
}

/** What a tracking link told us about this install. */
export interface AdSignal {
  deep_link_value: string;
  deep_link_sub1?: string;
  deferred: boolean;
  received_at: string;
}

/**
 * Deferred deep link → the one user-level "which ad" signal that survives an
 * ATT denial. A OneLink click before install resolves here on first launch
 * with whatever `deep_link_value` the link carried (an angle, a campaign
 * code). It is stored for the onboarding, pushed to the Adapty profile so a
 * placement audience can key on it, and registered on every PostHog event.
 */
async function handleDeepLink(event: UnifiedDeepLinkEvent): Promise<void> {
  if (event?.deepLinkStatus !== 'FOUND' || !event.data) return;
  const str = (key: string): string => {
    const v = event.data?.[key];
    return typeof v === 'string' ? v : v == null ? '' : String(v);
  };
  const value = str('deep_link_value');
  if (!value) return;
  const signal: AdSignal = {
    deep_link_value: value,
    deep_link_sub1: str('deep_link_sub1') || undefined,
    deferred: Boolean(event.isDeferred),
    received_at: new Date().toISOString(),
  };
  try {
    await AsyncStorage.setItem(AD_SIGNAL_KEY, JSON.stringify(signal));
  } catch {
    // storage is a convenience; the profile attribute below is the record
  }
  const props = {
    deep_link_value: signal.deep_link_value,
    deep_link_sub1: signal.deep_link_sub1,
    deep_link_deferred: signal.deferred,
  };
  register(props);
  setPersonProperties(props);
  track('deep_link_received', props);
  void setAdaptyCustomAttributes({
    dl_value: signal.deep_link_value,
    dl_sub1: signal.deep_link_sub1,
  });
}

/** The stored deep-link signal, if a tracking link ever reached this install. */
export async function loadAdSignal(): Promise<AdSignal | null> {
  try {
    const raw = await AsyncStorage.getItem(AD_SIGNAL_KEY);
    return raw ? (JSON.parse(raw) as AdSignal) : null;
  } catch {
    return null;
  }
}

/**
 * Start AppsFlyer (and, when `ATT_PROMPT_AT_LAUNCH`, ask for ATT first).
 * Idempotent — the first call wins. Called once at launch from the root layout.
 */
export async function initAttribution(): Promise<void> {
  if (started) return;
  started = true;

  if (ATT_PROMPT_AT_LAUNCH) {
    // Prompt for ATT first so the IDFA (if granted) is available to AppsFlyer
    // and SKAdNetwork when the SDK starts.
    await requestTrackingConsent();
  }

  if (!isAppsFlyerConfigured()) return;
  const appsFlyer = loadAppsFlyer();
  if (!appsFlyer) return;

  try {
    // Both listeners must be registered BEFORE initSdk, or the first (and
    // only uncached) delivery of conversion data / the deferred link is lost.
    appsFlyer.onInstallConversionData((event: ConversionDataEvent) => {
      void handleConversionData(event);
    });
    appsFlyer.onDeepLink((event: UnifiedDeepLinkEvent) => {
      void handleDeepLink(event);
    });
    appsFlyer.initSdk(
      {
        devKey: AF_DEV_KEY,
        appId: AF_APP_ID,
        isDebug: __DEV__,
        onInstallConversionDataListener: true,
        onDeepLinkListener: true,
        // Hold the install postback until ATT is answered (or this many
        // seconds pass) so the IDFA is included when granted. The prompt is
        // raised on the welcome step, seconds after launch.
        timeToWaitForATTUserAuthorization: ATT_WAIT_SECONDS,
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
