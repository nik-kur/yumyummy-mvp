import { useCallback, useEffect, useRef, useState } from 'react';
import { View, StyleSheet, Pressable, TextInput, Alert, Linking, AppState } from 'react-native';
import { useRouter } from 'expo-router';
import {
  CreditCard,
  Send,
  Bell,
  CircleHelp,
  FileText,
  Lock,
  LogOut,
  Sparkles,
  Star,
  Trash2,
  ChevronRight,
  type LucideIcon,
} from 'lucide-react-native';

import { adapty } from 'react-native-adapty';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { useAuth } from '@/state/auth';
import * as api from '@/api/endpoints';
import { activateAdapty, isAdaptyConfigured, PREMIUM_ACCESS_LEVEL } from '@/billing/adapty';
import { openStoreReviewFromSettings } from '@/state/rateReview';
import { track } from '@/analytics/posthog';
import { captureException } from '@/analytics/sentry';
import { formatInt } from '@/utils/format';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';

function Row({
  icon: Icon,
  label,
  value,
  onPress,
  danger,
  last,
}: {
  icon: LucideIcon;
  label: string;
  value?: string;
  onPress?: () => void;
  danger?: boolean;
  last?: boolean;
}) {
  const tint = danger ? colors.error : colors.ink;
  return (
    <Pressable onPress={onPress} style={[styles.row, !last && styles.rowBorder]}>
      <Icon size={20} color={danger ? colors.error : colors.inkMuted} strokeWidth={1.5} />
      <AppText variant="body" color={tint} style={styles.rowLabel}>
        {label}
      </AppText>
      {value ? (
        <AppText variant="caption" color={colors.inkFaint}>
          {value}
        </AppText>
      ) : onPress ? (
        <ChevronRight size={18} color={colors.inkFaint} strokeWidth={1.5} />
      ) : null}
    </Pressable>
  );
}

// Launch decision: app-first users should NOT be nudged into the Telegram bot,
// so the "connect Telegram" entry point is hidden for accounts without a linked
// telegram identity. Bot-first users who migrated still see their "Connected"
// status. Flip to true to re-enable the app -> Telegram linking flow.
const TELEGRAM_CONNECT_ENABLED = false;

export default function ProfileScreen() {
  const router = useRouter();
  const { profile, linkTelegram, refreshProfile, signOut } = useAuth();

  const [tgOpen, setTgOpen] = useState(false);
  const [tgCode, setTgCode] = useState('');
  const [tgBusy, setTgBusy] = useState(false);
  const [tgError, setTgError] = useState<string | null>(null);
  const [tgManual, setTgManual] = useState(false);
  // Reverse-link (app -> Telegram) state.
  const [tgConnecting, setTgConnecting] = useState(false);
  const [tgIssuedCode, setTgIssuedCode] = useState<string | null>(null);
  const [tgWaiting, setTgWaiting] = useState(false);

  const billing = profile?.billing;
  const status = billing?.access_status ?? 'new';
  const telegramLinked = Boolean(profile?.telegram_id) || (profile?.linked_providers ?? []).includes('telegram');

  const statusLabel =
    status === 'active'
      ? 'Subscribed'
      : status === 'trial'
        ? `Trial · ${Math.max(0, Math.ceil(billing?.trial_days_remaining ?? 0))} days left`
        : status === 'trial_expired' || status === 'expired'
          ? 'Expired'
          : 'Free';

  const providersLabel = (profile?.linked_providers ?? []).join(' · ') || 'email';
  const initials = (profile?.telegram_id ?? 'YY').slice(0, 2).toUpperCase();

  // Reverse flow: app issues a code + deep link, opens Telegram, then polls for
  // the bot to confirm (telegram_id appears on the profile).
  const onConnectTelegram = async () => {
    setTgError(null);
    setTgConnecting(true);
    try {
      const issued = await api.issueAppTelegramLink();
      setTgIssuedCode(issued.code);
      setTgWaiting(true);
      const opened = await Linking.openURL(issued.deep_link).then(() => true).catch(() => false);
      if (!opened) {
        // Telegram not installed / couldn't open — fall back to the code.
        setTgError('Couldn’t open Telegram. Open @' + issued.bot_username + ' and send the code below.');
      }
    } catch (e) {
      setTgError(e instanceof Error ? e.message : 'Could not start linking');
      setTgWaiting(false);
    } finally {
      setTgConnecting(false);
    }
  };

  // While waiting for the bot to confirm, poll the profile. Stop once linked.
  const waitingRef = useRef(false);
  waitingRef.current = tgWaiting && !telegramLinked;
  useEffect(() => {
    if (!tgWaiting || telegramLinked) return;
    let attempts = 0;
    const tick = async () => {
      attempts += 1;
      try {
        await refreshProfile();
      } catch {
        /* keep polling */
      }
      if (attempts >= 40) setTgWaiting(false); // ~2 min then give up quietly
    };
    const interval = setInterval(() => {
      if (waitingRef.current) void tick();
    }, 3000);
    // Re-check immediately when the user switches back from Telegram.
    const sub = AppState.addEventListener('change', (s) => {
      if (s === 'active' && waitingRef.current) void tick();
    });
    return () => {
      clearInterval(interval);
      sub.remove();
    };
  }, [tgWaiting, telegramLinked, refreshProfile]);

  // Once linked, collapse the connect UI.
  useEffect(() => {
    if (telegramLinked) {
      setTgWaiting(false);
      setTgOpen(false);
    }
  }, [telegramLinked]);

  // Forward flow (fallback): user pastes a code the bot gave them.
  const onLinkTelegramManual = useCallback(async () => {
    setTgError(null);
    setTgBusy(true);
    try {
      await linkTelegram(tgCode);
      setTgOpen(false);
      setTgCode('');
      setTgManual(false);
    } catch (e) {
      setTgError(e instanceof Error ? e.message : 'Could not link');
    } finally {
      setTgBusy(false);
    }
  }, [linkTelegram, tgCode]);

  const onRestore = useCallback(async () => {
    if (!isAdaptyConfigured()) {
      Alert.alert('Restore purchases', 'Purchases can be restored from a TestFlight or App Store build.');
      return;
    }
    track('profile_restore_started');
    try {
      await activateAdapty();
      const adaptyProfile = await adapty.restorePurchases();
      const active = Boolean(adaptyProfile.accessLevels?.[PREMIUM_ACCESS_LEVEL]?.isActive);
      if (active) await refreshProfile();
      track(active ? 'profile_restore_success' : 'profile_restore_empty');
      Alert.alert(
        'Restore purchases',
        active
          ? 'Your subscription has been restored.'
          : 'No active subscription was found for your Apple ID.',
      );
    } catch (e) {
      track('profile_restore_failed', { error: e instanceof Error ? e.message : String(e) });
      captureException(e);
      Alert.alert('Restore purchases', 'Couldn’t restore purchases. Please try again.');
    }
  }, [refreshProfile]);

  const onDelete = useCallback(() => {
    Alert.alert(
      'Delete account',
      'This permanently deletes your account and diary across the app and the Telegram bot. This cannot be undone.\n\nAn active App Store subscription is managed by Apple — cancel it in Settings › Apple Account › Subscriptions.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.deleteAccount();
            } catch {
              Alert.alert('Delete account', 'Couldn’t delete your account. Please try again.');
              return;
            }
            await signOut();
          },
        },
      ],
    );
  }, [signOut]);

  return (
    <Screen scroll>
      <View style={styles.header}>
        <View style={styles.avatar}>
          <AppText style={styles.avatarText}>{initials}</AppText>
        </View>
        <View style={styles.headerText}>
          <AppText variant="h2">Your account</AppText>
          <AppText variant="caption" color={colors.inkMuted}>
            {providersLabel}
            {profile?.account_id ? ` · #${profile.account_id}` : ''}
          </AppText>
        </View>
      </View>

      <AppText variant="overline" color={colors.inkMuted} style={styles.sectionLabel}>
        Daily targets
      </AppText>
      <Card style={styles.targetsCard}>
        <View style={styles.targetsTop}>
          <View>
            <AppText variant="h1" color={colors.terracotta}>
              {profile?.target_calories ? formatInt(profile.target_calories) : '—'}
            </AppText>
            <AppText variant="overline" color={colors.inkMuted}>
              kcal / day
            </AppText>
          </View>
          <View style={styles.targetMacros}>
            <AppText variant="caption" color={colors.protein}>
              P {profile?.target_protein_g ? Math.round(profile.target_protein_g) : 0}g
            </AppText>
            <AppText variant="caption" color={colors.fat}>
              F {profile?.target_fat_g ? Math.round(profile.target_fat_g) : 0}g
            </AppText>
            <AppText variant="caption" color={colors.carbs}>
              C {profile?.target_carbs_g ? Math.round(profile.target_carbs_g) : 0}g
            </AppText>
          </View>
        </View>
        <View style={styles.targetActions}>
          <Button
            label="Recalculate from questionnaire"
            variant="secondary"
            size="md"
            onPress={() => router.push('/(onboarding)/goal')}
          />
          <Button
            label="Enter targets manually"
            variant="ghost"
            size="md"
            haptic={false}
            onPress={() => router.push('/edit-targets')}
          />
        </View>
      </Card>

      <AppText variant="overline" color={colors.inkMuted} style={styles.sectionLabel}>
        Subscription
      </AppText>
      <Card padded={false}>
        <Row icon={CreditCard} label="Plan" value={statusLabel} last />
      </Card>
      <View style={styles.subActions}>
        <Button
          label={status === 'active' ? 'Manage plan' : 'See plans'}
          // Dismissable: unlike the onboarding gate, a member browsing plans
          // must always be able to close the paywall and come back here.
          onPress={() => router.push({ pathname: '/paywall', params: { dismissable: '1' } })}
        />
        <Button label="Restore purchases" variant="ghost" onPress={onRestore} haptic={false} />
      </View>

      {telegramLinked || TELEGRAM_CONNECT_ENABLED ? (
        <>
          <AppText variant="overline" color={colors.inkMuted} style={styles.sectionLabel}>
            Connections
          </AppText>
          <Card padded={false}>
            <Row
              icon={Send}
              label="Telegram bot"
              value={telegramLinked ? 'Connected' : undefined}
              onPress={telegramLinked || !TELEGRAM_CONNECT_ENABLED ? undefined : () => setTgOpen((v) => !v)}
              last
            />
          </Card>
        </>
      ) : null}
      {TELEGRAM_CONNECT_ENABLED && tgOpen && !telegramLinked ? (
        <Card style={styles.tgCard} flat>
          <AppText variant="body" color={colors.ink}>
            Connect the Telegram bot to log from both places — your diary and
            targets stay in sync everywhere.
          </AppText>
          <Button
            label={tgWaiting ? 'Reopen Telegram' : 'Open Telegram to connect'}
            size="md"
            loading={tgConnecting}
            onPress={onConnectTelegram}
          />
          {tgWaiting ? (
            <View style={styles.tgWaiting}>
              <AppText variant="caption" color={colors.inkMuted}>
                Finish in Telegram, then come back — this updates automatically.
              </AppText>
              {tgIssuedCode ? (
                <AppText variant="caption" color={colors.inkFaint}>
                  Code: <AppText variant="caption" color={colors.ink}>{tgIssuedCode}</AppText>
                </AppText>
              ) : null}
            </View>
          ) : null}
          {tgError ? (
            <AppText variant="caption" color={colors.error}>
              {tgError}
            </AppText>
          ) : null}

          <Pressable onPress={() => setTgManual((v) => !v)} hitSlop={8}>
            <AppText variant="caption" color={colors.infoBlue}>
              {tgManual ? 'Hide' : 'Already have a code from the bot?'}
            </AppText>
          </Pressable>
          {tgManual ? (
            <>
              <TextInput
                style={styles.input}
                placeholder="Link code"
                placeholderTextColor={colors.inkFaint}
                autoCapitalize="characters"
                value={tgCode}
                onChangeText={setTgCode}
              />
              <Button label="Link with code" size="md" loading={tgBusy} onPress={onLinkTelegramManual} />
            </>
          ) : null}
        </Card>
      ) : null}

      <AppText variant="overline" color={colors.inkMuted} style={styles.sectionLabel}>
        Preferences
      </AppText>
      <Card padded={false}>
        <Row icon={Bell} label="Notifications" onPress={() => router.push('/notifications')} />
        <Row icon={Star} label="Rate YumYummy" onPress={() => void openStoreReviewFromSettings()} last />
      </Card>

      <AppText variant="overline" color={colors.inkMuted} style={styles.sectionLabel}>
        Support
      </AppText>
      <Card padded={false}>
        <Row
          icon={CircleHelp}
          label="Help & contact"
          onPress={() => Linking.openURL('https://t.me/yumyummy_support')}
        />
        <Row
          icon={FileText}
          label="Terms of Service"
          onPress={() => Linking.openURL('https://yumyummy.ai/terms.html')}
        />
        <Row
          icon={Lock}
          label="Privacy Policy"
          onPress={() => Linking.openURL('https://yumyummy.ai/privacy.html')}
        />
        <Row
          icon={Sparkles}
          label="AI data processing"
          onPress={() => Linking.openURL('https://yumyummy.ai/privacy.html#ai-processing')}
          last
        />
      </Card>

      <AppText variant="overline" color={colors.inkMuted} style={styles.sectionLabel}>
        Account
      </AppText>
      <Card padded={false}>
        <Row icon={LogOut} label="Sign out" onPress={signOut} />
        <Row icon={Trash2} label="Delete account" onPress={onDelete} danger last />
      </Card>

      <AppText variant="caption" color={colors.inkFaint} center style={styles.version}>
        YumYummy · v1.0.0
      </AppText>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: space.base, marginTop: space.sm, marginBottom: space.lg },
  avatar: {
    width: 56,
    height: 56,
    borderRadius: radius.pill,
    backgroundColor: colors.terracotta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: { fontFamily: fonts.serifBold, fontSize: 22, color: colors.white },
  headerText: { flex: 1, gap: 2 },
  sectionLabel: { marginTop: space.lg, marginBottom: space.sm },
  targetsCard: { gap: space.base },
  targetsTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  targetMacros: { alignItems: 'flex-end', gap: 4 },
  targetActions: { gap: space.xs },
  subActions: { gap: space.sm, marginTop: space.md },
  tgCard: { marginTop: space.sm, gap: space.md },
  tgWaiting: { gap: space.xs },
  input: {
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.md,
    paddingHorizontal: space.base,
    minHeight: 48,
    fontFamily: fonts.sans,
    fontSize: 16,
    color: colors.ink,
  },
  row: { flexDirection: 'row', alignItems: 'center', gap: space.md, paddingHorizontal: space.base, paddingVertical: space.base },
  rowBorder: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.hairline },
  rowLabel: { flex: 1 },
  version: { marginTop: space.xl },
});
