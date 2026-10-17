/**
 * Tolerant parsers for Adapty remote configs.
 *
 * The dashboard is edited by hand, so every value is checked against what the
 * app can render: an unknown variant, a typo or a wrong type falls back to the
 * default for that one key instead of breaking the screen or the whole config.
 */
import type { AdaptyFlow } from 'react-native-adapty';

import {
  DEFAULT_OFFER_ARM,
  DEFAULT_ONBOARDING_CONFIG,
  DEFAULT_ONBOARDING_CONTENT,
  DEFAULT_PAYWALL_ARM,
  OFFER_VARIANTS,
  PAYWALL_VARIANTS,
} from './defaults';
import type {
  BeforeAfter,
  ContentGoal,
  OnboardingConfig,
  OnboardingContent,
  PaywallArmConfig,
  Review,
} from './types';

type Json = Record<string, unknown>;

function isObject(v: unknown): v is Json {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function oneOf<T extends string>(v: unknown, allowed: readonly T[], fallback: T): T {
  return typeof v === 'string' && (allowed as readonly string[]).includes(v) ? (v as T) : fallback;
}

function bool(v: unknown, fallback: boolean): boolean {
  return typeof v === 'boolean' ? v : fallback;
}

function str(v: unknown): string | null {
  return typeof v === 'string' && v.trim() !== '' ? v : null;
}

function stringMap(v: unknown): Record<string, string> {
  if (!isObject(v)) return {};
  const out: Record<string, string> = {};
  for (const [k, val] of Object.entries(v)) {
    if (typeof val === 'string') out[k] = val;
  }
  return out;
}

/**
 * The remote config of a flow. A flow carries one per locale; we ship English
 * only, so take `en` when present and the first one otherwise.
 */
export function remoteConfigData(flow: AdaptyFlow | null | undefined): Json | undefined {
  const configs = flow?.remoteConfigs;
  if (!configs || configs.length === 0) return undefined;
  const en = configs.find((c) => c.lang?.toLowerCase().startsWith('en'));
  const data = (en ?? configs[0])?.data;
  return isObject(data) ? data : undefined;
}

export function parseOnboardingConfig(data: Json | undefined): OnboardingConfig {
  const d = DEFAULT_ONBOARDING_CONFIG;
  if (!data) return d;
  const welcome = isObject(data.welcome) ? data.welcome : {};
  const social = isObject(data.social_proof) ? data.social_proof : {};
  return {
    onboarding: oneOf(data.onboarding, ['v3', 'v1'] as const, d.onboarding),
    welcome: {
      render: oneOf(welcome.render, ['native', 'flow'] as const, d.welcome.render),
      variant: oneOf(welcome.variant, ['A', 'B', 'C', 'D'] as const, d.welcome.variant),
      headline: str(welcome.headline),
      subline: str(welcome.subline),
    },
    // `try_it` (test O2) is backlog: no V3 screen for it, so it shows the screen.
    features: oneOf(data.features, ['screen', 'off'] as const, d.features),
    social_proof: {
      render: oneOf(social.render, ['native', 'flow'] as const, d.social_proof.render),
      show: bool(social.show, d.social_proof.show),
      hero: oneOf(social.hero, ['before_after', 'text'] as const, d.social_proof.hero),
    },
    loader_review: bool(data.loader_review, d.loader_review),
    plan: oneOf(data.plan, ['chart', 'ahead'] as const, d.plan),
    att: oneOf(data.att, ['loader', 'welcome'] as const, d.att),
    preview_mode: bool(data.preview_mode, d.preview_mode),
    free_first_log: bool(data.free_first_log, d.free_first_log),
    after_cancel_offer: bool(data.after_cancel_offer, d.after_cancel_offer),
    tutorial: bool(data.tutorial, d.tutorial),
    ai_consent: oneOf(data.ai_consent, ['save_plan', 'sheet'] as const, d.ai_consent),
  };
}

const CONTENT_GOALS: readonly ContentGoal[] = ['lose', 'gain', 'maintain', 'track'];

function parseReview(v: unknown): Review | null {
  if (!isObject(v)) return null;
  const text = str(v.text);
  const name = str(v.name);
  if (!text || !name) return null;
  return { text, name, city: str(v.city) ?? undefined };
}

function isHttpsUrl(v: unknown): v is string {
  return typeof v === 'string' && /^https:\/\/\S+$/.test(v);
}

function parseBeforeAfter(v: unknown): BeforeAfter | null {
  if (!isObject(v)) return null;
  const caption = str(v.caption);
  if (!isHttpsUrl(v.before_url) || !isHttpsUrl(v.after_url) || !caption) return null;
  return { before_url: v.before_url, after_url: v.after_url, caption, quote: str(v.quote) ?? undefined };
}

export function parseOnboardingContent(data: Json | undefined): OnboardingContent {
  const d = DEFAULT_ONBOARDING_CONTENT;
  if (!data) return d;
  const reviews: OnboardingContent['reviews'] = {};
  const beforeAfter: OnboardingContent['before_after'] = {};
  const loaderReview: OnboardingContent['loader_review'] = {};
  const rawReviews = isObject(data.reviews) ? data.reviews : {};
  const rawBa = isObject(data.before_after) ? data.before_after : {};
  const rawLoader = isObject(data.loader_review) ? data.loader_review : {};
  for (const goal of CONTENT_GOALS) {
    const list = Array.isArray(rawReviews[goal])
      ? (rawReviews[goal] as unknown[]).map(parseReview).filter((r): r is Review => r !== null)
      : [];
    if (list.length > 0) reviews[goal] = list;
    const ba = parseBeforeAfter(rawBa[goal]);
    if (ba) beforeAfter[goal] = ba;
    const lr = parseReview(rawLoader[goal]);
    if (lr) loaderReview[goal] = lr;
  }
  return {
    rating: str(data.rating) ?? d.rating,
    users: str(data.users) ?? d.users,
    reviews,
    before_after: beforeAfter,
    loader_review: loaderReview,
    texts: stringMap(data.texts),
  };
}

/**
 * One paywall-side arm. Which renderer, in order:
 *   1. an explicit `render` key (V3 configs always carry one);
 *   2. `use_native: true` without `render` → our code screen. Every arm keeps
 *      `use_native` so builds ≤1.0.10 stay on their legacy paywall;
 *   3. a flow with a builder view → that flow (e.g. a Flow Builder test arm);
 *   4. otherwise our code screen.
 */
export function parsePaywallArm(
  flow: AdaptyFlow | null,
  kind: 'paywall' | 'offer',
): PaywallArmConfig {
  const d = kind === 'offer' ? DEFAULT_OFFER_ARM : DEFAULT_PAYWALL_ARM;
  if (!flow) return d;
  const data = remoteConfigData(flow) ?? {};
  let render: PaywallArmConfig['render'];
  if (data.render === 'native' || data.render === 'flow' || data.render === 'legacy') {
    render = data.render;
  } else if (data.use_native === true) {
    render = 'native';
  } else if (flow.hasViewConfiguration) {
    render = 'flow';
  } else {
    render = 'native';
  }
  // A flow arm without a builder view cannot render: use our screen instead.
  if (render === 'flow' && !flow.hasViewConfiguration) render = 'native';
  const variants: readonly string[] = kind === 'offer' ? OFFER_VARIANTS : PAYWALL_VARIANTS;
  return {
    render,
    variant: oneOf(data.variant, variants, d.variant),
    copy: stringMap(data.copy),
    price_emphasis: oneOf(data.price_emphasis, ['design', 'billed', 'weekly'] as const, d.price_emphasis),
    show_rating: bool(data.show_rating, d.show_rating),
  };
}
