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
import { initPostHog, getDistinctId, registerDevice } from '@/analytics/posthog';
import { initAttribution, getAppsFlyerId, syncTrackingStatusToAdapty } from '@/analytics/attribution';
import { activateAdapty, setAdaptyCustomAttributes, setAdaptyIntegrationIdentifier } from '@/billing/adapty';
import { IS_QA_BUILD } from '@/config/buildFlags';
import { loadQaOverrides } from '@/config/qa';
import { isTesterDevice } from '@/config/testerDevice';

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
  // The tester phone stays out of the funnels after every sign-out (reset), not only until the first one.
  void isTesterDevice().then((tester) => {
    if (tester) registerDevice({ qa_tester: true });
  });
  void loadQaOverrides();

  await withTimeout(initAttribution(), PRE_ACTIVATION_TIMEOUT_MS, undefined);
  const appsFlyerId = await getAppsFlyerId(PRE_ACTIVATION_TIMEOUT_MS);

  if (!(await activateAdapty())) return;

  await Promise.all([
    appsFlyerId
      ? setAdaptyIntegrationIdentifier('appsflyer_id', appsFlyerId)
      : Promise.resolve(),
    setAdaptyIntegrationIdentifier('posthog_distinct_user_id', getDistinctId() ?? ''),
    // The ATT answer can also change in Settings between launches.
    syncTrackingStatusToAdapty(),
    // Lets an Adapty segment keep local test installs out of real audiences.
    // Written either way so a store build over a QA build resets it.
    setAdaptyCustomAttributes({ qa_build: IS_QA_BUILD ? 'true' : 'false' }),
  ]);

  // `acquisition_source` is set only from AppsFlyer conversion data (see
  // attribution.ts). The old Adapty-based check tagged *every* user as
  // apple_search_ads: Adapty lists the source whenever the AdServices token
  // was processed, not only when the install was actually attributed.
}
