import { useEffect, useState } from 'react';
import { Redirect } from 'expo-router';
import { ActivityIndicator, View } from 'react-native';
import { CloudOff } from 'lucide-react-native';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { requestTrackingConsent } from '@/analytics/attribution';
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
 *   - Signed out otherwise → (intro) flow (resumes from the local draft)
 *   - Signed in, onboarding incomplete → (onboarding) legacy flow
 *   - Signed in, no active subscription → /paywall (hard gate)
 *   - Signed in, active → (tabs)
 */
const ACTIVE_STATUSES = new Set(['trial', 'active']);

export default function Index() {
  const { status, profile, retryBoot } = useAuth();
  const [introChecked, setIntroChecked] = useState(false);
  const [hasIntroDraft, setHasIntroDraft] = useState(false);
  const [hasPendingPurchase, setHasPendingPurchase] = useState(false);

  // The ATT prompt lives in the onboarding; a returning user who signs in
  // straight from the welcome screen skips it, so ask once here. No-op when
  // already answered.
  useEffect(() => {
    if (status === 'signedIn') void requestTrackingConsent();
  }, [status]);

  useEffect(() => {
    if (status === 'signedOut') {
      Promise.all([loadDraft(), loadPendingPurchase()]).then(([d, pending]) => {
        setHasIntroDraft(d.goal_type !== null);
        setHasPendingPurchase(pending !== null);
        setIntroChecked(true);
      });
    }
  }, [status]);

  if (status === 'loading') {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={colors.terracotta} />
      </View>
    );
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

  if (status === 'signedOut') {
    if (!introChecked) {
      return (
        <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={colors.terracotta} />
        </View>
      );
    }
    // Paid on the paywall, then the app was closed before signing in: the
    // purchase sits on an anonymous Adapty profile with no account behind it.
    // Go straight back to the gate — restarting the intro would look like the
    // purchase was lost.
    if (hasPendingPurchase) {
      return <Redirect href="/save-plan" />;
    }
    return <Redirect href="/(intro)" />;
  }

  if (profile && !profile.onboarding_completed) {
    return <Redirect href="/(onboarding)/goal" />;
  }

  if (profile && !ACTIVE_STATUSES.has(profile.billing.access_status)) {
    return <Redirect href="/paywall" />;
  }

  return <Redirect href="/(tabs)" />;
}
