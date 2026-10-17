/**
 * Bottom sheet in a modal: the backdrop fades in and out in place, only the
 * sheet slides. (`<Modal animationType="slide">` slid the whole window, dim
 * included, up and down the screen.)
 */
import { useEffect, useState, type ReactNode } from 'react';
import { Modal, StyleSheet, View, useWindowDimensions } from 'react-native';
import Animated, { Easing, useAnimatedStyle, useSharedValue, withTiming } from 'react-native-reanimated';

import { colors } from '@/theme/tokens';

const IN_MS = 300;
const OUT_MS = 220;

interface Props {
  visible: boolean;
  onRequestClose: () => void;
  children: ReactNode;
  /** Backdrop colour; the app's overlay by default. */
  backdrop?: string;
}

export function SheetModal({ visible, onRequestClose, children, backdrop = colors.overlay }: Props) {
  const { height } = useWindowDimensions();
  const [mounted, setMounted] = useState(visible);
  const p = useSharedValue(0);

  useEffect(() => {
    if (visible) {
      setMounted(true);
      p.value = withTiming(1, { duration: IN_MS, easing: Easing.out(Easing.cubic) });
      return;
    }
    p.value = withTiming(0, { duration: OUT_MS, easing: Easing.in(Easing.cubic) });
    const t = setTimeout(() => setMounted(false), OUT_MS);
    return () => clearTimeout(t);
  }, [visible, p]);

  const dim = useAnimatedStyle(() => ({ opacity: p.value }));
  const slide = useAnimatedStyle(() => ({ transform: [{ translateY: (1 - p.value) * height }] }));

  return (
    <Modal visible={mounted} transparent animationType="none" onRequestClose={onRequestClose} statusBarTranslucent>
      <View style={s.root}>
        <Animated.View style={[StyleSheet.absoluteFill, { backgroundColor: backdrop }, dim]} />
        {/* Fills the screen so a sheet's `maxHeight: '88%'` resolves against it;
            the sheet itself sits at the bottom. */}
        <Animated.View style={[s.slot, slide]} pointerEvents="box-none">
          {children}
        </Animated.View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, justifyContent: 'flex-end' },
  slot: { ...StyleSheet.absoluteFillObject, justifyContent: 'flex-end' },
});
