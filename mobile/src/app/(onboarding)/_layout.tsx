import { Stack } from 'expo-router';
import { OnboardingProvider } from '@/state/onboarding';
import { colors } from '@/theme/tokens';

export default function OnboardingLayout() {
  return (
    <OnboardingProvider>
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.bg },
          gestureEnabled: false,
        }}
      />
    </OnboardingProvider>
  );
}
