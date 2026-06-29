import { View, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Sparkles } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { colors, radius, space } from '@/theme/tokens';

export default function FirstLogScreen() {
  const router = useRouter();

  return (
    <Screen edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.wrap}>
        <View style={styles.medallion}>
          <Sparkles size={40} color={colors.terracotta} strokeWidth={1.5} />
        </View>
        <AppText variant="h1" center>
          You’re all set
        </AppText>
        <AppText variant="body" color={colors.inkMuted} center style={styles.body}>
          Logging is one sentence away. Just tell YumYummy what you ate — “two eggs and toast” — and
          we’ll handle the numbers.
        </AppText>
      </View>

      <View style={styles.actions}>
        <Button
          label="Log my first meal"
          variant="brand"
          onPress={() => {
            router.replace('/(tabs)');
            router.push('/capture');
          }}
        />
        <Button
          label="I’ll explore first"
          variant="ghost"
          onPress={() => router.replace('/(tabs)')}
          haptic={false}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  wrap: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.md },
  medallion: {
    width: 96,
    height: 96,
    borderRadius: radius.pill,
    backgroundColor: colors.terracottaSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: space.sm,
  },
  body: { maxWidth: 320, marginTop: space.xs },
  actions: { gap: space.sm, paddingBottom: space.lg },
});
