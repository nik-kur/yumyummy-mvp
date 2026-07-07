import { useEffect } from 'react';
import { AppState, Platform } from 'react-native';
import { useRouter } from 'expo-router';

const APP_GROUP = 'group.ai.yumyummy.app';
const PENDING_KEY = 'pendingCaptureMode';

type Storage = { get: (key: string) => string | null; remove: (key: string) => void };

/**
 * Bridges widget quick-action taps into in-app navigation.
 *
 * Widget buttons run an App Intent that writes `pendingCaptureMode` into the
 * shared App Group and opens the app (we can't use iOS 18's `OpenURLIntent` on
 * our iOS 17 target). Here we read that value on cold start and on every
 * foreground, route to the matching screen, then clear it so it fires once.
 *
 * No-ops on Android and in Expo Go / dev where the native module is absent.
 */
export function WidgetActionBridge() {
  const router = useRouter();

  useEffect(() => {
    if (Platform.OS !== 'ios') return;

    let storage: Storage | null = null;
    try {
      const { ExtensionStorage } = require('@bacons/apple-targets');
      storage = new ExtensionStorage(APP_GROUP) as Storage;
    } catch {
      return; // native module unavailable
    }

    const consume = () => {
      try {
        const mode = storage?.get(PENDING_KEY);
        if (!mode) return;
        storage?.remove(PENDING_KEY);
        switch (mode) {
          case 'saved':
            router.push('/menu');
            break;
          case 'photo':
            router.push({ pathname: '/capture', params: { mode: 'photo' } });
            break;
          case 'voice':
            router.push({ pathname: '/capture', params: { mode: 'voice' } });
            break;
          default:
            router.push({ pathname: '/capture', params: { mode: 'text' } });
        }
      } catch {
        // ignore — never let widget routing crash the app
      }
    };

    // Cold start: defer briefly so the root navigator is mounted before we push.
    const cold = setTimeout(consume, 300);
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') consume();
    });
    return () => {
      clearTimeout(cold);
      sub.remove();
    };
  }, [router]);

  return null;
}
