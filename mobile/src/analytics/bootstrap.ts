/**
 * Launch-time SDK startup, in the order Adapty requires.
 *
 * Adapty's rule: bring up analytics/MMP SDKs first and wait for their device
 * ids, then `activate()`, then hand those ids over. Activating first means the
 * ids attach to a throwaway anonymous profile and don't reliably transfer to
 * the identified one — which shows up later as installs with no attribution and
 * Adapty events landing on a second PostHog person.
 *
 * The pre-activation wait is bounded: ATT is a user-facing prompt and AppsFlyer
 * can be slow, and nothing here is worth stalling the paywall for.
 */
import { initSentry } from '@/analytics/sentry';
import { initPostHog, getDistinctId, register } from '@/analytics/posthog';
import { initAttribution, getAppsFlyerId } from '@/analytics/attribution';
import {
  activateAdapty,
  setAdaptyIntegrationIdentifier,
  waitForAppleAdsAttribution,
} from '@/billing/adapty';

/** How long we let ATT + AppsFlyer settle before activating Adapty anyway. */
const PRE_ACTIVATION_TIMEOUT_MS = 5000;

/** How long to keep listening for Apple Ads attribution after launch. */
const APPLE_ADS_ATTRIBUTION_TIMEOUT_MS = 30000;

let started = false;

function withTimeout<T>(promise: Promise<T>, ms: number, fallback: T): Promise<T> {
  return Promise.race([
    promise,
    new Promise<T>((resolve) => setTimeout(() => resolve(fallback), ms)),
  ]);
}

/** Idempotent — the first call wins. */
export async function bootstrapSdks(): Promise<void> {
  if (started) return;
  started = true;

  initSentry();
  initPostHog();

  await withTimeout(initAttribution(), PRE_ACTIVATION_TIMEOUT_MS, undefined);
  const appsFlyerId = await getAppsFlyerId(PRE_ACTIVATION_TIMEOUT_MS);

  if (!(await activateAdapty())) return;

  await Promise.all([
    appsFlyerId
      ? setAdaptyIntegrationIdentifier('appsflyer_id', appsFlyerId)
      : Promise.resolve(),
    setAdaptyIntegrationIdentifier('posthog_distinct_user_id', getDistinctId() ?? ''),
  ]);

  // Tag every event from an Apple Ads install so campaign performance is
  // sliceable in PostHog without joining against Adapty.
  void waitForAppleAdsAttribution(APPLE_ADS_ATTRIBUTION_TIMEOUT_MS).then((applied) => {
    if (applied) register({ acquisition_source: 'apple_search_ads' });
  });
}
