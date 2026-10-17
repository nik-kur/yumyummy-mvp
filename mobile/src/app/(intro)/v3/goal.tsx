/** V3 screen 2 — Goal. The answer sets the tone for Reflect, Features and the plan. */
import { useState } from 'react';

import { ChoiceScreen } from '@/components/onb/ChoiceScreen';
import { IMG } from '@/onb/assets';
import { useOnbScreen } from '@/onb/useOnbScreen';
import type { GoalType } from '@/utils/calories';

const OPTIONS = [
  { key: 'lose' as GoalType, label: 'Lose weight', icon: IMG.goal_lose },
  { key: 'maintain' as GoalType, label: 'Maintain and eat healthier', icon: IMG.goal_maintain },
  { key: 'gain' as GoalType, label: 'Gain muscle', icon: IMG.goal_gain },
  { key: 'just_track' as GoalType, label: 'Just track my food', icon: IMG.goal_track },
];

export default function GoalScreen() {
  const { intro, next, progress } = useOnbScreen('S2_goal');
  const [goal, setGoal] = useState<GoalType | null>(intro.goal_type);
  return (
    <ChoiceScreen
      progress={progress}
      title="What’s your goal?"
      sub="We’ll build your plan around it."
      options={OPTIONS}
      value={goal}
      onChange={setGoal}
      onContinue={() => goal && next({ goal_type: goal }, { goal }, { onb_goal: goal })}
    />
  );
}
