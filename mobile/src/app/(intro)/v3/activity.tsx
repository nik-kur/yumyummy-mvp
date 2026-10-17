/**
 * V3 screen 6 — Activity. Four answers on the Mifflin–St Jeor factors:
 * sitting 1.2, lightly active 1.375, active (3–5 workouts) 1.55,
 * very active (6–7 days) 1.725.
 */
import { useState } from 'react';

import { ChoiceScreen } from '@/components/onb/ChoiceScreen';
import { IMG } from '@/onb/assets';
import { useOnbScreen } from '@/onb/useOnbScreen';
import type { ActivityLevel } from '@/utils/calories';

const OPTIONS = [
  { key: 'sedentary' as ActivityLevel, label: 'Mostly sitting', sub: 'Desk job, little movement', icon: IMG.act_armchair },
  { key: 'light' as ActivityLevel, label: 'Lightly active', sub: 'Walks, 1–2 workouts a week', icon: IMG.act_sneaker },
  { key: 'moderate' as ActivityLevel, label: 'Active', sub: '3–5 workouts a week', icon: IMG.act_bike },
  { key: 'active' as ActivityLevel, label: 'Very active', sub: 'Training 6–7 days a week', icon: IMG.act_kettlebell },
];

export default function ActivityScreen() {
  const { intro, next, progress } = useOnbScreen('S6_activity');
  const [level, setLevel] = useState<ActivityLevel | null>(
    intro.activity_level && OPTIONS.some((o) => o.key === intro.activity_level) ? intro.activity_level : null,
  );
  return (
    <ChoiceScreen
      progress={progress}
      title="How active is your typical week?"
      options={OPTIONS}
      value={level}
      onChange={setLevel}
      iconSize={40}
      bold
      onContinue={() => level && next({ activity_level: level }, { activity: level }, { onb_activity: level })}
    />
  );
}
