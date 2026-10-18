/**
 * The offer's close button, shown only after a short beat so the offer gets
 * read before it can be dismissed (Nikita, build 64). Until then there is
 * nothing to tap; then it fades in.
 */
import { useEffect, useState, type ReactNode } from 'react';
import type { StyleProp, ViewStyle } from 'react-native';
import Animated, { FadeIn } from 'react-native-reanimated';

export const OFFER_CLOSE_DELAY_MS = 2500;

export function DelayedClose({ style, children }: { style?: StyleProp<ViewStyle>; children: ReactNode }) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShown(true), OFFER_CLOSE_DELAY_MS);
    return () => clearTimeout(t);
  }, []);
  if (!shown) return null;
  return (
    <Animated.View entering={FadeIn.duration(300)} style={style}>
      {children}
    </Animated.View>
  );
}
