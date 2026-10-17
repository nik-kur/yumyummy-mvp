import { useEffect, useRef } from 'react';
import { View } from 'react-native';
import { Tabs } from 'expo-router';

import { setPreviewGateHandler } from '@/state/previewGate';

import { TabBar } from '@/components/TabBar';
import { PreviewHint } from '@/components/tour/PreviewHint';
import { TourOverlay } from '@/components/tour/TourOverlay';
import { usePreview } from '@/state/usePreview';

export default function TabsLayout() {
  const { preview, freeLogLeft, openLastOffer } = usePreview();

  // Preview mode (21): the backend refused an action (402, or the free log is
  // used up) → Last offer. Only in a preview session; members never see it.
  const previewRef = useRef(preview);
  previewRef.current = preview;
  useEffect(() => {
    setPreviewGateHandler((from) => {
      if (previewRef.current) openLastOffer(from);
    });
    return () => setPreviewGateHandler(null);
  }, [openLastOffer]);
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
      <PreviewHint visible={freeLogLeft} />
    </View>
  );
}
