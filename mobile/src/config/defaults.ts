/**
 * Review-safe defaults: what the app shows when Adapty has nothing to say, and
 * what App Review sees unless the dashboard says otherwise.
 *
 *   - Welcome A (photo + badge), design headline;
 *   - screen 16 and the loader review card hidden — the reviews we have are
 *     demo copy, and UK law bans showing invented reviews to consumers;
 *   - the after-cancel offer as "Try it FREE" (the "50% OFF" copy is a remote
 *     override, switched on only after release);
 *   - paywall and offer with the billed amount as the big price and the trial
 *     terms spelled out (`price_emphasis: "billed"`, App Review 3.1.2(c)). The
 *     layout as drawn — per-month figure first, no terms line — is
 *     `price_emphasis: "design"`, for A/B arms after review (decided 17 Oct).
 *
 * Copy for every screen lives with the screen; `onb_content.texts` overrides it
 * by key.
 */
import type { OnboardingConfig, OnboardingContent, PaywallArmConfig } from './types';

export const DEFAULT_ONBOARDING_CONFIG: OnboardingConfig = {
  onboarding: 'v3',
  welcome: { render: 'native', variant: 'A', headline: null, subline: null },
  features: 'screen',
  social_proof: { render: 'native', show: false, hero: 'before_after' },
  loader_review: false,
  plan: 'chart',
  att: 'loader',
  free_first_log: true,
  after_cancel_offer: true,
  tutorial: true,
};

export const DEFAULT_ONBOARDING_CONTENT: OnboardingContent = {
  rating: '5.0',
  users: '12,000+',
  reviews: {},
  before_after: {},
  loader_review: {},
  texts: {},
};

export const DEFAULT_PAYWALL_ARM: PaywallArmConfig = {
  render: 'native',
  variant: 'b3_joe',
  copy: {},
  price_emphasis: 'billed',
  show_rating: true,
};

export const DEFAULT_OFFER_ARM: PaywallArmConfig = {
  render: 'native',
  variant: 'costa',
  copy: {},
  price_emphasis: 'billed',
  show_rating: true,
};

export const PAYWALL_VARIANTS = [
  'b3_joe',
  'b3_home',
  'b3_office',
  'b3_wide',
  'p1_photo',
  'p1_text',
  'p1_voice',
] as const;

export const OFFER_VARIANTS = ['costa', 'closeup'] as const;
