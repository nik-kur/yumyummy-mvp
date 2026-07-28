import 'react-native-gesture-handler';

import { useEffect } from 'react';
import { Stack } from 'expo-router';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider, initialWindowMetrics } from 'react-native-safe-area-context';
import * as SplashScreen from 'expo-splash-screen';

import { AuthProvider } from '@/state/auth';
import { PendingMealsProvider } from '@/state/pendingMeals';
import { NotificationsBridge } from '@/notifications/NotificationsBridge';
import { WidgetActionBridge } from '@/widgets/WidgetActionBridge';
import { useAppFonts } from '@/theme/useAppFonts';
import { bootstrapSdks } from '@/analytics/bootstrap';
import { colors } from '@/theme/tokens';

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  const fontsLoaded = useAppFonts();

  useEffect(() => {
    // Sentry + PostHog + ATT/AppsFlyer + Adapty, in the order Adapty requires.
    void bootstrapSdks();
  }, []);

  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync().catch(() => {});
  }, [fontsLoaded]);

  if (!fontsLoaded) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.bg }}>
      {/* Seed the provider with the natively-measured metrics so the very first
          frame already knows the insets — without them a screen can mount with
          zero padding and render under the Dynamic Island. */}
      <SafeAreaProvider initialMetrics={initialWindowMetrics}>
        <AuthProvider>
          <PendingMealsProvider>
            <NotificationsBridge />
            <WidgetActionBridge />
            <Stack
              screenOptions={{
                headerShown: false,
                contentStyle: { backgroundColor: colors.bg },
              }}
            >
              {/* Full-screen so the keyboard lifts a docked footer reliably
                  (pageSheet modals mis-report overlap and bury the action bar). */}
              <Stack.Screen name="capture" options={{ presentation: 'fullScreenModal' }} />
              <Stack.Screen name="advisor" options={{ presentation: 'modal' }} />
              <Stack.Screen
                name="paywall"
                options={{
                  presentation: 'fullScreenModal',
                  gestureEnabled: false,
                }}
              />
              <Stack.Screen name="meal/[id]" options={{ presentation: 'card' }} />
              <Stack.Screen name="edit-targets" options={{ presentation: 'card' }} />
              <Stack.Screen name="notifications" options={{ presentation: 'card' }} />
              <Stack.Screen
                name="postbuy"
                options={{
                  presentation: 'fullScreenModal',
                  gestureEnabled: false,
                }}
              />
              <Stack.Screen name="recap" options={{ presentation: 'modal' }} />
              <Stack.Screen name="week1-report" options={{ presentation: 'card' }} />
              <Stack.Screen name="sources" options={{ presentation: 'card' }} />
            </Stack>
          </PendingMealsProvider>
        </AuthProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
