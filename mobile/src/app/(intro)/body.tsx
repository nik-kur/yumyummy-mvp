/**
 * S6 Height + Weight — smooth wheel pickers (Cal AI / Bitepal style) with a
 * metric/imperial toggle. Canonical values are always stored in cm/kg; the
 * imperial wheels just convert on the way in and out.
 */
import { useEffect, useMemo, useState } from 'react';
import { View, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { IntroHeader } from '@/components/IntroHeader';
import { SegmentedControl } from '@/components/SegmentedControl';
import { WheelPicker } from '@/components/WheelPicker';
import { useIntro } from '@/state/introContext';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

type Unit = 'metric' | 'imperial';

function range(start: number, end: number): number[] {
  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}

// Canonical bounds in cm/kg, mirrored to imperial wheels.
const HEIGHT_CM = range(120, 230);
const WEIGHT_KG = range(30, 250);
const HEIGHT_IN = range(48, 90); // 4'0" – 7'6"
const WEIGHT_LB = range(66, 551); // ~30 – 250 kg

const cmToIn = (cm: number) => Math.round(cm / 2.54);
const inToCm = (inch: number) => Math.round(inch * 2.54);
const kgToLb = (kg: number) => Math.round(kg * 2.2046);
const lbToKg = (lb: number) => Math.round(lb / 2.2046);
const fmtFtIn = (inch: number) => `${Math.floor(inch / 12)}'${inch % 12}"`;
const fmtLb = (lb: number) => `${lb} lb`;
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

export default function BodyScreen() {
  const router = useRouter();
  const intro = useIntro();
  const [unit, setUnit] = useState<Unit>('metric');
  const [heightCm, setHeightCm] = useState(clamp(intro.height_cm, 120, 230));
  const [weightKg, setWeightKg] = useState(clamp(intro.weight_kg, 30, 250));

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: 'S6_body' });
  }, []);

  const heightIn = useMemo(() => clamp(cmToIn(heightCm), 48, 90), [heightCm]);
  const weightLb = useMemo(() => clamp(kgToLb(weightKg), 66, 551), [weightKg]);

  return (
    <Screen grow edges={['top', 'bottom', 'left', 'right']}>
      <IntroHeader step={5} />

      <View style={s.header}>
        <AppText variant="overline" color={colors.terracottaText}>Your metabolism</AppText>
        <AppText variant="h1" style={s.title}>Your height and weight</AppText>
        <AppText variant="body" color={colors.inkMuted}>
          Used to calculate your calorie target. We never share this data.
        </AppText>
      </View>

      <View style={s.toggle}>
        <SegmentedControl<Unit>
          options={[
            { label: 'Metric', value: 'metric' },
            { label: 'Imperial', value: 'imperial' },
          ]}
          value={unit}
          onChange={setUnit}
        />
      </View>

      <View style={s.wheels}>
        <View style={s.wheelCol}>
          <AppText variant="overline" color={colors.inkMuted} center>
            Height
          </AppText>
          {unit === 'metric' ? (
            <WheelPicker
              key="h-metric"
              values={HEIGHT_CM}
              value={heightCm}
              suffix="cm"
              onChange={setHeightCm}
            />
          ) : (
            <WheelPicker
              key="h-imperial"
              values={HEIGHT_IN}
              value={heightIn}
              format={fmtFtIn}
              onChange={(v) => setHeightCm(clamp(inToCm(v), 120, 230))}
            />
          )}
        </View>
        <View style={s.wheelCol}>
          <AppText variant="overline" color={colors.inkMuted} center>
            Weight
          </AppText>
          {unit === 'metric' ? (
            <WheelPicker
              key="w-metric"
              values={WEIGHT_KG}
              value={weightKg}
              suffix="kg"
              onChange={setWeightKg}
            />
          ) : (
            <WheelPicker
              key="w-imperial"
              values={WEIGHT_LB}
              value={weightLb}
              format={fmtLb}
              onChange={(v) => setWeightKg(clamp(lbToKg(v), 30, 250))}
            />
          )}
        </View>
      </View>

      <Button
        label="Continue"
        variant="brand"
        onPress={() => {
          intro.set({ height_cm: heightCm, weight_kg: weightKg });
          track('onboarding_screen_completed', { screen: 'S6_body' });
          router.push('/(intro)/activity');
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.md, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  toggle: { marginBottom: space.lg },
  wheels: { flex: 1, flexDirection: 'row', justifyContent: 'center', gap: space.xl },
  wheelCol: { flex: 1, gap: space.sm, justifyContent: 'center' },
  cta: { marginTop: 'auto' },
});
