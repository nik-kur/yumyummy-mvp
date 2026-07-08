import { useEffect, useState } from 'react';
import {
  Keyboard,
  LayoutAnimation,
  Platform,
  type KeyboardEvent,
} from 'react-native';

/**
 * Height of the on-screen keyboard in points. 0 when hidden; always 0 on Android
 * (the OS resizes the window instead).
 *
 * Uses `endCoordinates.height` directly — the only reliable signal inside iOS
 * sheet/full-screen modals. Measuring a padded view or subtracting window
 * coords caused the build-28 feedback loop (footer slid back under the keys).
 */
export function useKeyboardHeight(): number {
  const [height, setHeight] = useState(0);

  useEffect(() => {
    if (Platform.OS !== 'ios') return;

    const apply = (e: KeyboardEvent, next: number) => {
      LayoutAnimation.configureNext({
        duration: e.duration > 0 ? e.duration : 250,
        update: { type: LayoutAnimation.Types.keyboard },
      });
      setHeight(next);
    };

    const subs = [
      Keyboard.addListener('keyboardWillChangeFrame', (e) => {
        apply(e, Math.max(0, Math.round(e.endCoordinates.height)));
      }),
      Keyboard.addListener('keyboardWillHide', (e) => apply(e, 0)),
    ];
    return () => subs.forEach((s) => s.remove());
  }, []);

  return height;
}

/** @deprecated use useKeyboardHeight */
export function useKeyboardOverlap(): number {
  return useKeyboardHeight();
}
