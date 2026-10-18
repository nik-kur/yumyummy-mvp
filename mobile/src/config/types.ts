/**
 * Shapes of the remote configs the app reads from Adapty placements.
 *
 * Adapty is the switchboard: each A/B arm is a flow whose remote config picks
 * screen variants, hides or shows screens and overrides copy. Every key is
 * optional on the wire — anything missing or malformed falls back to the
 * review-safe default in `defaults.ts`. Keys are only ever added, never renamed:
 * builds ≤1.0.10 read nothing but `use_native` and ignore the rest.
 */

/** Where a slot's screen comes from: our code, or an Adapty flow for that slot. */
export type SlotRender = 'native' | 'flow';

/** `onb_main`: the onboarding test switches (one flow per arm). */
export interface OnboardingConfig {
  /** T0: the V3 onboarding, or the pre-V3 one as the control. */
  onboarding: 'v3' | 'v1';
  welcome: {
    render: SlotRender;
    /** O3: A photo + badge (default), B + laurel, C mascot + laurels, D demo video. */
    variant: 'A' | 'B' | 'C' | 'D';
    /** Copy override; `null` keeps the design's text. */
    headline: string | null;
    subline: string | null;
  };
  /** O1: show the Features screen (12) or skip it. */
  features: 'screen' | 'off';
  social_proof: {
    render: SlotRender;
    /** Screen 16. Off in code; on in Adapty for everyone since 18 Oct (real reviews from `onb_content`). */
    show: boolean;
    /** O4: before/after photos or a text-only hero. */
    hero: 'before_after' | 'text';
  };
  /** Review card inside the loader (14). Off by default. */
  loader_review: boolean;
  /** O7: dated weight chart (control) or the "See what's ahead" milestones. */
  plan: 'chart' | 'ahead';
  /** O6: ATT prompt over the loader (default) or on the welcome screen. */
  att: 'loader' | 'welcome';
  /**
   * PM: closing the after-cancel offer opens preview mode (the real Today on
   * an anonymous account). Off = the paywall stays hard, as before V3.
   */
  preview_mode: boolean;
  /** PM2: preview mode lets the first AI log through for free. */
  free_first_log: boolean;
  /** C5: offer after the customer cancels the App Store sheet. */
  after_cancel_offer: boolean;
  /** Post-purchase 6-step tour over Today (24). */
  tutorial: boolean;
  /**
   * Where a buyer agrees to AI processing (App Review 5.1.2(i)): `save_plan`
   * = a disclosure line on Save plan, agreed with Sign in with Apple (the tour
   * then runs without the consent sheet); `sheet` = the sheet before the
   * first AI log. Anyone who never saw the line still gets the sheet.
   */
  ai_consent: 'save_plan' | 'sheet';
  /**
   * The onboarding's App Store rating prompt: `auto` = over screen 16 when it
   * shows, else over the plan reveal (15); `plan` = always over the plan
   * reveal; `off` = none in the onboarding. The in-app moments (a full day
   * logged, the Week 1 report) ask either way, within their own caps.
   */
  rating_prompt: 'auto' | 'plan' | 'off';
}

/** One review on the carousel (16) or in the loader card (14). */
export interface Review {
  text: string;
  name: string;
  city?: string;
}

/** Before/after hero on screen 16 (lose and gain only). */
export interface BeforeAfter {
  before_url: string;
  after_url: string;
  /** Bundled photos — QA demo content only (`demoContent.ts`). */
  before_local?: number;
  after_local?: number;
  /** e.g. "Emma, −7 kg in 4 months" */
  caption: string;
  quote?: string;
}

export type ContentGoal = 'lose' | 'gain' | 'maintain' | 'track';

/** `onb_content`: copy, numbers and reviews shared by every arm (no A/B). */
export interface OnboardingContent {
  /** App Store rating as shown, e.g. "5.0". */
  rating: string;
  /** e.g. "12,000+". */
  users: string;
  reviews: Partial<Record<ContentGoal, Review[]>>;
  before_after: Partial<Record<ContentGoal, BeforeAfter>>;
  loader_review: Partial<Record<ContentGoal, Review>>;
  /** Copy overrides by key, e.g. `reflect.gain.title`. Missing key = design copy. */
  texts: Record<string, string>;
}

/** Which renderer a paywall-side placement uses for this arm. */
export type PaywallRender = 'native' | 'flow' | 'legacy';

/** `pw_main` / `pw_after_cancel`: one arm's remote config. */
export interface PaywallArmConfig {
  render: PaywallRender;
  /**
   * `pw_main`: b3_joe (control) | b3_home | b3_office | b3_wide |
   * p1_photo | p1_text | p1_voice. `pw_after_cancel`: costa (control) | closeup.
   */
  variant: string;
  /** Copy overrides by key, e.g. `headline` on the offer ("Try it FREE" / "50% OFF"). */
  copy: Record<string, string>;
  /**
   * Which price is the big one on the plans screen and the offer. `billed`
   * (default) = the amount actually charged leads and the trial terms are
   * spelled out (App Review 3.1.2(c)); `design` = as drawn on the canvas
   * (per-month figure first); `weekly` = per-week figure first.
   */
  price_emphasis: 'design' | 'billed' | 'weekly';
  /** "5.0 ★ avg App Store rating" on B3 and the rating chip on P1 plans. */
  show_rating: boolean;
  /**
   * `pw_main` plans screen (19), apart from the first screen: `auto` follows
   * the variant (p1_* → light cards, b3_* → that photo); `light`, or a B3
   * photo (`b3_joe` …) to pair e.g. P1's video with the photo plans.
   */
  plans: 'auto' | 'light' | 'b3_joe' | 'b3_home' | 'b3_office' | 'b3_wide';
}

/** How a config reached the app — goes to PostHog as `config_source`. */
export type ConfigSource = 'adapty' | 'default' | 'qa';

/** The Adapty side of an assignment, for analytics. */
export interface AssignmentMeta {
  source: ConfigSource;
  placement: string;
  variation_id?: string;
  variation_name?: string;
  ab_test?: string;
  audience?: string;
  /** Why a default was used: timeout, error, adapty_unavailable. */
  default_reason?: string;
  fetch_ms?: number;
  assigned_at: string;
}
