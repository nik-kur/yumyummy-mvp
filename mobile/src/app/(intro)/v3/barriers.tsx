/** V3 screen 10 — What made tracking hard? One answer; it picks the Features variant. */
import { useState } from 'react';

import { ChoiceScreen } from '@/components/onb/ChoiceScreen';
import { IMG } from '@/onb/assets';
import { useOnbScreen } from '@/onb/useOnbScreen';

export type Barrier = 'too_long' | 'gave_up' | 'accuracy' | 'eating_out' | 'other';

const OPTIONS = [
  { key: 'too_long' as Barrier, label: 'Logging took too long', icon: IMG.bar_time },
  { key: 'gave_up' as Barrier, label: 'I gave up after a few days', icon: IMG.bar_battery },
  { key: 'accuracy' as Barrier, label: 'Never sure the calories were right', icon: IMG.bar_dice },
  { key: 'eating_out' as Barrier, label: 'Eating out broke everything', icon: IMG.bar_takeaway },
  { key: 'other' as Barrier, label: 'Other', icon: IMG.misc_dots },
];

export default function BarriersScreen() {
  const { intro, next, progress } = useOnbScreen('S10_barriers');
  const [barrier, setBarrier] = useState<Barrier | null>((intro.barrier as Barrier | null) ?? null);
  return (
    <ChoiceScreen
      progress={progress}
      title="What made tracking hard before?"
      sub="Pick the main one."
      options={OPTIONS}
      value={barrier}
      onChange={setBarrier}
      gap={10}
      pad={{ v: 12, h: 16 }}
      onContinue={() => barrier && next({ barrier, pain_points: [barrier] }, { barrier }, { onb_barrier: barrier })}
    />
  );
}
