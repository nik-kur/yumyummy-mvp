import { useEffect, useState } from 'react';
import { Redirect } from 'expo-router';
import { ActivityIndicator, View } from 'react-native';
import { CloudOff } from 'lucide-react-native';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useAuth } from '@/state/auth';
import { loadDraft } from '@/state/introDraft';
import { colors, space } from '@/theme/tokens';

/**
 * Launch router — decides where to send the user based on auth, onboarding,
 * and billing state.
 *
 * Routes:
 *   - Signed out, no onboarding draft → (intro) flow
 *   - Signed out with existing intent → (auth) sign-in
 *   - Signed in, onboarding incomplete → (onboarding) legacy flow
 *   - Signed in, no active subscription → /paywall (hard gate)
 *   - Signed in, active → (tabs)
 */
const ACTIVE_STATUSES = new Set(['trial', 'active']);

export default function Index() {
  const { status, profile, retryBoot } = useAuth();
  const [introChecked, setIntroChecked] = useState(false);
  const [hasIntroDraft, setHasIntroDraft] = useState(false);

  useEffect(() => {
    if (status === 'signedOut') {
      loadDraft().then((d) => {
        setHasIntroDraft(d.goal_type !== null);
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
