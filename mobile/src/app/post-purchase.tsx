/**
 * Post-purchase: Sign in with Apple to save your plan.
 *
 * After a successful purchase on an anonymous Adapty profile, the user is
 * prompted to create an account. This merges the Adapty anonymous profile
 * with the identified one and syncs the onboarding draft to the backend.
 */
import { useCallback, useState } from 'react';
import { View, StyleSheet, Alert } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useAuth } from '@/state/auth';
import { loadDraft, clearDraft } from '@/state/introDraft';
import { loadJourney, saveJourney } from '@/state/journey';
import * as api from '@/api/endpoints';
import { colors, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';
import { addBreadcrumb, captureException } from '@/analytics/sentry';

export default function PostPurchaseScreen() {
  const router = useRouter();
  const { signInWithProvider, refreshProfile } = useAuth();
  const [busy, setBusy] = useState(false);

  const handleSignIn = useCallback(async () => {
    setBusy(true);
    addBreadcrumb('auth', 'Post-purchase Apple sign-in started');

    try {
      await signInWithProvider('apple');
      track('post_purchase_signin_success');

      const draft = await loadDraft();
      if (draft.goal_type) {
        await api.updateMe({
          goal_type: draft.goal_type,
          gender: draft.gender,
          age: draft.age,
          height_cm: draft.height_cm,
          weight_kg: draft.weight_kg,
          activity_level: draft.activity_level,
          target_calories: draft.target_calories,
          target_protein_g: draft.target_protein_g,
          target_fat_g: draft.target_fat_g,
          target_carbs_g: draft.target_carbs_g,
          onboarding_completed: true,
        });
        await clearDraft();
      }

      const j = await loadJourney();
      if (!j.started_at) {
        j.started_at = new Date().toISOString();
        await saveJourney(j);
      }

      await refreshProfile();
      router.replace('/notifications');
    } catch (e) {
      captureException(e);
      if (e instanceof Error && e.message.includes('canceled')) {
        // user cancelled, stay on screen
      } else {
        Alert.alert('Sign in failed', 'Please try again.');
      }
    } finally {
      setBusy(false);
    }
  }, [signInWithProvider, refreshProfile, router]);

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.center}>
        <AppText variant="overline" color={colors.terracottaText}>
          PURCHASE COMPLETE
        </AppText>
        <AppText variant="display" style={s.title}>
          Save your plan
        </AppText>
        <AppText variant="body" color={colors.inkMuted} center style={s.sub}>
          Sign in with Apple to keep your plan and subscription across devices.
          Your data stays private and secure.
        </AppText>
      </View>

      <View style={s.bottom}>
        <Button
          label={busy ? 'Signing in…' : 'Sign in with Apple'}
          variant="primary"
          loading={busy}
          onPress={handleSignIn}
        />
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', paddingHorizontal: space.lg },
  title: { marginTop: space.md, textAlign: 'center' },
  sub: { marginTop: space.md },
  bottom: { paddingBottom: space.lg, gap: space.md },
});
