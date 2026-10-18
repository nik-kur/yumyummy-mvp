/**
 * Floating "QA" pill that opens the QA menu. Rendered by the root layout in QA
 * builds only; small and in a corner the screens leave free.
 */
import { Pressable, StyleSheet } from 'react-native';
import { router, usePathname } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { AppText } from '@/components/AppText';
import { qaOverrides } from '@/config/qa';

export function QaButton() {
  const insets = useSafeAreaInsets();
  const pathname = usePathname();
  if (pathname === '/qa' || qaOverrides().auto_tour) return null;
  return (
    <Pressable
      onPress={() => router.push('/qa')}
      style={[s.pill, { top: insets.top + 2 }]}
      hitSlop={8}
      accessibilityLabel="QA menu"
    >
      <AppText variant="caption" style={s.text}>QA</AppText>
    </Pressable>
  );
}

const s = StyleSheet.create({
  pill: {
    position: 'absolute',
    right: 6,
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 8,
    backgroundColor: 'rgba(25,21,15,0.35)',
  },
  text: { color: '#FFFFFF', fontSize: 10, lineHeight: 13 },
});
