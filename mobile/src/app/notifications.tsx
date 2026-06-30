import { useCallback, useEffect, useRef, useState } from 'react';
import { View, StyleSheet, Pressable, Switch, Platform, AppState, Linking } from 'react-native';
import { useRouter } from 'expo-router';
import { ChevronLeft } from 'lucide-react-native';
import DateTimePicker, { type DateTimePickerEvent } from '@react-native-community/datetimepicker';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { colors, radius, space } from '@/theme/tokens';
import {
  type NotificationPrefs,
  type ReminderPref,
  DEFAULT_PREFS,
  loadPrefs,
  savePrefs,
  formatTime,
} from '@/notifications/prefs';
import {
  getPermissionGranted,
  requestPermission,
  syncFromPrefs,
} from '@/notifications/scheduler';

function dateFor(hour: number, minute: number): Date {
  const d = new Date();
  d.setHours(hour, minute, 0, 0);
  return d;
}

function ReminderRow({
  reminder,
  dimmed,
  onToggle,
  onTime,
  last,
}: {
  reminder: ReminderPref;
  dimmed: boolean;
  onToggle: (enabled: boolean) => void;
  onTime: (hour: number, minute: number) => void;
  last?: boolean;
}) {
  const [picking, setPicking] = useState(false);

  const onChange = (event: DateTimePickerEvent, selected?: Date) => {
    if (Platform.OS === 'android') setPicking(false);
    if (event.type === 'set' && selected) onTime(selected.getHours(), selected.getMinutes());
  };

  return (
    <View style={[styles.row, !last && styles.rowBorder]}>
      <AppText variant="body" color={reminder.enabled ? colors.ink : colors.inkFaint} style={styles.flex}>
        {reminder.label}
      </AppText>

      {Platform.OS === 'ios' ? (
        <DateTimePicker
          value={dateFor(reminder.hour, reminder.minute)}
          mode="time"
          display="compact"
          onChange={onChange}
          disabled={dimmed || !reminder.enabled}
          accentColor={colors.terracotta}
          themeVariant="light"
        />
      ) : (
        <>
          <Pressable
            onPress={() => setPicking(true)}
            disabled={dimmed || !reminder.enabled}
            style={styles.timePill}
          >
            <AppText variant="bodyStrong" color={reminder.enabled ? colors.ink : colors.inkFaint}>
              {formatTime(reminder.hour, reminder.minute)}
            </AppText>
          </Pressable>
          {picking ? (
            <DateTimePicker value={dateFor(reminder.hour, reminder.minute)} mode="time" onChange={onChange} />
          ) : null}
        </>
      )}

      <Switch
        value={reminder.enabled}
        onValueChange={onToggle}
        disabled={dimmed}
        trackColor={{ true: colors.terracotta, false: colors.hairlineStrong }}
        thumbColor={colors.white}
        ios_backgroundColor={colors.hairlineStrong}
      />
    </View>
  );
}

export default function NotificationsScreen() {
  const router = useRouter();
  const [prefs, setPrefs] = useState<NotificationPrefs>(DEFAULT_PREFS);
  const [granted, setGranted] = useState<boolean | null>(null);
  const [loaded, setLoaded] = useState(false);

  // Load saved prefs + current OS permission on mount.
  useEffect(() => {
    let active = true;
    (async () => {
      const [p, g] = await Promise.all([loadPrefs(), getPermissionGranted()]);
      if (!active) return;
      setPrefs(p);
      setGranted(g);
      setLoaded(true);
    })();
    return () => {
      active = false;
    };
  }, []);

  // Re-check permission when returning from the OS Settings app, and re-sync so
  // newly-granted permission immediately activates the saved reminders.
  const prefsRef = useRef(prefs);
  prefsRef.current = prefs;
  useEffect(() => {
    const sub = AppState.addEventListener('change', (s) => {
      if (s !== 'active') return;
      void (async () => {
        const g = await getPermissionGranted();
        setGranted(g);
        await syncFromPrefs(prefsRef.current);
      })();
    });
    return () => sub.remove();
  }, []);

  // Persist + reschedule on every change. Single source of truth = `next`.
  const apply = useCallback(async (next: NotificationPrefs) => {
    setPrefs(next);
    await savePrefs(next);
    await syncFromPrefs(next);
  }, []);

  const onToggleMaster = useCallback(
    async (on: boolean) => {
      if (on) {
        const ok = await requestPermission();
        setGranted(ok);
      }
      await apply({ ...prefs, enabled: on });
    },
    [apply, prefs],
  );

  const onToggleReminder = useCallback(
    (id: string, enabled: boolean) => {
      void apply({
        ...prefs,
        reminders: prefs.reminders.map((r) => (r.id === id ? { ...r, enabled } : r)),
      });
    },
    [apply, prefs],
  );

  const onReminderTime = useCallback(
    (id: string, hour: number, minute: number) => {
      void apply({
        ...prefs,
        reminders: prefs.reminders.map((r) => (r.id === id ? { ...r, hour, minute } : r)),
      });
    },
    [apply, prefs],
  );

  const needsPermission = prefs.enabled && granted === false;

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={26} color={colors.inkMuted} strokeWidth={1.5} />
        </Pressable>
        <AppText variant="overline" color={colors.inkMuted}>
          Notifications
        </AppText>
        <View style={{ width: 26 }} />
      </View>

      <AppText variant="h1" style={styles.title}>
        Reminders
      </AppText>
      <AppText variant="body" color={colors.inkMuted} style={styles.subtitle}>
        Gentle daily nudges to log your meals. Everything runs on your device — no
        spam, and you can turn any of them off.
      </AppText>

      <Card padded={false}>
        <View style={[styles.row, styles.rowBorder]}>
          <View style={styles.flex}>
            <AppText variant="body">Daily reminders</AppText>
            <AppText variant="caption" color={colors.inkFaint}>
              {prefs.enabled ? 'On' : 'Off'}
            </AppText>
          </View>
          <Switch
            value={prefs.enabled}
            onValueChange={onToggleMaster}
            trackColor={{ true: colors.terracotta, false: colors.hairlineStrong }}
            thumbColor={colors.white}
            ios_backgroundColor={colors.hairlineStrong}
          />
        </View>
        <View style={styles.helpRow}>
          <AppText variant="caption" color={colors.inkFaint}>
            We’ll never send marketing here — only the reminders you pick below.
          </AppText>
        </View>
      </Card>

      {needsPermission ? (
        <Card style={styles.warnCard} flat>
          <AppText variant="bodyStrong" color={colors.warning}>
            Notifications are blocked
          </AppText>
          <AppText variant="caption" color={colors.inkMuted}>
            To get reminders, allow notifications for YumYummy in your device settings.
          </AppText>
          <Button
            label="Open Settings"
            variant="secondary"
            size="md"
            onPress={() => Linking.openSettings()}
          />
        </Card>
      ) : null}

      {prefs.enabled ? (
        <>
          <AppText variant="overline" color={colors.inkMuted} style={styles.sectionLabel}>
            Meal reminders
          </AppText>
          <Card padded={false}>
            {prefs.reminders.map((r, i) => (
              <ReminderRow
                key={r.id}
                reminder={r}
                dimmed={!loaded}
                onToggle={(enabled) => onToggleReminder(r.id, enabled)}
                onTime={(h, m) => onReminderTime(r.id, h, m)}
                last={i === prefs.reminders.length - 1}
              />
            ))}
          </Card>
          <AppText variant="caption" color={colors.inkFaint} style={styles.footnote}>
            Tap a time to change it. Reminders repeat every day.
          </AppText>
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: space.sm,
  },
  title: { marginTop: space.base },
  subtitle: { marginTop: space.xs, marginBottom: space.lg },
  sectionLabel: { marginTop: space.lg, marginBottom: space.sm },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    paddingHorizontal: space.base,
    paddingVertical: space.md,
    minHeight: 56,
  },
  rowBorder: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.hairline },
  helpRow: { paddingHorizontal: space.base, paddingVertical: space.md },
  warnCard: { marginTop: space.sm, gap: space.sm, borderColor: colors.warning },
  timePill: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.sm,
    paddingHorizontal: space.md,
    paddingVertical: space.xs,
  },
  footnote: { marginTop: space.sm },
});
