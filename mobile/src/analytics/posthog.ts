/**
 * PostHog RN SDK wrapper — single init, anonymous-first, identify after auth.
 *
 * Usage:
 *   import { track, identify, reset } from '@/analytics/posthog';
 *   track('paywall_shown', { variant: 'A_clean_v3' });
 */
import PostHog from 'posthog-react-native';

const API_KEY = process.env.EXPO_PUBLIC_POSTHOG_API_KEY ?? '';
const HOST = process.env.EXPO_PUBLIC_POSTHOG_HOST ?? 'https://eu.i.posthog.com';

let client: PostHog | null = null;

export function initPostHog(): void {
  if (client || !API_KEY) return;
  client = new PostHog(API_KEY, { host: HOST });
}

export function track(event: string, properties?: Record<string, unknown>): void {
  client?.capture(event, properties as Record<string, string | number | boolean | null>);
}

export function identify(distinctId: string, properties?: Record<string, unknown>): void {
  client?.identify(distinctId, properties as Record<string, string | number | boolean | null>);
}

export function reset(): void {
  client?.reset();
}

export function getAnonymousId(): string | undefined {
  return client?.getAnonymousId();
}
