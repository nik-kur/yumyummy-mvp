/** Metric / Imperial segmented control (canvas: 2 × 108 × 36 on a paper-2 track). */
import { Pressable, StyleSheet, Text, View } from 'react-native';
import * as Haptics from 'expo-haptics';

import { C, F } from '@/onb/theme';

export type Units = 'metric' | 'imperial';

export function UnitToggle({ value, onChange }: { value: Units; onChange: (u: Units) => void }) {
  return (
    <View style={s.track}>
      {(['metric', 'imperial'] as const).map((u) => {
        const on = u === value;
        return (
          <Pressable
            key={u}
            onPress={() => {
              if (on) return;
              void Haptics.selectionAsync().catch(() => {});
              onChange(u);
            }}
            style={[s.seg, on && s.on]}
            accessibilityRole="button"
            accessibilityState={{ selected: on }}
          >
            <Text style={[s.label, on ? s.labelOn : s.labelOff]}>{u === 'metric' ? 'Metric' : 'Imperial'}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const s = StyleSheet.create({
  track: {
    alignSelf: 'center',
    flexDirection: 'row',
    padding: 3,
    backgroundColor: C.paper2,
    borderWidth: 1,
    borderColor: C.hair,
    borderRadius: 12,
  },
  seg: { width: 108, height: 36, borderRadius: 9, alignItems: 'center', justifyContent: 'center' },
  on: {
    backgroundColor: C.surface,
    shadowColor: '#2A1C0E',
    shadowOpacity: 0.14,
    shadowRadius: 1.5,
    shadowOffset: { width: 0, height: 1 },
  },
  label: { fontSize: 15 },
  labelOn: { fontFamily: F.sansSemibold, color: C.ink },
  labelOff: { fontFamily: F.sansMedium, color: C.muted },
});
