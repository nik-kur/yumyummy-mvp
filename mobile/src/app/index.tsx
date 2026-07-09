import { useEffect, useState } from 'react';
import { Redirect } from 'expo-router';
import { ActivityIndicator, View } from 'react-native';

import { useAuth } from '@/state/auth';
import { loadDraft } from '@/state/introDraft';
import { colors } from '@/theme/tokens';

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
  const { status, profile } = useAuth();
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
