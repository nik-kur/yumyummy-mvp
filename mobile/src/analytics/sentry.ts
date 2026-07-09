/**
 * Sentry RN init — crash reporting + JS error capture.
 * DSN comes from env; when absent (Expo Go / missing config), Sentry is a no-op.
 */
import * as Sentry from '@sentry/react-native';

const DSN = process.env.EXPO_PUBLIC_SENTRY_DSN ?? '';

export function initSentry(): void {
  if (!DSN) return;
  Sentry.init({
    dsn: DSN,
    tracesSampleRate: __DEV__ ? 1.0 : 0.2,
    enableNativeFramesTracking: !__DEV__,
    debug: __DEV__,
  });
}

export function setUser(id: string): void {
  Sentry.setUser({ id });
}

export function clearUser(): void {
  Sentry.setUser(null);
}

export function addBreadcrumb(
  category: string,
  message: string,
  data?: Record<string, unknown>,
): void {
  Sentry.addBreadcrumb({ category, message, data, level: 'info' });
}

export function captureException(error: unknown): void {
  Sentry.captureException(error);
}
