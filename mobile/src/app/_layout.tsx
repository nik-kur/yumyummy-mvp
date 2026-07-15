import 'react-native-gesture-handler';

import { useEffect } from 'react';
import { Stack } from 'expo-router';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import * as SplashScreen from 'expo-splash-screen';

import { AuthProvider } from '@/state/auth';
import { PendingMealsProvider } from '@/state/pendingMeals';
import { NotificationsBridge } from '@/notifications/NotificationsBridge';
import { WidgetActionBridge } from '@/widgets/WidgetActionBridge';
import { useAppFonts } from '@/theme/useAppFonts';
import { activateAdapty } from '@/billing/adapty';
import { initPostHog } from '@/analytics/posthog';
import { initSentry } from '@/analytics/sentry';
import { initAttribution } from '@/analytics/attribution';
import { colors } from '@/theme/tokens';

SplashScreen.preventAutoHideAsync().catch(() => {});

export default function RootLayout() {
  const fontsLoaded = useAppFonts();

  useEffect(() => {
    initSentry();
    initPostHog();
    void activateAdapty();
    // ATT prompt + AppsFlyer start (no-op without a configured dev key).
    void initAttribution();
  }, []);

  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync().catch(() => {});
  }, [fontsLoaded]);

  if (!fontsLoaded) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.bg }}>
      <SafeAreaProvider>
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
                name="post-purchase"
                options={{
                  presentation: 'fullScreenModal',
                  gestureEnabled: false,
                }}
              />
              <Stack.Screen
                name="postbuy"
                options={{
                  presentation: 'fullScreenModal',
                  gestureEnabled: false,
                }}
              />
              <Stack.Screen name="recap" options={{ presentation: 'modal' }} />
              <Stack.Screen name="week1-report" options={{ presentation: 'card' }} />
            </Stack>
          </PendingMealsProvider>
        </AuthProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
