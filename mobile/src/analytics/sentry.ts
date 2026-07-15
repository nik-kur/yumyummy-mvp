/**
 * Sentry RN init — crash reporting + JS error capture.
 * DSN comes from env; when absent (Expo Go / missing config), Sentry is a no-op.
 */
import * as Sentry from '@sentry/react-native';
import Constants from 'expo-constants';

const DSN = process.env.EXPO_PUBLIC_SENTRY_DSN ?? '';

// Human-readable release tag (e.g. "yumyummy@1.0.0"). Sourcemaps are matched by
// Debug ID (injected via metro.config.js), so this is only for grouping issues
// by app version in the Sentry UI. `dist` (the build number) is left to the SDK
// to auto-detect from the native bundle, which stays correct under EAS
// autoIncrement.
const appVersion = Constants.expoConfig?.version ?? undefined;
const RELEASE = appVersion ? `yumyummy@${appVersion}` : undefined;

export function initSentry(): void {
  if (!DSN) return;
  Sentry.init({
    dsn: DSN,
    release: RELEASE,
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
