/** V3 screen 5b — Age on a wheel (14–99), Taptic tick per value. */
import { useCallback, useState } from 'react';
import { View } from 'react-native';

import { OnbButton } from '@/components/onb/OnbButton';
import { OnbLayout } from '@/components/onb/OnbLayout';
import { Wheel, type WheelLabel } from '@/components/onb/Wheel';
import { useOnbScreen } from '@/onb/useOnbScreen';

const AGES = Array.from({ length: 86 }, (_, i) => 14 + i);

export default function AgeScreen() {
  const { intro, next, progress } = useOnbScreen('S5_age');
  const [age, setAge] = useState(intro.age || 30);
  const label = useCallback((v: number): WheelLabel => [{ text: String(v) }, { text: 'years', unit: true }], []);
  return (
    <OnbLayout
      progress={progress}
      title="How old are you?"
      sub="Calorie needs change with age."
      footer={<OnbButton label="Continue" onPress={() => next({ age }, { age_bucket: Math.floor(age / 10) * 10 }, { onb_age_bucket: Math.floor(age / 10) * 10 })} />}
    >
      <View style={{ flex: 1 }} />
      <Wheel values={AGES} value={age} onChange={setAge} half={3} label={label} bigSize={34} />
      <View style={{ flex: 1.4 }} />
    </OnbLayout>
  );
}
