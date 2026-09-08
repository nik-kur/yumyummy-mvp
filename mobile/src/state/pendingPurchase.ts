/**
 * "Bought, not signed in yet" marker.
 *
 * The acquisition funnel shows the paywall before sign-in, so a purchase lands
 * on an anonymous Adapty profile while we still have no account to attach it
 * to. This marker bridges the gap: written the moment StoreKit confirms the
 * purchase, read by the launch router (a cold start goes straight back to the
 * sign-in gate instead of restarting the intro) and by the gate itself, which
 * hands the anonymous profile id to `/app/billing/sync` so the backend can grant
 * the entitlement even before `identify()` has propagated. Cleared once that
 * reconciliation has run.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = '@yy_pending_purchase';

export interface PendingPurchase {
  /** Anonymous Adapty profile id the purchase landed on (null if unknown). */
  adapty_profile_id: string | null;
  /** Vendor product id, for analytics only. */
  product: string | null;
  /** 'purchase' = StoreKit sheet; 'restore' = Restore Purchases found access. */
  source: 'purchase' | 'restore' | 'existing_access';
  purchased_at: string;
}

export async function savePendingPurchase(
  pending: Omit<PendingPurchase, 'purchased_at'>,
): Promise<void> {
  const value: PendingPurchase = { ...pending, purchased_at: new Date().toISOString() };
  await AsyncStorage.setItem(KEY, JSON.stringify(value)).catch(() => {});
}

export async function loadPendingPurchase(): Promise<PendingPurchase | null> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<PendingPurchase>;
    return {
      adapty_profile_id: parsed.adapty_profile_id ?? null,
      product: parsed.product ?? null,
      source: parsed.source ?? 'purchase',
      purchased_at: parsed.purchased_at ?? new Date().toISOString(),
    };
  } catch {
    return null;
  }
}

export async function clearPendingPurchase(): Promise<void> {
  await AsyncStorage.removeItem(KEY).catch(() => {});
}
