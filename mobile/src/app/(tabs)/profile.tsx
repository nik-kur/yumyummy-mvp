import { useState } from 'react';
import { View, StyleSheet, Pressable, TextInput, Alert, Linking } from 'react-native';
import { useRouter } from 'expo-router';
import {
  CreditCard,
  Send,
  CircleHelp,
  FileText,
  Lock,
  LogOut,
  Trash2,
  ChevronRight,
  type LucideIcon,
} from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { useAuth } from '@/state/auth';
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

export default function ProfileScreen() {
  const router = useRouter();
  const { profile, linkTelegram, signOut } = useAuth();

  const [tgOpen, setTgOpen] = useState(false);
  const [tgCode, setTgCode] = useState('');
  const [tgBusy, setTgBusy] = useState(false);
  const [tgError, setTgError] = useState<string | null>(null);

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

  const onLinkTelegram = async () => {
    setTgError(null);
    setTgBusy(true);
    try {
      await linkTelegram(tgCode);
      setTgOpen(false);
      setTgCode('');
    } catch (e) {
      setTgError(e instanceof Error ? e.message : 'Could not link');
    } finally {
      setTgBusy(false);
    }
  };

  const onRestore = () =>
    Alert.alert(
      'Restore purchases',
      'In production this asks Adapty / the App Store to restore your subscription.\n\n(Not wired in this build.)',
    );

  const onDelete = () =>
    Alert.alert(
      'Delete account',
      'This permanently deletes your account and diary across the app and the Telegram bot. This cannot be undone.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => {
            // TODO(account-deletion): call a backend DELETE /app/me endpoint to
            // erase the account + identities + diary (Apple requirement), then:
            signOut();
          },
        },
      ],
    );

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
            <AppText variant="caption" color={colors.carbs}>
              C {profile?.target_carbs_g ? Math.round(profile.target_carbs_g) : 0}g
            </AppText>
            <AppText variant="caption" color={colors.fat}>
              F {profile?.target_fat_g ? Math.round(profile.target_fat_g) : 0}g
            </AppText>
          </View>
        </View>
        <Button
          label="Adjust goals & targets"
          variant="secondary"
          size="md"
          onPress={() => router.push('/(onboarding)/goal')}
        />
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
          onPress={() => router.push('/paywall')}
        />
        <Button label="Restore purchases" variant="ghost" onPress={onRestore} haptic={false} />
      </View>

      <AppText variant="overline" color={colors.inkMuted} style={styles.sectionLabel}>
        Connections
      </AppText>
      <Card padded={false}>
        <Row
          icon={Send}
          label="Telegram bot"
          value={telegramLinked ? 'Connected' : undefined}
          onPress={telegramLinked ? undefined : () => setTgOpen((v) => !v)}
          last
        />
      </Card>
      {tgOpen && !telegramLinked ? (
        <Card style={styles.tgCard} flat>
          <AppText variant="caption" color={colors.inkMuted}>
            In the bot, tap “Link app” to get a one‑time code, then enter it here.
          </AppText>
          <TextInput
            style={styles.input}
            placeholder="Link code"
            placeholderTextColor={colors.inkFaint}
            autoCapitalize="characters"
            value={tgCode}
            onChangeText={setTgCode}
          />
          {tgError ? (
            <AppText variant="caption" color={colors.error}>
              {tgError}
            </AppText>
          ) : null}
          <Button label="Link Telegram" size="md" loading={tgBusy} onPress={onLinkTelegram} />
        </Card>
      ) : null}

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
  subActions: { gap: space.sm, marginTop: space.md },
  tgCard: { marginTop: space.sm, gap: space.md },
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
