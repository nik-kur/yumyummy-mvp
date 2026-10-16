/**
 * DEMO content for QA builds only — invented people ("SYNTHETIC — INTERNAL
 * DESIGN TEST ONLY"). Never imported by a production bundle: the only require
 * sits behind a build-time constant in `onboardingConfig.ts`. Real, consented
 * reviews reach production through the `onb_content` remote config.
 *
 * Filled from the V3 canvas in stage 2.
 */
import type { OnboardingContent } from './types';

export const DEMO_CONTENT: OnboardingContent = {
  rating: '5.0',
  users: '12,000+',
  reviews: {},
  before_after: {},
  loader_review: {},
  // Marker the release-bundle check greps for: it must never appear there.
  texts: { __bundle_marker: 'yy-demo-content-qa-only' },
};
