import { Pressable, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';
import { useRouter } from 'expo-router';
import { BookOpen } from 'lucide-react-native';

import { AppText } from './AppText';
import { colors, space } from '@/theme/tokens';

/**
 * Inline "see the science" link shown next to any calculation or
 * recommendation — opens the citations screen (App Review Guideline 1.4.1:
 * citations for health information must be easy to find).
 */
export function SourcesLink({
  label = 'Based on published research — see sources',
  center,
  style,
}: {
  label?: string;
  center?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const router = useRouter();
  return (
    <Pressable
      onPress={() => router.push('/sources')}
      hitSlop={8}
      style={[styles.row, center && styles.center, style]}
    >
      <BookOpen size={14} color={colors.infoBlue} strokeWidth={1.5} />
      <AppText variant="caption" color={colors.infoBlue}>
        {label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  center: { justifyContent: 'center' },
});
