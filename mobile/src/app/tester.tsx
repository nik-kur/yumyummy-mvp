/**
 * `yumyummy://tester?code=<code>` — marks this install as a tester in Adapty
 * (see `config/testerMark.ts`). Not linked from anywhere in the app.
 */
import { useEffect, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Screen } from '@/components/Screen';
import { applyTesterCode, sanitizeTesterCode, type TesterResult } from '@/config/testerMark';
import { useAuth } from '@/state/auth';
import { clearDraft } from '@/state/introDraft';
import { colors, space } from '@/theme/tokens';

export default function TesterScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ code?: string }>();
  const { status } = useAuth();
  const code = sanitizeTesterCode(params.code);
  const [result, setResult] = useState<TesterResult | 'invalid' | null>(code ? null : 'invalid');

  useEffect(() => {
    if (!code) return;
    let alive = true;
    void applyTesterCode(code).then((r) => {
      if (alive) setResult(r);
    });
    return () => {
      alive = false;
    };
  }, [code]);

  const startOver = async () => {
    // The onboarding re-reads its config from Adapty, now as a tester.
    await clearDraft();
    router.replace('/');
  };

  const title =
    result === 'marked' ? 'Tester mode is on'
      : result === 'cleared' ? 'Tester mode is off'
        : result === 'failed' ? 'Couldn’t reach the server'
          : result === 'invalid' ? 'This link isn’t valid'
            : 'One moment…';

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.body}>
        {result === null ? <ActivityIndicator color={colors.terracotta} /> : null}
        <AppText variant="h1" center>{title}</AppText>
        {result === 'marked' || result === 'cleared' ? (
          <AppText color={colors.inkMuted} center>
            {status === 'signedIn'
              ? 'Sign out in Profile, then the onboarding starts with the variant set up for this phone.'
              : 'Start the onboarding again to see the variant set up for this phone.'}
          </AppText>
        ) : null}
      </View>
      <View style={s.bottom}>
        {result === 'failed' && code ? (
          <Button
            label="Try again"
            variant="brand"
            onPress={() => {
              setResult(null);
              void applyTesterCode(code).then(setResult);
            }}
          />
        ) : null}
        {result !== null ? (
          <Button
            label={result === 'marked' || result === 'cleared' ? 'Start over' : 'Close'}
            variant={result === 'marked' || result === 'cleared' ? 'brand' : 'secondary'}
            onPress={() => void (result === 'marked' || result === 'cleared' ? startOver() : router.replace('/'))}
          />
        ) : null}
      </View>
    </Screen>
  );
}

const s = StyleSheet.create({
  body: { flex: 1, justifyContent: 'center', gap: space.md },
  bottom: { gap: space.md, paddingBottom: space.lg },
});
