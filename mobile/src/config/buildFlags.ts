/**
 * What kind of binary this is.
 *
 * A QA build is any local build used to exercise the app: a Debug build
 * (`__DEV__`) or a Release build bundled with `EXPO_PUBLIC_QA_BUILD=1`. EAS
 * production builds set neither, so everything gated on this is dead code in
 * the App Store binary — Metro folds the constant and drops the branch.
 *
 * In a QA build:
 *   - AppsFlyer stays off, so test installs and sandbox purchases never reach
 *     Meta (in-app events cannot be deleted there once received);
 *   - every PostHog event carries `qa_build: true` and Sentry reports under the
 *     `qa` environment, so funnels can drop them;
 *   - the QA menu (`app/qa.tsx`) can override any remote-config key.
 */
export const IS_QA_BUILD: boolean = __DEV__ || process.env.EXPO_PUBLIC_QA_BUILD === '1';
