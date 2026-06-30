import { useEffect } from 'react';
import * as Notifications from 'expo-notifications';
import { useRouter } from 'expo-router';

import { loadPrefs } from './prefs';
import { configureNotificationHandler, syncFromPrefs } from './scheduler';

/**
 * App-wide notification side effects, mounted once under the providers:
 *  - install the foreground handler,
 *  - re-sync the OS schedule from saved prefs on cold start (idempotent; only
 *    schedules when the master switch is on AND permission is granted),
 *  - route a tapped reminder to the meal-logging screen for two-tap logging.
 */
export function NotificationsBridge() {
  const router = useRouter();

  useEffect(() => {
    configureNotificationHandler();
    void (async () => {
      try {
        await syncFromPrefs(await loadPrefs());
      } catch {
        // never block app start on notification scheduling
      }
    })();

    const sub = Notifications.addNotificationResponseReceivedListener((response) => {
      const route = response.notification.request.content.data?.route;
      if (typeof route === 'string' && route.startsWith('/')) {
        router.push(route as never);
      }
    });
    return () => sub.remove();
  }, [router]);

  return null;
}
