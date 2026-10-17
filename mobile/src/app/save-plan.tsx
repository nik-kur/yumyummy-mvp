/**
 * Post-purchase sign-in gate — Sign in with Apple, no way past it.
 *
 * Order of the acquisition funnel (V3): intro quiz → plan reveal → paywall →
 * Success (22) → THIS screen (23) → Today with the tour (24). The paywall runs before sign-in so the trial decision
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
 *   4. clear the pending-purchase marker and continue to Today; a new buyer
 *      (not a restore) gets the tour and the first-log payoff.
 * Every step after sign-in is best-effort: nothing here may strand a paying
 * user — the launch router and the paywall's own Adapty-side check are the
 * safety nets if a network call fails.
 *
 * The local intro draft is deliberately kept: it fills the paywall placeholders
 * and Today's plan if the user relaunches before the profile has synced.
 */
import { useCallback, useEffect, useState } from 'react';
import { View, StyleSheet, Alert, ActivityIndicator, Image, Linking, Text } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import * as AppleAuthentication from 'expo-apple-authentication';
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withSequence,
  withTiming,
} from 'react-native-reanimated';

import { Button } from '@/components/Button';
import { clearOnboardingAssignment, getOnboardingConfig, resolveOnboardingAssignment } from '@/config/onboardingConfig';
import { enableRemindersAfterPurchase } from '@/notifications/scheduler';
import { IMG } from '@/onb/assets';
import { C, F, PAD } from '@/onb/theme';
import { reportJourneyEvent } from '@/state/journey';
import { startPostPurchase } from '@/state/tour';
import { lastSignInCreatedAccount, useAuth } from '@/state/auth';
import { AI_PROVIDERS_LABEL, grantAIConsent, hasAIConsent } from '@/state/aiConsent';
import { PRIVACY_URL } from '@/components/pw/PwParts';
import { loadDraft } from '@/state/introDraft';
import {
  clearPendingPurchase,
  loadPendingPurchase,
  type PendingPurchase,
} from '@/state/pendingPurchase';
import { getAdaptyProfileId, isAdaptyConfigured } from '@/billing/adapty';
import * as api from '@/api/endpoints';
import { ApiError, getToken } from '@/api/client';
import { track } from '@/analytics/posthog';
import { addBreadcrumb, captureException } from '@/analytics/sentry';

const MAX_SYNC_ATTEMPTS = 3;
const SYNC_RETRY_DELAY_MS = 500;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/** Canvas `yy-float`, 3.2 s: the cloud drifts up 8 pt and back. */
function FloatingCloud() {
  const t = useSharedValue(0);
  useEffect(() => {
    const e = Easing.inOut(Easing.ease);
    t.value = withRepeat(withSequence(withTiming(-8, { duration: 1600, easing: e }), withTiming(0, { duration: 1600, easing: e })), -1);
    return () => cancelAnimation(t);
  }, [t]);
  const style = useAnimatedStyle(() => ({ transform: [{ translateY: t.value }] }));
  return (
    <Animated.View style={[s.cloudBox, style]}>
      <Image source={IMG.save_cloud} style={s.cloud} accessibilityLabel="A cloud with a check mark" />
    </Animated.View>
  );
}

export default function SavePlanScreen() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { signInWithProvider, refreshProfile } = useAuth();
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<PendingPurchase | null>(null);
  // null = still checking. Render no Apple button until we know, so the
  // non-compliant fallback never flashes where the official one is available
  // (App Review Guideline 4).
  const [appleAvailable, setAppleAvailable] = useState<boolean | null>(null);
  // AI consent on this screen (`ai_consent: save_plan`), unless already given.
  const [showAiLine, setShowAiLine] = useState(false);
  useEffect(() => {
    if (getOnboardingConfig().ai_consent !== 'save_plan') return;
    void hasAIConsent().then((has) => setShowAiLine(!has));
  }, []);

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
      // The disclosure line above the button was the AI consent (App Review
      // 5.1.2(i)): record it, so the first log in the tour asks nothing more.
      if (showAiLine) await grantAIConsent();

      await syncDraft();
      await reconcilePurchase();
      // Pull the reconciled billing + synced targets into state so Today and the
      // launch router see the entitlement without waiting for a background sync.
      await refreshProfile().catch(() => {});
      const marker = pending ?? (await loadPendingPurchase());
      await clearPendingPurchase();
      // A new buyer on a new account gets reminders (if allowed on B2), the
      // tour (if this arm has `tutorial` on) and the first-log payoff. A
      // restore, or an Apple ID that already had an account, goes straight in.
      // The arm is read after a cold start too (resolve reads the stored one);
      // then it has done its job: forget it, keep the super properties.
      if (marker?.source === 'purchase') {
        try {
          if (await enableRemindersAfterPurchase()) {
            await reportJourneyEvent({ type: 'push_permission_granted' }).catch(() => {});
          }
        } catch (e) {
          captureException(e);
        }
        if (lastSignInCreatedAccount()) {
          await resolveOnboardingAssignment().catch(() => null);
          await startPostPurchase(getOnboardingConfig().tutorial);
        }
      }
      await clearOnboardingAssignment();

      track('onboarding_screen_completed', { screen: 'N2b_save_plan' });
      router.replace('/(tabs)');
    } catch (e) {
      captureException(e);
      track('signin_gate_failed', {
        error: e instanceof Error ? e.message : String(e),
      });
      Alert.alert('Sign in failed', 'Please try again.');
    } finally {
      setBusy(false);
    }
  }, [busy, signInWithProvider, syncDraft, reconcilePurchase, refreshProfile, router, pending, showAiLine]);

  return (
    <View style={[s.screen, { paddingTop: insets.top + PAD.topBelowStatus, paddingBottom: Math.max(insets.bottom, 20) }]}>
      <View style={{ flex: 1 }} />
      <FloatingCloud />
      <Text style={s.h1} accessibilityRole="header">
        Save your plan
      </Text>
      <Text style={s.sub}>Your plan, diary and subscription stay safe in your account, on any device.</Text>
      <View style={{ flex: 1.3 }} />
      {showAiLine ? (
        <Text style={s.ai}>
          By continuing, you agree that what you log (text, voice and photos) is analysed by our AI partners,{' '}
          {AI_PROVIDERS_LABEL}.{' '}
          <Text style={s.aiLink} onPress={() => void Linking.openURL(PRIVACY_URL)} accessibilityRole="link">
            Privacy Policy
          </Text>
        </Text>
      ) : null}

      {/* Official Sign in with Apple button — HIG-required artwork with the
          Apple logo (App Review Guideline 4). The plain-button fallback only
          exists for environments without the native module (Expo Go). */}
      {busy ? (
        <View style={s.busyBox}>
          <ActivityIndicator color={C.ink} />
        </View>
      ) : appleAvailable === null ? (
        <View style={s.busyBox} />
      ) : appleAvailable ? (
        <AppleAuthentication.AppleAuthenticationButton
          buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
          buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.BLACK}
          cornerRadius={12}
          style={s.appleButton}
          onPress={handleSignIn}
        />
      ) : (
        <Button label="Sign in with Apple" variant="primary" onPress={handleSignIn} />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.paper, paddingHorizontal: PAD.side },
  cloudBox: { alignSelf: 'center', width: 150, height: 150 },
  cloud: { width: 150, height: 150 },
  h1: {
    marginTop: 24,
    textAlign: 'center',
    fontFamily: F.serif,
    fontSize: 34,
    lineHeight: 40,
    letterSpacing: -0.34,
    color: C.ink,
  },
  sub: { marginTop: 10, textAlign: 'center', fontFamily: F.sans, fontSize: 18, lineHeight: 27, color: C.muted },
  ai: { marginBottom: 14, textAlign: 'center', fontFamily: F.sans, fontSize: 13, lineHeight: 18, color: C.muted },
  aiLink: { color: C.info },
  appleButton: { alignSelf: 'stretch', height: 54 },
  busyBox: { height: 54, alignItems: 'center', justifyContent: 'center' },
});
