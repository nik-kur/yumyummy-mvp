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
  /**
   * `trial_big` leads the card with the free-trial length and pushes the price
   * into the sub-line — the right shape for a single-plan paywall. Anything
   * else leads with the price, which is what makes several plans comparable at
   * a glance. Ignored when the plan carries no trial.
   */
  price_style?: string;
  sub?: string;
  /**
   * Display-only price strings shown when StoreKit products are unavailable
   * (e.g. subscriptions not yet approved). Purchases stay disabled — these
   * exist so the paywall never renders empty price slots.
   */
  display_price?: string;
  display_sub?: string;
}

export interface PaywallRemoteConfig {
  variant: string;
  headline: string;
  hero: PaywallHero;
  social: SocialProof;
  /**
   * Shown whenever the selected plan carries a trial. `enabled_for` is legacy
   * and ignored — which plan gets the trial is StoreKit's answer, not config's.
   */
  timeline?: { enabled_for?: string; steps: TimelineStep[] };
  plans: PlanConfig[];
  /**
   * Keyed by `trial` when the selected plan has one, else by billing period
   * (`yearly` / `monthly` / `weekly`). The period keys are the fallback for
   * customers who already used their one offer for this subscription group.
   */
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
    laurels: ['★ {RATING} rating', '{USERS}+ trackers', '✓ Verified data'],
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
      badge: 'BEST VALUE',
      rec_tag_by_goal: {
        lose: '✦ Recommended for a steady habit',
        default: '✦ Recommended for building the habit',
      },
      display_price: '$1.73/wk',
      display_sub: '3 days free, then billed annually at $89.99',
    },
    {
      product: 'ai.yumyummy.app.monthly',
      display_price: '$2.31/wk',
      display_sub: '3 days free, then billed monthly at $9.99',
    },
    {
      product: 'ai.yumyummy.app.weekly_upd',
      display_price: '$4.99/wk',
      display_sub: '3 days free, then billed weekly',
    },
  ],
  cta: {
    trial: 'Start my 3-day free trial',
    yearly: 'Start 3 days free now',
    monthly: 'Continue — {PRICE_M}/mo',
    weekly: 'Start now — {PRICE_W}/wk',
  },
  above_cta: '✓ No payment due now · Cancel anytime',
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
  RATING: '4.9',
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

/** True when a filled template still contains an unresolved {PLACEHOLDER}. */
export function hasUnresolvedPlaceholders(text: string): boolean {
  return /\{\w+\}/.test(text);
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

/** Weeks in one unit of each billing period — the divisor behind `perWeekPrice`. */
const WEEKS_PER_UNIT: Record<string, number> = {
  year: 52,
  month: 52 / 12,
  week: 1,
  day: 1 / 7,
};

/**
 * Price normalised to a weekly rate — formatted for display.
 *
 * Quoting every plan in the same unit is what makes them comparable: a year at
 * $89.99 and a week at $4.99 say nothing side by side until both read "/wk".
 * Returns undefined when the product carries no price or no recognised period.
 */
export function perWeekPrice(product: AdaptyPaywallProduct): string | undefined {
  const price = product.price;
  if (!price?.amount) return undefined;
  const period = product.subscription?.subscriptionPeriod;
  const weeks = (WEEKS_PER_UNIT[period?.unit ?? ''] ?? 0) * (period?.numberOfUnits || 1);
  if (!weeks) return undefined;
  const symbol = price.currencySymbol ?? price.currencyCode ?? '$';
  return `${symbol}${(price.amount / weeks).toFixed(2)}`;
}

type AdaptySubscription = NonNullable<AdaptyPaywallProduct['subscription']>;
type AdaptyOfferPhase = NonNullable<AdaptySubscription['offer']>['phases'][number];

/** The store's own formatting — correct for currencies that trail the symbol. */
export function priceLabel(product: AdaptyPaywallProduct | undefined): string {
  const price = product?.price;
  if (!price) return '';
  if (price.localizedString) return price.localizedString;
  return `${price.currencySymbol ?? ''}${price.amount?.toFixed(2) ?? ''}`;
}

/**
 * The free-trial phase the store actually granted, or undefined.
 *
 * Trial presence has to be read from StoreKit, never inferred from the product
 * id: introductory offers are added and removed in App Store Connect without a
 * release, and eligibility is per *subscription group* — a customer who already
 * used a trial on one plan gets none on the others, so the same product is
 * trial-bearing for one person and not for the next.
 */
export function freeTrialPhase(
  product: AdaptyPaywallProduct | undefined,
): AdaptyOfferPhase | undefined {
  return (product?.subscription?.offer?.phases ?? []).find(
    (ph) => ph.paymentMode === 'free_trial',
  );
}

/** Localised trial length as the store words it, e.g. "3 days". */
export function trialLength(product: AdaptyPaywallProduct | undefined): string | undefined {
  return freeTrialPhase(product)?.localizedSubscriptionPeriod ?? undefined;
}

export type BillingPeriod = AdaptySubscription['subscriptionPeriod']['unit'];

export function billingPeriod(
  product: AdaptyPaywallProduct | undefined,
): BillingPeriod | undefined {
  return product?.subscription?.subscriptionPeriod?.unit;
}

/**
 * Headline price for a plan card: every plan quoted per week, so the cards
 * compare on one number. The real charge and its cadence live in the sub-line
 * (`billingCadence`), which always names the amount actually billed.
 */
export function periodPriceLabel(product: AdaptyPaywallProduct | undefined): string {
  if (!product) return '';
  const weekly = perWeekPrice(product);
  return weekly ? `${weekly}/wk` : priceLabel(product);
}

/**
 * How the charge recurs — pairs with `periodPriceLabel` in the sub-line.
 * Carries the billed amount for periods longer than a week, where the weekly
 * headline price is a derived number the customer is never actually charged.
 */
export function billingCadence(product: AdaptyPaywallProduct | undefined): string {
  if (!product) return '';
  switch (billingPeriod(product)) {
    case 'year':
      return `billed annually at ${priceLabel(product)}`;
    case 'month':
      return `billed monthly at ${priceLabel(product)}`;
    case 'week':
      return 'billed weekly';
    case 'day':
      return 'billed daily';
    default:
      return '';
  }
}
