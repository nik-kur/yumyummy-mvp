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
import { initPostHog, getDistinctId } from '@/analytics/posthog';
import { initAttribution, getAppsFlyerId } from '@/analytics/attribution';
import { activateAdapty, setAdaptyIntegrationIdentifier } from '@/billing/adapty';

/** How long we let ATT + AppsFlyer settle before activating Adapty anyway. */
const PRE_ACTIVATION_TIMEOUT_MS = 5000;

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

  // `acquisition_source` is set only from AppsFlyer conversion data (see
  // attribution.ts). The old Adapty-based check tagged *every* user as
  // apple_search_ads: Adapty lists the source whenever the AdServices token
  // was processed, not only when the install was actually attributed.
}
