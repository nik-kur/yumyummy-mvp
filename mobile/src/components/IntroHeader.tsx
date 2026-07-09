/**
 * Intro flow top bar — back button + thin progress bar (prototype v3 topbar).
 *
 * `step` is the 1-based position of the screen in the 13-touchpoint chain
 * (welcome=0 … plan-reveal=12); progress fills proportionally.
 */
import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { ChevronLeft } from 'lucide-react-native';

import { colors, radius, space } from '@/theme/tokens';

/** Index of the last touchpoint (plan-reveal) in the intro chain. */
const LAST_STEP = 12;

export function IntroHeader({ step }: { step: number }) {
  const router = useRouter();
  const pct = Math.min(100, Math.round((step / LAST_STEP) * 100));

  return (
    <View style={s.row}>
      <Pressable
        onPress={() => router.back()}
        hitSlop={10}
        style={s.back}
        accessibilityLabel="Go back"
      >
        <ChevronLeft size={18} color={colors.ink} strokeWidth={1.5} />
      </Pressable>
      <View style={s.track}>
        <View style={[s.fill, { width: `${pct}%` }]} />
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    marginTop: space.sm,
    marginBottom: space.sm,
  },
  back: {
    width: 32,
    height: 32,
    borderRadius: radius.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.hairline,
    alignItems: 'center',
    justifyContent: 'center',
  },
  track: {
    flex: 1,
    height: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.terracottaSoft,
    overflow: 'hidden',
  },
  fill: {
    height: '100%',
    borderRadius: radius.pill,
    backgroundColor: colors.terracotta,
  },
});
