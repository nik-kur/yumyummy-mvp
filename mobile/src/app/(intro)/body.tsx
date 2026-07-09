/**
 * S6 Height + Weight — two numeric steppers on one screen.
 */
import { useState } from 'react';
import { View, StyleSheet, Pressable } from 'react-native';
import { useRouter } from 'expo-router';
import { Minus, Plus } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { useIntro } from '@/state/introContext';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

function Stepper({
  label,
  unit,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  unit: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <View style={s.stepperRow}>
      <AppText variant="bodyStrong">{label}</AppText>
      <View style={s.stepperControls}>
        <Pressable
          onPress={() => onChange(Math.max(min, value - step))}
          style={s.btn}
          hitSlop={12}
        >
          <Minus size={20} color={colors.ink} strokeWidth={1.5} />
        </Pressable>
        <View style={s.valBox}>
          <AppText variant="h1">{value}</AppText>
          <AppText variant="caption" color={colors.inkMuted}>{unit}</AppText>
        </View>
        <Pressable
          onPress={() => onChange(Math.min(max, value + step))}
          style={s.btn}
          hitSlop={12}
        >
          <Plus size={20} color={colors.ink} strokeWidth={1.5} />
        </Pressable>
      </View>
    </View>
  );
}

export default function BodyScreen() {
  const router = useRouter();
  const intro = useIntro();
  const [height, setHeight] = useState(intro.height_cm);
  const [weight, setWeight] = useState(intro.weight_kg);

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.header}>
        <AppText variant="overline" color={colors.inkMuted}>Step 5 of 8</AppText>
        <AppText variant="h1" style={s.title}>Your measurements</AppText>
        <AppText variant="body" color={colors.inkMuted}>
          Used to calculate your calorie target. We never share this data.
        </AppText>
      </View>

      <View style={s.steppers}>
        <Stepper label="Height" unit="cm" value={height} min={120} max={230} step={1} onChange={setHeight} />
        <Stepper label="Weight" unit="kg" value={weight} min={30} max={250} step={1} onChange={setWeight} />
      </View>

      <Button
        label="Continue"
        onPress={() => {
          intro.set({ height_cm: height, weight_kg: weight });
          track('onboarding_screen_completed', { screen: 'S6_body' });
          router.push('/(intro)/activity');
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.xl, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  steppers: { flex: 1, justifyContent: 'center', gap: space.xxl },
  stepperRow: { alignItems: 'center', gap: space.md },
  stepperControls: { flexDirection: 'row', alignItems: 'center', gap: space.xl },
  btn: {
    width: 44, height: 44, borderRadius: radius.pill,
    backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.hairline,
    alignItems: 'center', justifyContent: 'center',
  },
  valBox: { alignItems: 'center', minWidth: 80 },
  cta: { marginTop: 'auto' },
});
