import { Stack } from 'expo-router';
import { IntroProvider } from '@/state/introContext';
import { colors } from '@/theme/tokens';

export default function IntroLayout() {
  return (
    <IntroProvider>
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.bg },
          gestureEnabled: false,
        }}
      />
    </IntroProvider>
  );
}
