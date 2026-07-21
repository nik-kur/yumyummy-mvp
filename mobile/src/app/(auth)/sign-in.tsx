import { useEffect, useState } from 'react';
import { View, TextInput, StyleSheet, Pressable, Linking } from 'react-native';
import { useRouter } from 'expo-router';
import { Send } from 'lucide-react-native';
import * as AppleAuthentication from 'expo-apple-authentication';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useAuth } from '@/state/auth';
import * as api from '@/api/endpoints';
import { DEFAULT_TARGETS } from '@/api/mock';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';

export default function SignInScreen() {
  const router = useRouter();
  const auth = useAuth();

  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [emailSent, setEmailSent] = useState(false);
  const [tgVisible, setTgVisible] = useState(false);
  const [tgCode, setTgCode] = useState('');
  const [hint, setHint] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // null = unknown (still checking). Render no Apple button at all until we
  // know, so a non-compliant fallback never flashes on devices where the
  // official button is available (App Review Guideline 4).
  const [appleAvailable, setAppleAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    AppleAuthentication.isAvailableAsync()
      .then(setAppleAvailable)
      .catch(() => setAppleAvailable(false));
  }, []);

  const run = async (fn: () => Promise<void>) => {
    setError(null);
    setBusy(true);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
    } finally {
      setBusy(false);
    }
  };

  const goHome = () => router.replace('/');

  const onSendCode = () =>
    run(async () => {
      if (!email.includes('@')) throw new Error('Enter a valid email address');
      const debug = await auth.requestEmailCode(email);
      setEmailSent(true);
      if (debug) {
        setCode(debug);
        setHint(`Dev code: ${debug}`);
      }
    });

  const onSkipDemo = () =>
    run(async () => {
      await auth.signInWithDemoEmail();
      await api.updateMe({
        onboarding_completed: true,
        goal_type: 'maintain',
        target_calories: DEFAULT_TARGETS.calories,
        target_protein_g: DEFAULT_TARGETS.protein,
        target_fat_g: DEFAULT_TARGETS.fat,
        target_carbs_g: DEFAULT_TARGETS.carbs,
      });
      await auth.refreshProfile();
      goHome();
    });

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.brandBlock}>
        <AppText variant="overline" color={colors.inkMuted}>
          AI nutrition, your way
        </AppText>
        <AppText variant="display" style={styles.wordmark}>
          <AppText variant="display" color={colors.terracotta}>
            Y
          </AppText>
          umYummy
        </AppText>
        <AppText variant="body" color={colors.inkMuted} style={styles.tagline}>
          Log food by text, voice or photo. Real, source‑checked numbers — no streaks, no shame.
        </AppText>
      </View>

      <View style={styles.section}>
        {/* Official Sign in with Apple button (HIG-compliant artwork — App Review
            Guideline 4). Falls back to a plain button where the native module is
            unavailable (Expo Go / Android). */}
        {appleAvailable === null ? (
          <View style={styles.appleButton} />
        ) : appleAvailable ? (
          <AppleAuthentication.AppleAuthenticationButton
            buttonType={AppleAuthentication.AppleAuthenticationButtonType.CONTINUE}
            buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.BLACK}
            cornerRadius={radius.md}
            style={styles.appleButton}
            onPress={() => run(async () => { await auth.signInWithProvider('apple'); goHome(); })}
          />
        ) : (
          <Button
            label="Continue with Apple"
            variant="dark"
            onPress={() => run(async () => { await auth.signInWithProvider('apple'); goHome(); })}
          />
        )}
        {/* Google sign-in ships in a later build (native @react-native-google-signin
            + OAuth client). Hidden until then so we don't present a dead control. */}
      </View>

      <View style={styles.dividerRow}>
        <View style={styles.line} />
        <AppText variant="caption" color={colors.inkFaint}>
          or
        </AppText>
        <View style={styles.line} />
      </View>

      <View style={styles.section}>
        <TextInput
          style={styles.input}
          placeholder="you@email.com"
          placeholderTextColor={colors.inkFaint}
          autoCapitalize="none"
          keyboardType="email-address"
          value={email}
          editable={!emailSent}
          onChangeText={setEmail}
        />
        {emailSent ? (
          <>
            <TextInput
              style={styles.input}
              placeholder="6‑digit code"
              placeholderTextColor={colors.inkFaint}
              keyboardType="number-pad"
              value={code}
              onChangeText={setCode}
            />
            {hint ? (
              <AppText variant="caption" color={colors.infoBlue}>
                {hint}
              </AppText>
            ) : null}
            <Button
              label="Verify & continue"
              loading={busy}
              onPress={() => run(async () => { await auth.signInWithEmail(email, code); goHome(); })}
            />
            <Pressable onPress={() => setEmailSent(false)}>
              <AppText variant="caption" color={colors.inkMuted} center>
                Use a different email
              </AppText>
            </Pressable>
          </>
        ) : (
          <Button label="Email me a code" variant="secondary" loading={busy} onPress={onSendCode} />
        )}
      </View>

      <Pressable style={styles.tgToggle} onPress={() => setTgVisible((v) => !v)}>
        <Send size={16} color={colors.infoBlue} strokeWidth={1.5} />
        <AppText variant="bodyStrong" color={colors.infoBlue}>
          Already use our Telegram bot?
        </AppText>
      </Pressable>

      {tgVisible ? (
        <View style={styles.section}>
          <AppText variant="caption" color={colors.inkMuted}>
            In the bot, tap “Link app” to get a one‑time code, then enter it here. Your diary, My
            Menu and subscription stay in sync.
          </AppText>
          <TextInput
            style={styles.input}
            placeholder="Link code"
            placeholderTextColor={colors.inkFaint}
            autoCapitalize="characters"
            value={tgCode}
            onChangeText={setTgCode}
          />
          <Button
            label="Continue from Telegram"
            loading={busy}
            onPress={() => run(async () => { await auth.signInFromTelegram(tgCode); goHome(); })}
          />
        </View>
      ) : null}

      {error ? (
        <AppText variant="caption" color={colors.error} center style={styles.error}>
          {error}
        </AppText>
      ) : null}

      <View style={styles.footer}>
        <Pressable onPress={() => Linking.openURL('https://yumyummy.ai/terms.html')}>
          <AppText variant="caption" color={colors.inkFaint}>
            Terms
          </AppText>
        </Pressable>
        <AppText variant="caption" color={colors.inkFaint}>
          ·
        </AppText>
        <Pressable onPress={() => Linking.openURL('https://yumyummy.ai/privacy.html')}>
          <AppText variant="caption" color={colors.inkFaint}>
            Privacy
          </AppText>
        </Pressable>
      </View>

      {/* Dev-only shortcut: relies on the backend returning the login code,
          which is disabled in production. Hidden from release/TestFlight builds
          (reviewers sign in with Apple). */}
      {__DEV__ ? (
        <Pressable style={styles.demo} onPress={onSkipDemo}>
          <AppText variant="caption" color={colors.inkFaint} center>
            Demo: skip sign‑in →
          </AppText>
        </Pressable>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  brandBlock: { marginTop: space.xxl, marginBottom: space.xl, gap: space.xs },
  wordmark: { marginTop: space.xs },
  tagline: { marginTop: space.sm, maxWidth: 320 },
  section: { gap: space.md, marginBottom: space.lg },
  appleButton: { alignSelf: 'stretch', height: 54 },
  dividerRow: { flexDirection: 'row', alignItems: 'center', gap: space.md, marginBottom: space.lg },
  line: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.hairline },
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.md,
    paddingHorizontal: space.base,
    minHeight: 52,
    fontFamily: fonts.sans,
    fontSize: 16,
    color: colors.ink,
  },
  tgToggle: { flexDirection: 'row', alignItems: 'center', gap: space.sm, justifyContent: 'center', paddingVertical: space.sm, marginBottom: space.sm },
  error: { marginBottom: space.md },
  footer: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: space.sm, marginTop: 'auto', paddingTop: space.xl },
  demo: { marginTop: space.xl, paddingVertical: space.sm },
});
