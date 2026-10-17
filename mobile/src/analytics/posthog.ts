/**
 * PostHog RN SDK wrapper — single init, anonymous-first, identify after auth.
 *
 * Usage:
 *   import { track, identify, reset } from '@/analytics/posthog';
 *   track('paywall_shown', { variant: 'A_clean_v3' });
 */
import PostHog from 'posthog-react-native';

import { IS_QA_BUILD } from '@/config/buildFlags';

const API_KEY = process.env.EXPO_PUBLIC_POSTHOG_API_KEY ?? '';
const HOST = process.env.EXPO_PUBLIC_POSTHOG_HOST ?? 'https://eu.i.posthog.com';

let client: PostHog | null = null;

export function initPostHog(): void {
  if (client || !API_KEY) return;
  client = new PostHog(API_KEY, { host: HOST });
  // Local test builds share the production project: tag every event so
  // funnels can drop them (`qa_build != true`). Registered either way, so a
  // store install over a QA build on the same phone clears the persisted tag.
  void client.register({ qa_build: IS_QA_BUILD });
}

export function track(event: string, properties?: Record<string, unknown>): void {
  client?.capture(event, properties as Record<string, string | number | boolean | null>);
}

export function identify(distinctId: string, properties?: Record<string, unknown>): void {
  client?.identify(distinctId, properties as Record<string, string | number | boolean | null>);
}

/**
 * Super properties that describe the device, not the person: the QA flag and
 * the A/B arms (onboarding, paywall). `reset()` on sign-out would wipe them,
 * so they are kept here and registered again afterwards.
 */
const deviceProps: Record<string, unknown> = {};

export function registerDevice(properties: Record<string, unknown>): void {
  Object.assign(deviceProps, properties);
  register(properties);
}

export function reset(): void {
  client?.reset();
  register({ qa_build: IS_QA_BUILD, ...deviceProps });
}

export function getAnonymousId(): string | undefined {
  return client?.getAnonymousId();
}

/** Current distinct id (anonymous before login). Sent to Adapty so its
 *  server-side events land on this same person instead of a second one. */
export function getDistinctId(): string | undefined {
  return client?.getDistinctId();
}

/** Attach a property to every future event on this device. */
export function register(properties: Record<string, unknown>): void {
  void client?.register(properties as Record<string, string | number | boolean | null>);
}

type Scalars = Record<string, string | number | boolean | null>;

/** Set person properties on the current distinct id (overwrites). */
export function setPersonProperties(properties: Record<string, unknown>): void {
  client?.capture('$set', { $set: properties as Scalars });
}

/** Set person properties only if they are not already set on the person. */
export function setPersonPropertiesOnce(properties: Record<string, unknown>): void {
  client?.capture('$set', { $set_once: properties as Scalars });
}
