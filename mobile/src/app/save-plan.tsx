/**
 * Post-purchase sign-in gate — Sign in with Apple, no way past it.
 *
 * Order of the acquisition funnel: intro quiz → plan reveal → paywall → THIS
 * screen → postbuy → app. The paywall runs before sign-in so the trial decision
 * is never taxed by an account prompt; the account is created right after the
 * purchase, because every other part of the app (diary, plan, sync) needs one.
 *
 * Buying first means the receipt lands on an anonymous Adapty profile and the
 * webhook reaches the backend with no account to attach it to. This screen
 * closes that gap explicitly, in order and awaited:
 *   1. sign in (creates/loads the account; auth kicks off adapty.identify());
 *   2. push the onboarding draft (targets, onboarding_completed);
 *   3. `/app/billing/sync` with the anonymous profile id captured at purchase,
 *      so the entitlement is granted server-side before the user reaches Today;
 *   4. clear the pending-purchase marker and continue to /postbuy.
 * Every step after sign-in is best-effort: nothing here may strand a paying
 * user — the launch router and the paywall's own Adapty-side check are the
 * safety nets if a network call fails.
 *
 * The local intro draft is deliberately kept: it fills the paywall placeholders
 * and Today's plan if the user relaunches before the profile has synced.
 */
import { useCallback, useEffect, useState } from 'react';
import { View, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import * as AppleAuthentication from 'expo-apple-authentication';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useAuth } from '@/state/auth';
import { loadDraft } from '@/state/introDraft';
import {
  clearPendingPurchase,
  loadPendingPurchase,
  type PendingPurchase,
} from '@/state/pendingPurchase';
import { getAdaptyProfileId, isAdaptyConfigured } from '@/billing/adapty';
import * as api from '@/api/endpoints';
import { ApiError, getToken } from '@/api/client';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';
import { addBreadcrumb, captureException } from '@/analytics/sentry';

const MAX_SYNC_ATTEMPTS = 3;
const SYNC_RETRY_DELAY_MS = 500;

const REASONS = [
  { emoji: '🔒', text: 'Your plan, diary and subscription are saved to your account, not just this phone' },
  { emoji: '📱', text: 'Log from any device and pick up exactly where you left off' },
  { emoji: '🍎', text: 'Apple hides your email if you want — we never see a password' },
];

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function SavePlanScreen() {
  const router = useRouter();
  const { signInWithProvider, refreshProfile } = useAuth();
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingPurchase | null>(null);
  // null = still checking. Render no Apple button until we know, so the
  // non-compliant fallback never flashes where the official one is available
  // (App Review Guideline 4).
  const [appleAvailable, setAppleAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    loadPendingPurchase().then(setPending).catch(() => {});
  }, []);

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'N2b_save_plan', placement: 'post_paywall' });
    track('signin_gate_shown', { placement: 'post_paywall' });
  }, []);

  useEffect(() => {
    AppleAuthentication.isAvailableAsync()
      .then(setAppleAvailable)
      .catch(() => setAppleAvailable(false));
  }, []);

  // Pushing the draft has failed in the wild with a 401 immediately after a
  // sign-in that reported success, losing the whole questionnaire. We still
  // refuse to strand the user, so instead of surfacing it we retry, then record
  // enough context (status, whether a token was even present) to diagnose it.
  const syncDraft = useCallback(async () => {
    const intro = await loadDraft();
    if (!intro.goal_type) return;
    const payload = {
      goal_type: intro.goal_type,
      gender: intro.gender,
      age: intro.age,
      height_cm: intro.height_cm,
      weight_kg: intro.weight_kg,
      activity_level: intro.activity_level,
      target_calories: intro.target_calories,
      target_protein_g: intro.target_protein_g,
      target_fat_g: intro.target_fat_g,
      target_carbs_g: intro.target_carbs_g,
      onboarding_completed: true,
    };

    for (let attempt = 1; attempt <= MAX_SYNC_ATTEMPTS; attempt += 1) {
      try {
        await api.updateMe(payload);
        if (attempt > 1) track('signin_profile_sync_recovered', { attempts: attempt });
        return;
      } catch (e) {
        const httpStatus = e instanceof ApiError ? e.status : null;
        const hasToken = Boolean(await getToken());
        addBreadcrumb('auth', `Profile sync attempt ${attempt} failed`, {
          status: httpStatus,
          has_token: hasToken,
        });
        if (attempt === MAX_SYNC_ATTEMPTS) {
          track('signin_profile_sync_failed', {
            status: httpStatus,
            has_token: hasToken,
            error: e instanceof Error ? e.message : String(e),
          });
          captureException(e, { attempts: attempt, status: httpStatus, has_token: hasToken });
          return;
        }
        await delay(SYNC_RETRY_DELAY_MS * attempt);
      }
    }
  }, []);

  /**
   * Attach the pre-sign-in purchase to the account we just signed into.
   *
   * `/billing/sync` resolves the anonymous profile by id, so this works whether
   * or not `identify()` (started in the background by sign-in) has propagated.
   * Retried, because the first request right after sign-in has seen 401s.
   */
  const reconcilePurchase = useCallback(async () => {
    const marker = pending ?? (await loadPendingPurchase());
    if (!marker) return;

    for (let attempt = 1; attempt <= MAX_SYNC_ATTEMPTS; attempt += 1) {
      try {
        if (isAdaptyConfigured()) {
          const profileId = marker.adapty_profile_id ?? (await getAdaptyProfileId());
          const billing = await api.syncBilling(profileId);
          track('post_purchase_billing_synced', {
            source: marker.source,
            access_status: billing.access_status,
            attempts: attempt,
          });
        } else {
          // Dev/mock build without Adapty: the paywall couldn't start the trial
          // while signed out, so start it now that there is an account.
          await api.startTrial(3);
        }
        return;
      } catch (e) {
        addBreadcrumb('billing', `Post-purchase sync attempt ${attempt} failed`, {
          status: e instanceof ApiError ? e.status : null,
        });
        if (attempt === MAX_SYNC_ATTEMPTS) {
          track('post_purchase_billing_sync_failed', {
            source: marker.source,
            error: e instanceof Error ? e.message : String(e),
          });
          captureException(e, { stage: 'post_purchase_billing_sync' });
          return;
        }
        await delay(SYNC_RETRY_DELAY_MS * attempt);
      }
    }
  }, [pending]);

  const handleSignIn = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    addBreadcrumb('auth', 'Post-purchase gate Apple sign-in started');

    try {
      const signedIn = await signInWithProvider('apple');
      const hasToken = Boolean(await getToken());
      // Dismissing Apple's sheet is not a sign-in. Stay on the gate: there is a
      // paid purchase on this device with no account behind it yet, and the app
      // is unusable without one. The token is checked too, so any other path
      // that fails to authenticate is caught here.
      if (!signedIn || !hasToken) {
        track('signin_gate_canceled', { reason: signedIn ? 'no_token' : 'dismissed' });
        return;
      }
      track('signin_gate_success', { placement: 'post_paywall' });

      await syncDraft();
      await reconcilePurchase();
      // Pull the reconciled billing + synced targets into state so Today and the
      // launch router see the entitlement without waiting for a background sync.
      await refreshProfile().catch(() => {});
      await clearPendingPurchase();

      track('onboarding_screen_completed', { screen: 'N2b_save_plan' });
      router.replace('/postbuy');
    } catch (e) {
      captureException(e);
      track('signin_gate_failed', {
        error: e instanceof Error ? e.message : String(e),
      });
      Alert.alert('Sign in failed', 'Please try again.');
    } finally {
      setBusy(false);
    }
  }, [busy, signInWithProvider, syncDraft, reconcilePurchase, refreshProfile, router]);

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.center}>
        <View style={s.successPill}>
          <AppText variant="caption" color={colors.success}>
            ✓ Trial started — one last step
          </AppText>
        </View>
        <AppText variant="h1" center style={s.title}>
          Save your plan
        </AppText>
        <AppText variant="body" color={colors.inkMuted} center style={s.sub}>
          Your plan is built and your trial is active. Sign in to keep them —
          so they’re still here tomorrow, and on every device you use.
        </AppText>

        <View style={s.reasons}>
          {REASONS.map((row) => (
            <View key={row.emoji} style={s.reasonRow}>
              <AppText style={s.reasonEmoji}>{row.emoji}</AppText>
              <AppText variant="small" color={colors.ink} style={s.reasonText}>
                {row.text}
              </AppText>
            </View>
          ))}
        </View>
      </View>

      <View style={s.bottom}>
        {/* Official Sign in with Apple button — HIG-required artwork with the
            Apple logo (App Review Guideline 4). The plain-button fallback only
            exists for environments without the native module (Expo Go). */}
        {busy ? (
          <View style={s.busyBox}>
            <ActivityIndicator color={colors.ink} />
          </View>
        ) : appleAvailable === null ? (
          <View style={s.busyBox} />
        ) : appleAvailable ? (
          <AppleAuthentication.AppleAuthenticationButton
            buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
            buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.BLACK}
            cornerRadius={radius.md}
            style={s.appleButton}
            onPress={handleSignIn}
          />
        ) : (
          <Button label="Sign in with Apple" variant="primary" onPress={handleSignIn} />
        )}
        <AppText variant="caption" color={colors.inkFaint} center>
          No password. Nothing shared with anyone.
        </AppText>
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: space.sm },
  successPill: {
    alignSelf: 'center',
    backgroundColor: colors.successSoft,
    borderRadius: radius.pill,
    paddingHorizontal: space.base,
    paddingVertical: space.xs,
  },
  title: { marginTop: space.md },
  sub: { marginTop: space.md },
  reasons: {
    alignSelf: 'stretch',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.base,
    gap: space.md,
    marginTop: space.xl,
  },
  reasonRow: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  reasonEmoji: { fontSize: 20, lineHeight: 26 },
  reasonText: { flex: 1 },
  bottom: { paddingBottom: space.lg, gap: space.md },
  appleButton: { alignSelf: 'stretch', height: 54 },
  busyBox: { height: 54, alignItems: 'center', justifyContent: 'center' },
});
