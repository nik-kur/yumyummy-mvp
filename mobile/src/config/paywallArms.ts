/**
 * Paywall-side switchboard: `pw_main` (paywall 17–19) and `pw_after_cancel`
 * (offer 20 and Last offer 21). Each A/B arm is a flow; its remote config says
 * whether our code draws the screen (`render: "native"`, with a `variant`) or
 * the flow's own builder screens do (`render: "flow"`).
 *
 * Either way the arm's flow is kept: the code paywall buys the flow's products
 * (`getPaywallProducts(flow)`) and logs its show (`logShowFlow(flow)`), so
 * Adapty compares code and builder arms inside one A/B test.
 */
import { adapty } from 'react-native-adapty';
import type { AdaptyFlow } from 'react-native-adapty';

import { addBreadcrumb } from '@/analytics/sentry';
import { whenAdaptyActivated } from '@/billing/adapty';

import { DEFAULT_OFFER_ARM, DEFAULT_PAYWALL_ARM } from './defaults';
import { parsePaywallArm } from './parse';
import { loadQaOverrides } from './qa';
import type { ConfigSource, PaywallArmConfig } from './types';

const ACTIVATION_GRACE_MS = 1200;

export interface ResolvedArm {
  /** The arm's flow; `null` when Adapty did not answer (no products then). */
  flow: AdaptyFlow | null;
  config: PaywallArmConfig;
  source: ConfigSource;
}

export async function resolvePaywallArm(
  placement: string,
  kind: 'paywall' | 'offer',
  timeoutMs: number,
): Promise<ResolvedArm> {
  const qa = await loadQaOverrides();
  const override = kind === 'offer' ? qa.offer : qa.paywall;
  let flow: AdaptyFlow | null = null;
  if (!qa.simulate_timeout && (await whenAdaptyActivated(ACTIVATION_GRACE_MS))) {
    try {
      flow = await adapty.getFlow(placement, { loadTimeoutMs: timeoutMs });
    } catch (e) {
      addBreadcrumb('config', 'Paywall arm fetch failed', {
        placement,
        error: e instanceof Error ? e.message : String(e),
      });
    }
  }
  const parsed = flow
    ? parsePaywallArm(flow, kind)
    : kind === 'offer'
      ? DEFAULT_OFFER_ARM
      : DEFAULT_PAYWALL_ARM;
  if (override && Object.keys(override).length > 0) {
    const config = { ...parsed, ...override, copy: { ...parsed.copy, ...(override.copy ?? {}) } };
    // A forced builder render needs a flow with a view; otherwise stay on ours.
    if (config.render === 'flow' && !flow?.hasViewConfiguration) config.render = 'native';
    return { flow, config, source: 'qa' };
  }
  return { flow, config: parsed, source: flow ? 'adapty' : 'default' };
}
