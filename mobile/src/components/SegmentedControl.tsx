import { View, Pressable, StyleSheet } from 'react-native';
import { AppText } from './AppText';
import { colors, radius, space } from '@/theme/tokens';

interface Option<T> {
  label: string;
  value: T;
}

interface SegmentedControlProps<T extends string | number> {
  options: Option<T>[];
  value: T | null;
  onChange: (value: T) => void;
}

/** Segmented control: selected segment = charcoal fill + cream text. */
export function SegmentedControl<T extends string | number>({
  options,
  value,
  onChange,
}: SegmentedControlProps<T>) {
  return (
    <View style={styles.wrap}>
      {options.map((opt) => {
        const selected = opt.value === value;
        return (
          <Pressable
            key={String(opt.value)}
            onPress={() => onChange(opt.value)}
            style={[styles.seg, selected && styles.segSelected]}
          >
            <AppText variant="bodyStrong" color={selected ? colors.bg : colors.inkMuted}>
              {opt.label}
            </AppText>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.xs,
    gap: space.xs,
  },
  seg: {
    flex: 1,
    paddingVertical: space.md,
    borderRadius: radius.sm,
    alignItems: 'center',
    justifyContent: 'center',
  },
  segSelected: { backgroundColor: colors.ink },
});
