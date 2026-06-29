import { type ReactNode } from 'react';
import {
  ScrollView,
  View,
  StyleSheet,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView, type Edge } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';

import { colors, space } from '@/theme/tokens';

interface ScreenProps {
  children: ReactNode;
  scroll?: boolean;
  padded?: boolean;
  bg?: string;
  dark?: boolean;
  edges?: Edge[];
  contentStyle?: StyleProp<ViewStyle>;
  /** Make the scroll content fill the viewport so children can distribute / pin a footer. */
  grow?: boolean;
}

export function Screen({
  children,
  scroll = false,
  padded = true,
  bg,
  dark = false,
  edges = ['top', 'left', 'right'],
  contentStyle,
  grow = false,
}: ScreenProps) {
  const background = bg ?? (dark ? colors.darkBg : colors.bg);
  const inner: StyleProp<ViewStyle> = [padded && styles.padded, contentStyle];

  return (
    <SafeAreaView style={[styles.safe, { backgroundColor: background }]} edges={edges}>
      <StatusBar style={dark ? 'light' : 'dark'} />
      {scroll ? (
        <ScrollView
          contentContainerStyle={[styles.scrollContent, grow && styles.grow, inner]}
          showsVerticalScrollIndicator={false}
          keyboardShouldPersistTaps="handled"
        >
          {children}
        </ScrollView>
      ) : (
        <View style={[styles.flex, inner]}>{children}</View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  flex: { flex: 1 },
  grow: { flexGrow: 1 },
  padded: { paddingHorizontal: space.lg },
  scrollContent: { paddingBottom: space.xxxl },
});
