/**
 * V3 screen 5c — Height and weight on two wheels, Metric / Imperial.
 * Imperial is feet + inches and stones + pounds (UK). The draft always stores
 * centimetres and kilograms; `units` remembers the choice for later screens.
 */
import { useCallback, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { OnbButton } from '@/components/onb/OnbButton';
import { OnbLayout } from '@/components/onb/OnbLayout';
import { UnitToggle, type Units } from '@/components/onb/UnitToggle';
import { ROW, Wheel, WheelBand, type WheelLabel } from '@/components/onb/Wheel';
import { LB_PER_KG } from '@/onb/plan';
import { C, F } from '@/onb/theme';
import { useOnbScreen } from '@/onb/useOnbScreen';

const CM = Array.from({ length: 111 }, (_, i) => 120 + i); // 120–230
const KG = Array.from({ length: 221 }, (_, i) => 30 + i); // 30–250
const INCH = Array.from({ length: 43 }, (_, i) => 48 + i); // 4′0″–7′6″
const LB = Array.from({ length: 485 }, (_, i) => 66 + i); // 4 st 10 – 39 st 4

const LABEL_H = 30;

export default function BodyScreen() {
  const { intro, next, progress } = useOnbScreen('S5_body');
  const [units, setUnits] = useState<Units>(intro.units ?? 'metric');
  const [cm, setCm] = useState(intro.height_cm || 170);
  const [kg, setKg] = useState(intro.weight_kg || 70);

  const cmLabel = useCallback((v: number): WheelLabel => [{ text: String(v) }, { text: 'cm', unit: true }], []);
  const kgLabel = useCallback((v: number): WheelLabel => [{ text: String(v) }, { text: 'kg', unit: true }], []);
  const inLabel = useCallback(
    (v: number): WheelLabel => [
      { text: String(Math.floor(v / 12)) },
      { text: 'ft', unit: true },
      { text: String(v % 12) },
      { text: 'in', unit: true },
    ],
    [],
  );
  const lbLabel = useCallback(
    (v: number): WheelLabel => [
      { text: String(Math.floor(v / 14)) },
      { text: 'st', unit: true },
      { text: String(v % 14) },
      { text: 'lb', unit: true },
    ],
    [],
  );

  const inches = Math.round(cm / 2.54);
  const pounds = Math.round(kg * LB_PER_KG);

  return (
    <OnbLayout
      progress={progress}
      title="Your height and weight"
      sub="This sets your starting point."
      footer={
        <OnbButton
          label="Continue"
          onPress={() => next({ height_cm: cm, weight_kg: kg, units }, { units }, { onb_units: units })}
        />
      }
    >
      <View style={s.toggle}>
        <UnitToggle value={units} onChange={setUnits} />
      </View>
      <View style={{ flex: 1 }} />
      <View>
        <WheelBand top={LABEL_H + 2 * ROW} />
        <View style={s.cols} key={units}>
          <View style={s.col}>
            <Text style={s.colLabel}>Height</Text>
            {units === 'metric' ? (
              <Wheel values={CM} value={Math.min(230, Math.max(120, Math.round(cm)))} onChange={setCm} half={2} label={cmLabel} bigSize={30} band={false} />
            ) : (
              <Wheel
                values={INCH}
                value={Math.min(90, Math.max(48, inches))}
                onChange={(v) => setCm(Math.round(v * 2.54))}
                half={2}
                label={inLabel}
                bigSize={30}
                band={false}
              />
            )}
          </View>
          <View style={s.col}>
            <Text style={s.colLabel}>Weight</Text>
            {units === 'metric' ? (
              <Wheel values={KG} value={Math.min(250, Math.max(30, Math.round(kg)))} onChange={setKg} half={2} label={kgLabel} bigSize={30} band={false} />
            ) : (
              <Wheel
                values={LB}
                value={Math.min(550, Math.max(66, pounds))}
                onChange={(v) => setKg(Math.round((v / LB_PER_KG) * 10) / 10)}
                half={2}
                label={lbLabel}
                bigSize={30}
                band={false}
              />
            )}
          </View>
        </View>
      </View>
      <View style={{ flex: 1.4 }} />
    </OnbLayout>
  );
}

const s = StyleSheet.create({
  toggle: { marginTop: 24 },
  cols: { flexDirection: 'row', gap: 16 },
  col: { flex: 1 },
  colLabel: { height: LABEL_H, textAlign: 'center', fontFamily: F.sansSemibold, fontSize: 15, color: C.ink },
});
