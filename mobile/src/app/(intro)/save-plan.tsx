/**
 * N2b Save-your-plan gate — Sign in with Apple, no way past it.
 *
 * Sits between the loader and the plan reveal so the account exists before the
 * paywall does. Buying first and signing in after was a standing source of
 * orphaned purchases: the receipt landed on an anonymous Adapty profile and the
 * webhook reached us with no account to attach it to.
 *
 * This is also where the onboarding draft is pushed to the server — the first
 * moment there is an account to push it to. The local draft is deliberately
 * kept afterwards: it is what fills the paywall's plan placeholders if the user
 * relaunches before subscribing.
 */
import { useCallback, useEffect, useState } from 'react';
import { View, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import * as AppleAuthentication from 'expo-apple-authentication';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useAuth } from '@/state/auth';
import { useIntro } from '@/state/introContext';
import * as api from '@/api/endpoints';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';
import { addBreadcrumb, captureException } from '@/analytics/sentry';

const REASONS = [
  { emoji: '🔒', text: 'Your plan and targets are saved to your account, not just this phone' },
  { emoji: '📱', text: 'Log from any device and pick up exactly where you left off' },
  { emoji: '🍎', text: 'Apple hides your email if you want — we never see a password' },
];

export default function SavePlanScreen() {
  const router = useRouter();
  const { signInWithProvider } = useAuth();
  const intro = useIntro();
  const [busy, setBusy] = useState(false);
  // null = still checking. Render no Apple button until we know, so the
  // non-compliant fallback never flashes where the official one is available
  // (App Review Guideline 4).
  const [appleAvailable, setAppleAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'N2b_save_plan' });
    track('signin_gate_shown');
  }, []);

  useEffect(() => {
    AppleAuthentication.isAvailableAsync()
      .then(setAppleAvailable)
      .catch(() => setAppleAvailable(false));
  }, []);

  const handleSignIn = useCallback(async () => {
    if (busy) return;
    setBusy(true);
    addBreadcrumb('auth', 'Save-plan gate Apple sign-in started');

    try {
      await signInWithProvider('apple');
      track('signin_gate_success');

      if (intro.goal_type) {
        try {
          await api.updateMe({
            goal_type: intro.goal_type,
            gender: intro.gender,
            age: intro.age,
            height_cm: intro.height_cm,
            weight_kg: intro.weight_kg,
            activity_level: intro.activity_level,
            target_calories: intro.target_calories,
            target_protein_g: intro.target_protein_g,
            target_fat_g: intro.target_fat_g,
            target_carbs_g: intro.target_carbs_g,
            onboarding_completed: true,
          });
        } catch (e) {
          // The account exists and the draft is still on disk — a failed sync
          // must not strand the user one screen short of the paywall.
          captureException(e);
        }
      }

      track('onboarding_screen_completed', { screen: 'N2b_save_plan' });
      router.replace('/(intro)/plan-reveal');
    } catch (e) {
      captureException(e);
      track('signin_gate_failed', {
        error: e instanceof Error ? e.message : String(e),
      });
      Alert.alert('Sign in failed', 'Please try again.');
    } finally {
      setBusy(false);
    }
  }, [busy, signInWithProvider, intro, router]);

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.center}>
        <AppText variant="overline" color={colors.terracottaText}>
          ONE LAST STEP
        </AppText>
        <AppText variant="h1" center style={s.title}>
          Save your plan
        </AppText>
        <AppText variant="body" color={colors.inkMuted} center style={s.sub}>
          We just built your personal plan. Sign in to keep it — so it’s still
          here tomorrow, and on every device you use.
        </AppText>

        <View style={s.reasons}>
          {REASONS.map((row) => (
            <View key={row.emoji} style={s.reasonRow}>
              <AppText style={s.reasonEmoji}>{row.emoji}</AppText>
              <AppText variant="small" color={colors.ink} style={s.reasonText}>
                {row.text}
              </AppText>
            </View>
          ))}
        </View>
      </View>

      <View style={s.bottom}>
        {/* Official Sign in with Apple button — HIG-required artwork with the
            Apple logo (App Review Guideline 4). The plain-button fallback only
            exists for environments without the native module (Expo Go). */}
        {busy ? (
          <View style={s.busyBox}>
            <ActivityIndicator color={colors.ink} />
          </View>
        ) : appleAvailable === null ? (
          <View style={s.busyBox} />
        ) : appleAvailable ? (
          <AppleAuthentication.AppleAuthenticationButton
            buttonType={AppleAuthentication.AppleAuthenticationButtonType.SIGN_IN}
            buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.BLACK}
            cornerRadius={radius.md}
            style={s.appleButton}
            onPress={handleSignIn}
          />
        ) : (
          <Button label="Sign in with Apple" variant="primary" onPress={handleSignIn} />
        )}
        <AppText variant="caption" color={colors.inkFaint} center>
          No password. Nothing shared with anyone.
        </AppText>
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: space.sm },
  title: { marginTop: space.sm },
  sub: { marginTop: space.md },
  reasons: {
    alignSelf: 'stretch',
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.base,
    gap: space.md,
    marginTop: space.xl,
  },
  reasonRow: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  reasonEmoji: { fontSize: 20, lineHeight: 26 },
  reasonText: { flex: 1 },
  bottom: { paddingBottom: space.lg, gap: space.md },
  appleButton: { alignSelf: 'stretch', height: 54 },
  busyBox: { height: 54, alignItems: 'center', justifyContent: 'center' },
});
