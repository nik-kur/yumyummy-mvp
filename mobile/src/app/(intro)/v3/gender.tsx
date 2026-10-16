/** V3 screen 5a — Gender (Female / Male / Other; "other" uses the midpoint BMR). */
import { useState } from 'react';

import { ChoiceScreen } from '@/components/onb/ChoiceScreen';
import { useOnbScreen } from '@/onb/useOnbScreen';
import type { Gender } from '@/utils/calories';

const OPTIONS = [
  { key: 'female' as Gender, label: 'Female' },
  { key: 'male' as Gender, label: 'Male' },
  { key: 'other' as Gender, label: 'Other' },
];

export default function GenderScreen() {
  const { intro, next, progress } = useOnbScreen('S5_gender');
  const [gender, setGender] = useState<Gender | null>(intro.gender);
  return (
    <ChoiceScreen
      progress={progress}
      title="What’s your gender?"
      sub="We use it to calculate your metabolism."
      options={OPTIONS}
      value={gender}
      onChange={setGender}
      pad={{ v: 0, h: 20, minHeight: 64 }}
      onContinue={() => gender && next({ gender }, { gender })}
    />
  );
}
