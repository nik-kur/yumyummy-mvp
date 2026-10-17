/** V3 screen 9 — Tracked before? "Yes" → Barriers (10), "No" → Features by weight direction. */
import { useState } from 'react';

import { ChoiceScreen } from '@/components/onb/ChoiceScreen';
import { IMG } from '@/onb/assets';
import { useOnbScreen } from '@/onb/useOnbScreen';

type Answer = 'yes' | 'no';

const OPTIONS = [
  { key: 'yes' as Answer, label: 'Yes, I have', icon: IMG.misc_notebook },
  { key: 'no' as Answer, label: 'No, this is my first time', icon: IMG.bar_sprout },
];

export default function TrackedScreen() {
  const { intro, next, progress } = useOnbScreen('S9_tracked');
  const [answer, setAnswer] = useState<Answer | null>(
    intro.tracked_before === null ? null : intro.tracked_before ? 'yes' : 'no',
  );
  return (
    <ChoiceScreen
      progress={progress}
      title="Have you tracked calories before?"
      sub="Any app, notebook or spreadsheet counts."
      options={OPTIONS}
      value={answer}
      onChange={setAnswer}
      iconSize={40}
      pad={{ v: 16, h: 18 }}
      onContinue={() =>
        answer &&
        next(
          answer === 'yes'
            ? { tracked_before: true }
            : { tracked_before: false, barrier: null, pain_points: [] },
          { tracked_before: answer === 'yes' },
          { onb_tracked_before: answer === 'yes' },
        )
      }
    />
  );
}
