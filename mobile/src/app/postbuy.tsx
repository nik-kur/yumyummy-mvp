/**
 * Post-purchase push opt-in — shown once after Apple sign-in (prototype
 * "postbuy" screen). "Enable reminders" asks the OS permission, turns the
 * master switch on and schedules the default reminder set; "Maybe later"
 * continues straight to the app. Both paths end in the Today tab.
 */
import { useCallback, useEffect, useState } from 'react';
import { View, StyleSheet, Pressable } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { requestPermission, syncFromPrefs } from '@/notifications/scheduler';
import { loadPrefs, savePrefs } from '@/notifications/prefs';
import { reportJourneyEvent } from '@/state/journey';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';
import { addBreadcrumb, captureException } from '@/analytics/sentry';

const WHY_ROWS = [
  { emoji: '🌱', text: 'Morning nudges for your first-week quests — tiny steps that build the habit' },
  { emoji: '🌙', text: 'One evening check-in so no day slips by unlogged' },
  { emoji: '📊', text: 'A heads-up when your weekly recap is ready' },
];

export default function PostbuyPushScreen() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    track('postbuy_push_screen_viewed');
  }, []);

  const goToApp = useCallback(() => {
    router.replace('/(tabs)');
  }, [router]);

  const enableReminders = useCallback(async () => {
    setBusy(true);
    addBreadcrumb('notifications', 'Post-purchase enable reminders tapped');
    try {
      const granted = await requestPermission();
      track(granted ? 'push_permission_granted' : 'push_permission_denied', {
        context: 'postbuy',
      });
      if (granted) {
        const prefs = await loadPrefs();
        prefs.enabled = true;
        await savePrefs(prefs);
        await syncFromPrefs(prefs);
        await reportJourneyEvent({ type: 'push_permission_granted' }).catch(() => {});
      }
    } catch (e) {
      captureException(e);
    } finally {
      setBusy(false);
      goToApp();
    }
  }, [goToApp]);

  const skip = useCallback(() => {
    track('postbuy_push_skipped');
    goToApp();
  }, [goToApp]);

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.center}>
        <View style={s.successPill}>
          <AppText variant="caption" color={colors.success}>
            ✓ Trial started — you’re all set
          </AppText>
        </View>

        <AppText variant="h1" center style={s.title}>
          Turn on reminders to hit your goal
        </AppText>
        <AppText variant="body" color={colors.inkMuted} center style={s.sub}>
          Your plan only works when logging becomes a habit — and that’s exactly
          what we help with.
        </AppText>

        <View style={s.whyList}>
          {WHY_ROWS.map((row) => (
            <View key={row.emoji} style={s.whyRow}>
              <AppText style={s.whyEmoji}>{row.emoji}</AppText>
              <AppText variant="small" color={colors.ink} style={s.whyText}>
                {row.text}
              </AppText>
            </View>
          ))}
        </View>

        <AppText variant="caption" color={colors.inkFaint} center>
          People who turn on reminders stick with tracking 3× longer.
        </AppText>
      </View>

      <View style={s.bottom}>
        <Button
          label={busy ? 'One moment…' : 'Enable reminders'}
          variant="brand"
          loading={busy}
          onPress={enableReminders}
        />
        <Pressable onPress={skip} hitSlop={8}>
          <AppText variant="small" color={colors.inkMuted} center style={s.later}>
            Maybe later
          </AppText>
        </Pressable>
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', gap: space.base },
  successPill: {
    alignSelf: 'center',
    backgroundColor: colors.successSoft,
    borderRadius: radius.pill,
    paddingHorizontal: space.base,
    paddingVertical: space.xs,
  },
  title: { marginTop: space.xs },
  sub: { paddingHorizontal: space.sm },
  whyList: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.base,
    gap: space.md,
    marginTop: space.sm,
  },
  whyRow: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  whyEmoji: { fontSize: 20, lineHeight: 26 },
  whyText: { flex: 1 },
  bottom: { gap: space.md, paddingBottom: space.lg },
  later: { paddingVertical: space.xs },
});
