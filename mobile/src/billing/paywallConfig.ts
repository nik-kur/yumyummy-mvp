/**
 * Remote config contract for code-rendered paywalls.
 *
 * Each Adapty paywall entity carries a JSON remote config (§1.2 of
 * Adapty_Integration_Architecture.md). The renderer picks a layout by
 * `variant`; unknown variants fall back to the default A layout.
 *
 * IRON RULE: prices / intro-offer details in the UI come ONLY from
 * `paywall.products` (localised from the store), never from this config.
 */
import type { AdaptyPaywallProduct } from 'react-native-adapty';

// ---------------------------------------------------------------------------
// Remote config schema
// ---------------------------------------------------------------------------

export interface PaywallHero {
  label: string;
  goal_line: string;
  maintain_line: string;
}

export interface SocialProof {
  laurels: string[];
  quote: { text: string; author: string };
}

export interface TimelineStep {
  icon: string;
  t: string;
  d: string;
  done?: boolean;
}

export interface PlanConfig {
  product: string;
  badge?: string;
  rec_tag_by_goal?: Record<string, string>;
  price_style?: string;
  sub?: string;
}

export interface PaywallRemoteConfig {
  variant: string;
  headline: string;
  hero: PaywallHero;
  social: SocialProof;
  timeline?: { enabled_for: string; steps: TimelineStep[] };
  plans: PlanConfig[];
  cta: Record<string, string>;
  above_cta: string;
  hard_paywall: boolean;
}

// ---------------------------------------------------------------------------
// Fallback config (variant A) — bundled for offline / first launch
// ---------------------------------------------------------------------------

export const FALLBACK_CONFIG: PaywallRemoteConfig = {
  variant: 'A_clean_v3',
  headline: 'Nutrition tracking that finally works',
  hero: {
    label: 'YOUR PLAN — LOCKED IN',
    goal_line: '{TARGET_WEIGHT} by {TARGET_DATE}',
    maintain_line: 'Your zone: {DAILY_KCAL} kcal',
  },
  social: {
    laurels: ['★ {RATING} App Store', '{USERS}+ trackers', '✓ Verified data'],
    quote: {
      text: 'Finally started losing — the numbers were just right.',
      author: 'Maria · −4 kg in 6 weeks',
    },
  },
  timeline: {
    enabled_for: 'yearly',
    steps: [
      { icon: '✓', t: 'Done', d: 'Your personal plan — built', done: true },
      { icon: '🔓', t: 'Today', d: 'Full access unlocked' },
      { icon: '🔔', t: 'Day 2', d: "We'll remind you 24h before any charge" },
      { icon: '★', t: 'Day 3', d: 'Trial ends — cancel anytime before' },
    ],
  },
  plans: [
    {
      product: 'ai.yumyummy.app.yearly',
      badge: 'BEST VALUE · 3 DAYS FREE',
      rec_tag_by_goal: {
        lose: '✦ Recommended for steady weight loss',
        default: '✦ Recommended for building the habit',
      },
      price_style: 'per_month_big',
    },
    { product: 'ai.yumyummy.app.monthly', sub: 'billed monthly · no trial' },
    { product: 'ai.yumyummy.app.weekly_upd', sub: 'start today · no commitment' },
  ],
  cta: {
    yearly: 'Try Free for 3 Days',
    monthly: 'Continue — {PRICE_M}/mo',
    weekly: 'Start now — {PRICE_W}/week',
  },
  above_cta: '✓ No payment due now · Cancel anytime in 2 taps',
  hard_paywall: true,
};

// ---------------------------------------------------------------------------
// Placeholder substitution
// ---------------------------------------------------------------------------

export interface PlaceholderValues {
  TARGET_WEIGHT?: string;
  TARGET_DATE?: string;
  DAILY_KCAL?: string;
  RATING?: string;
  USERS?: string;
  PRICE_M?: string;
  PRICE_W?: string;
}

const PLACEHOLDER_DEFAULTS: PlaceholderValues = {
  RATING: '4.8',
  USERS: '12,000',
};

export function fillPlaceholders(
  template: string,
  values: PlaceholderValues,
): string {
  const merged = { ...PLACEHOLDER_DEFAULTS, ...values };
  return template.replace(/\{(\w+)\}/g, (match, key: string) => {
    const val = merged[key as keyof PlaceholderValues];
    return val ?? match;
  });
}

// ---------------------------------------------------------------------------
// Config parser
// ---------------------------------------------------------------------------

export function parseRemoteConfig(raw: string | null | undefined): PaywallRemoteConfig {
  if (!raw) return FALLBACK_CONFIG;
  try {
    const parsed = JSON.parse(raw) as Partial<PaywallRemoteConfig>;
    if (!parsed.variant || !parsed.plans?.length) return FALLBACK_CONFIG;
    return parsed as PaywallRemoteConfig;
  } catch {
    return FALLBACK_CONFIG;
  }
}

/**
 * Resolve the variant key to a known renderer layout.
 * Unknown variants degrade to 'A' (forward-compatible).
 */
export type RendererVariant = 'A' | 'B' | 'B2' | 'C';

const VARIANT_MAP: Record<string, RendererVariant> = {
  A_clean_v3: 'A',
  B_trial_designer: 'B',
  B2_coffee_compare: 'B2',
  C_result_hook: 'C',
};

export function resolveVariant(variant: string): RendererVariant {
  return VARIANT_MAP[variant] ?? 'A';
}

// ---------------------------------------------------------------------------
// Product helpers
// ---------------------------------------------------------------------------

export function findProduct(
  products: AdaptyPaywallProduct[],
  vendorId: string,
): AdaptyPaywallProduct | undefined {
  return products.find((p) => p.vendorProductId === vendorId);
}

/**
 * Per-month price for yearly products — formatted for display.
 * Returns undefined if the product has no price info.
 */
export function perMonthPrice(product: AdaptyPaywallProduct): string | undefined {
  const price = product.price;
  if (!price?.amount) return undefined;
  const monthly = price.amount / 12;
  const symbol = price.currencySymbol ?? price.currencyCode ?? '$';
  return `${symbol}${monthly.toFixed(2)}`;
}
