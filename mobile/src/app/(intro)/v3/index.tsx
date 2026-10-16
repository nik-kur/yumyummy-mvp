/**
 * V3 onboarding entry. STAGE 1 STUB: shows which arm arrived; stage 2 replaces
 * it with screen 1 (Welcome A–D). Until then it hands over to the pre-V3 intro
 * so the branch stays usable end to end.
 */
import { StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Screen } from '@/components/Screen';
import { useOnboardingConfig } from '@/config/onboardingConfig';
import { colors, space } from '@/theme/tokens';

export default function V3Entry() {
  const router = useRouter();
  const { config, meta } = useOnboardingConfig();
  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.body}>
        <AppText variant="eyebrow">V3 · stage 1</AppText>
        <AppText variant="h1">Welcome {config.welcome.variant}</AppText>
        <AppText color={colors.inkMuted}>
          Arm from {meta?.source ?? '—'}
          {meta?.variation_name ? ` · ${meta.variation_name}` : ''}
          {meta?.default_reason ? ` · ${meta.default_reason}` : ''}
        </AppText>
        <AppText variant="small">
          features {config.features} · screen 16 {config.social_proof.show ? 'on' : 'off'} · plan {config.plan} · ATT on {config.att}
        </AppText>
      </View>
      <Button label="Continue (pre-V3 welcome)" variant="brand" onPress={() => router.replace('/(intro)/welcome')} />
    </Screen>
  );
}

const s = StyleSheet.create({
  body: { flex: 1, justifyContent: 'center', gap: space.sm },
});
