import { Redirect } from 'expo-router';
import { ActivityIndicator, View } from 'react-native';

import { useAuth } from '@/state/auth';
import { colors } from '@/theme/tokens';

/** Decides where to send the user on launch based on auth + onboarding state. */
export default function Index() {
  const { status, profile } = useAuth();

  if (status === 'loading') {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={colors.terracotta} />
      </View>
    );
  }

  if (status === 'signedOut') {
    return <Redirect href="/(auth)/sign-in" />;
  }

  if (profile && !profile.onboarding_completed) {
    return <Redirect href="/(onboarding)/goal" />;
  }

  return <Redirect href="/(tabs)" />;
}
