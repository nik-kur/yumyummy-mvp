import { useEffect, useRef } from 'react';
import { View } from 'react-native';
import { Tabs, useRouter } from 'expo-router';

import { track } from '@/analytics/posthog';
import { setPreviewGateHandler } from '@/state/previewGate';

import { TabBar } from '@/components/TabBar';
import { PreviewHint } from '@/components/tour/PreviewHint';
import { TourOverlay } from '@/components/tour/TourOverlay';
import { getOnboardingConfig } from '@/config/onboardingConfig';
import { useAuth } from '@/state/auth';
import { usePendingMeals } from '@/state/pendingMeals';

export default function TabsLayout() {
  const { status, profile } = useAuth();
  const { pending } = usePendingMeals();
  const router = useRouter();

  // Preview mode (21): the backend refused an action (402, or the free log is
  // used up) → Last offer. Only in a preview session; members never see it.
  const statusRef = useRef(status);
  statusRef.current = status;
  const lastGate = useRef(0);
  useEffect(() => {
    setPreviewGateHandler((from) => {
      if (statusRef.current !== 'preview' || Date.now() - lastGate.current < 1500) return;
      lastGate.current = Date.now();
      track('preview_gate', { from });
      router.push('/paywall?last_offer=1');
    });
    return () => setPreviewGateHandler(null);
  }, [router]);
  const previewHint =
    status === 'preview' &&
    Boolean(profile?.preview_free_log_available) &&
    getOnboardingConfig().free_first_log &&
    pending.length === 0;
  return (
    <View style={{ flex: 1 }}>
      <Tabs
        tabBar={(props) => (
          <TabBar
            routes={props.state.routes}
            activeIndex={props.state.index}
            onNavigate={(name) => props.navigation.navigate(name as never)}
          />
        )}
        screenOptions={{ headerShown: false }}
      >
        <Tabs.Screen name='index' options={{ title: 'Today' }} />
        <Tabs.Screen name='menu' options={{ title: 'My Menu' }} />
        <Tabs.Screen name='week' options={{ title: 'Week' }} />
        <Tabs.Screen name='profile' options={{ title: 'Profile' }} />
      </Tabs>
      {/* Post-purchase tour (24) over Today and the tab bar. */}
      <TourOverlay scope='tabs' />
      {/* Preview mode (21): "See how it works" over the "+". */}
      <PreviewHint visible={previewHint} />
    </View>
  );
}
