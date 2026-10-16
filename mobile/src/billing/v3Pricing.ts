/**
 * Price and trial wording for the V3 paywall (17–19) and offer (20), always
 * from the store products of the arm's flow — never hard-coded, so price and
 * trial tests in Adapty (P5–P7) need no release.
 *
 * Apple 3.1.2: the amount actually billed is always on screen next to any
 * derived per-month number; `price_emphasis: "billed"` makes it the big one.
 */
import type { AdaptyPaywallProduct } from 'react-native-adapty';

import { freeTrialPhase } from './paywallConfig';

export type Period = 'week' | 'month' | 'year' | 'other';

export function periodOf(p: AdaptyPaywallProduct): Period {
  const sp = p.subscription?.subscriptionPeriod;
  if (!sp) return 'other';
  const n = sp.numberOfUnits || 1;
  if (sp.unit === 'year' && n === 1) return 'year';
  if (sp.unit === 'month' && n === 12) return 'year';
  if (sp.unit === 'month' && n === 1) return 'month';
  if ((sp.unit === 'week' && n === 1) || (sp.unit === 'day' && n === 7)) return 'week';
  return 'other';
}

const ORDER: Record<Period, number> = { week: 0, month: 1, year: 2, other: 3 };

/** Shortest period first, as drawn (Monthly left, Yearly right). */
export function sortPlans(products: AdaptyPaywallProduct[]): AdaptyPaywallProduct[] {
  return [...products].sort((a, b) => ORDER[periodOf(a)] - ORDER[periodOf(b)]);
}

/** The plan selected by default: the yearly one when present (10 of 11 competitors). */
export function defaultPlan(products: AdaptyPaywallProduct[]): AdaptyPaywallProduct | undefined {
  return products.find((p) => periodOf(p) === 'year') ?? products[products.length - 1];
}

/**
 * `amount` written the way the store wrote this product's price: same symbol,
 * same side, same separators, same number of decimals ("$49.99" → "$4.17",
 * "49,99 €" → "4,17 €", "¥7,800" → "¥650").
 */
function likeStorePrice(p: AdaptyPaywallProduct, amount: number): string {
  const store = p.price?.localizedString;
  const num = store?.match(/\d(?:[\d.,\s\u00a0\u202f']*\d)?/)?.[0];
  if (store && num) {
    const dec = num.match(/[.,](\d{1,3})$/);
    // A trailing group of exactly 3 digits is a thousands group ("7,800"), not decimals.
    const decimals = dec && dec[1].length !== 3 ? dec[1].length : 0;
    const decSep = decimals ? num[num.length - decimals - 1] : '.';
    const groupSep = num.replace(/\d/g, '').replace(decimals ? decSep : '', '')[0] ?? (decSep === ',' ? '.' : ',');
    const [int, frac] = amount.toFixed(decimals).split('.');
    const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, groupSep);
    return store.replace(num, frac ? `${grouped}${decSep}${frac}` : grouped);
  }
  const symbol = p.price?.currencySymbol ?? '';
  return `${symbol}${amount.toFixed(2)}`;
}

/** The billed price as the store words it, e.g. "£49.99". */
export function billed(p: AdaptyPaywallProduct): string {
  return p.price?.localizedString ?? '';
}

/** Price per month for longer plans, e.g. yearly £49.99 → "£4.17". */
export function perMonth(p: AdaptyPaywallProduct): string | null {
  const amount = p.price?.amount;
  if (amount === undefined) return null;
  const per = periodOf(p) === 'year' ? amount / 12 : periodOf(p) === 'month' ? amount : null;
  if (per === null) return null;
  return likeStorePrice(p, per);
}

/** "SAVE 58%" for the yearly plan against the monthly one, honest arithmetic, rounded down. */
export function savePercent(products: AdaptyPaywallProduct[]): number | null {
  const y = products.find((p) => periodOf(p) === 'year')?.price?.amount;
  const m = products.find((p) => periodOf(p) === 'month')?.price?.amount;
  if (!y || !m) return null;
  const pct = Math.floor((1 - y / 12 / m) * 100);
  return pct >= 5 ? pct : null;
}

export function planName(p: AdaptyPaywallProduct): string {
  switch (periodOf(p)) {
    case 'week':
      return 'Weekly';
    case 'month':
      return 'Monthly';
    case 'year':
      return 'Yearly';
    default:
      return p.localizedTitle || 'Plan';
  }
}

/** "week", "month", "year" — or "3 months" / "6 months" for other periods. */
export function unitWord(p: AdaptyPaywallProduct): string {
  switch (periodOf(p)) {
    case 'week':
      return 'week';
    case 'month':
      return 'month';
    case 'year':
      return 'year';
    default: {
      const sp = p.subscription?.subscriptionPeriod;
      if (!sp?.unit) return 'period';
      const n = sp.numberOfUnits || 1;
      return n === 1 ? sp.unit : `${n} ${sp.unit}s`;
    }
  }
}

/** Days of free trial this customer gets on this product (0 when not eligible). */
export function trialDays(p: AdaptyPaywallProduct | undefined): number {
  const phase = freeTrialPhase(p);
  if (!phase) return 0;
  const sp = phase.subscriptionPeriod;
  const n = (sp?.numberOfUnits || 1) * (phase.numberOfPeriods || 1);
  switch (sp?.unit) {
    case 'day':
      return n;
    case 'week':
      return n * 7;
    case 'month':
      return n * 30;
    default:
      return n;
  }
}

/** "3 days free, then £4.99 per week" / "£4.99 per week". */
export function trialThenPrice(p: AdaptyPaywallProduct): string {
  const days = trialDays(p);
  const tail = `${billed(p)} per ${unitWord(p)}`;
  return days > 0 ? `${days} day${days === 1 ? '' : 's'} free, then ${tail}` : tail;
}

/** "Just £49.99 per year (£4.17/mo)". */
export function justPerYear(p: AdaptyPaywallProduct): string {
  const pm = periodOf(p) === 'year' ? perMonth(p) : null;
  return `Just ${billed(p)} per ${unitWord(p)}${pm ? ` (${pm}/mo)` : ''}`;
}
