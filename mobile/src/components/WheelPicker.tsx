import { useCallback } from 'react';
import {
  FlatList,
  View,
  StyleSheet,
  type ListRenderItemInfo,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
} from 'react-native';

import { AppText } from './AppText';
import { colors, radius, space } from '@/theme/tokens';

interface WheelPickerProps {
  values: number[];
  value: number;
  onChange: (value: number) => void;
  itemHeight?: number;
  visibleCount?: number; // should be odd
  suffix?: string;
}

/** Lightweight snapping wheel picker (no native deps; runs in Expo Go). */
export function WheelPicker({
  values,
  value,
  onChange,
  itemHeight = 44,
  visibleCount = 5,
  suffix,
}: WheelPickerProps) {
  const pad = Math.floor(visibleCount / 2);
  const height = itemHeight * visibleCount;
  const initialIndex = Math.max(0, values.indexOf(value));

  const handleMomentumEnd = useCallback(
    (e: NativeSyntheticEvent<NativeScrollEvent>) => {
      const idx = Math.round(e.nativeEvent.contentOffset.y / itemHeight);
      const clamped = Math.max(0, Math.min(values.length - 1, idx));
      const next = values[clamped];
      if (next !== undefined && next !== value) onChange(next);
    },
    [itemHeight, values, value, onChange],
  );

  const renderItem = useCallback(
    ({ item }: ListRenderItemInfo<number>) => {
      const selected = item === value;
      return (
        <View style={[styles.item, { height: itemHeight }]}>
          <AppText
            variant={selected ? 'h2' : 'title'}
            color={selected ? colors.ink : colors.inkFaint}
          >
            {item}
            {suffix ? ` ${suffix}` : ''}
          </AppText>
        </View>
      );
    },
    [itemHeight, value, suffix],
  );

  return (
    <View style={{ height }}>
      <View
        pointerEvents="none"
        style={[styles.band, { top: pad * itemHeight, height: itemHeight }]}
      />
      <FlatList
        data={values}
        keyExtractor={(v) => String(v)}
        renderItem={renderItem}
        getItemLayout={(_, i) => ({ length: itemHeight, offset: itemHeight * i, index: i })}
        initialScrollIndex={initialIndex}
        snapToInterval={itemHeight}
        decelerationRate="fast"
        showsVerticalScrollIndicator={false}
        contentContainerStyle={{ paddingVertical: pad * itemHeight }}
        onMomentumScrollEnd={handleMomentumEnd}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  item: { alignItems: 'center', justifyContent: 'center' },
  band: {
    position: 'absolute',
    left: 0,
    right: 0,
    borderRadius: radius.sm,
    backgroundColor: colors.terracottaSoft,
    opacity: 0.5,
  },
});
