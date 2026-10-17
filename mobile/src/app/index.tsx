import { useCallback, useEffect, useState } from 'react';
import { Redirect } from 'expo-router';
import { View } from 'react-native';
import { CloudOff } from 'lucide-react-native';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { SplashIntro, StaticSplash } from '@/components/splash/SplashIntro';
import { requestTrackingConsent } from '@/analytics/attribution';
import {
  getOnboardingConfig,
  resolveOnboardingAssignment,
  restoreOnboardingAssignment,
  type OnboardingAssignment,
} from '@/config/onboardingConfig';
import { useAuth } from '@/state/auth';
import { loadDraft } from '@/state/introDraft';
import { loadPendingPurchase } from '@/state/pendingPurchase';
import { colors, space } from '@/theme/tokens';

/**
 * Launch router — decides where to send the user based on auth, onboarding,
 * and billing state.
 *
 * Routes:
 *   - Signed out, purchase made but not signed in yet → /save-plan (sign-in gate)
 *   - Signed out otherwise → screen 0 (animated splash) while the onboarding
 *     config arrives from Adapty, then the arm's onboarding: V3, or the pre-V3
 *     (intro) flow as the T0 control (both resume from the local draft)
 *   - Signed in, onboarding incomplete → (onboarding) legacy flow
 *   - Signed in, no active subscription → /paywall (hard gate)
 *   - Signed in, active → (tabs)
 *   - Preview mode (closed the offer without buying) → (tabs) in preview,
 *     or the sign-in gate if a purchase is waiting for an account
 */
const ACTIVE_STATUSES = new Set(['trial', 'active']);

export default function Index() {
  const { status, profile, retryBoot } = useAuth();
  const [introChecked, setIntroChecked] = useState(false);
  const [hasIntroDraft, setHasIntroDraft] = useState(false);
  const [hasPendingPurchase, setHasPendingPurchase] = useState(false);
  const [assignment, setAssignment] = useState<OnboardingAssignment | null>(null);
  const [splashDone, setSplashDone] = useState(false);
  const onSplashDone = useCallback(() => setSplashDone(true), []);

  // The ATT prompt lives in the onboarding; a returning user who signs in
  // straight from the welcome screen skips it, so ask once here. No-op when
  // already answered.
  useEffect(() => {
    if (status === 'signedIn') void requestTrackingConsent();
  }, [status]);

  useEffect(() => {
    if (status === 'preview') {
      // Preview Today follows the arm (free_first_log): the stored one only.
      void Promise.all([loadPendingPurchase(), restoreOnboardingAssignment()]).then(([pending]) => {
        setHasPendingPurchase(pending !== null);
        setIntroChecked(true);
      });
      return;
    }
    if (status === 'signedOut') {
      Promise.all([loadDraft(), loadPendingPurchase()]).then(async ([d, pending]) => {
        // Started here, not at launch: only the onboarding needs the arm. A
        // signed-in launch, or a buyer on the way back to the sign-in gate,
        // must not wait for it or be counted in an onb_main test (the gate
        // reads the stored arm only).
        if (pending !== null) await restoreOnboardingAssignment();
        setHasIntroDraft(d.goal_type !== null);
        setHasPendingPurchase(pending !== null);
        setIntroChecked(true);
        if (pending === null) void resolveOnboardingAssignment().then(setAssignment);
      });
    }
  }, [status]);

  // Same look as the native launch screen, so restoring a session is seamless.
  if (status === 'loading') {
    return <StaticSplash />;
  }

  // Signed in, but the backend couldn't be reached at boot. Keep the session
  // and offer a retry — never route to onboarding from here.
  if (status === 'unreachable') {
    return (
      <View
        style={{
          flex: 1,
          backgroundColor: colors.bg,
          alignItems: 'center',
          justifyContent: 'center',
          padding: space.xl,
          gap: space.md,
        }}
      >
        <CloudOff size={40} color={colors.inkMuted} strokeWidth={1.5} />
        <AppText variant="h2" center>
          Can’t reach YumYummy
        </AppText>
        <AppText color={colors.inkMuted} center>
          Your account and diary are safe — we just can’t reach the server right
          now. Check your connection or switch between Wi-Fi and mobile data,
          then try again.
        </AppText>
        <Button
          label="Try Again"
          variant="brand"
          fullWidth={false}
          onPress={() => void retryBoot()}
          style={{ marginTop: space.sm, alignSelf: 'stretch' }}
        />
      </View>
    );
  }

  if (status === 'preview') {
    if (!introChecked) return <StaticSplash />;
    return <Redirect href={hasPendingPurchase ? '/save-plan' : '/(tabs)'} />;
  }

  if (status === 'signedOut') {
    // Paid on the paywall, then the app was closed before signing in: the
    // purchase sits on an anonymous Adapty profile with no account behind it.
    // Go straight back to the gate — restarting the intro would look like the
    // purchase was lost.
    if (introChecked && hasPendingPurchase) {
      return <Redirect href="/save-plan" />;
    }
    // Screen 0 plays while the arm resolves (bounded by ONB_CONFIG_TIMEOUT_MS).
    if (!splashDone || !assignment) {
      return <SplashIntro ready={introChecked && assignment !== null} onDone={onSplashDone} />;
    }
    // Effective config, so a QA override of `onboarding` routes too.
    return <Redirect href={getOnboardingConfig().onboarding === 'v1' ? '/(intro)' : '/(intro)/v3'} />;
  }

  if (profile && !profile.onboarding_completed) {
    return <Redirect href="/(onboarding)/goal" />;
  }

  if (profile && !ACTIVE_STATUSES.has(profile.billing.access_status)) {
    return <Redirect href="/paywall" />;
  }

  return <Redirect href="/(tabs)" />;
}
