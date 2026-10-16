/**
 * V3 screen 7 (after the ruler) — goal check:
 *   realistic (≤10 % of body weight) → praise the steady pace;
 *   ambitious (>10 %) → praise the ambition, promise milestones;
 *   below BMI 18.5 → never praised: "Let's aim for <healthy floor>", with
 *   "Change my goal" back to the ruler (agreed 15 Oct).
 */
import { MascotMessage } from '@/components/onb/MascotMessage';
import { IMG } from '@/onb/assets';
import { fmtKg, fmtStLb, goalCheck, healthyFloorKg } from '@/onb/plan';
import { useOnbScreen } from '@/onb/useOnbScreen';
import { useIntro } from '@/state/introContext';

export default function GoalCheckScreen() {
  const intro = useIntro();
  const target = intro.target_weight_kg ?? intro.weight_kg;
  const check = goalCheck(intro.weight_kg, target, intro.height_cm);
  const { next, progress, router } = useOnbScreen('S7_goal_check', check);
  const show = (kg: number) => (intro.units === 'imperial' ? fmtStLb(kg) : `${fmtKg(kg)} kg`);
  const losing = target < intro.weight_kg;
  const verb = losing ? 'Losing ' : 'Gaining ';
  const amount = show(Math.abs(target - intro.weight_kg));

  if (check === 'healthy') {
    const floor = healthyFloorKg(intro.height_cm);
    return (
      <MascotMessage
        progress={progress}
        mascot={IMG.mascot_heart}
        motion="beat"
        before="Let’s aim for "
        accent={show(floor)}
        sub={`${show(target)} would be below a healthy weight for your height. We’ll plan for ${show(floor)}, where the healthy range starts.`}
        cta={`Continue with ${show(floor)}`}
        onCta={() => next({ target_weight_kg: floor }, { accepted_healthy_target: true })}
        secondary={{ label: 'Change my goal', onPress: () => router.back() }}
      />
    );
  }
  if (check === 'ambitious') {
    return (
      <MascotMessage
        progress={progress}
        mascot={IMG.mascot_stellar}
        motion="hop"
        before={verb}
        accent={amount}
        after=" is ambitious. We love that."
        sub="People who aim high go further. We’ll split it into milestones and be with you at every meal."
        cta="Continue"
        onCta={() => next()}
      />
    );
  }
  return (
    <MascotMessage
      progress={progress}
      mascot={IMG.mascot_great}
      motion="bob"
      before={verb}
      accent={amount}
      after=" is a realistic target"
      sub="You’re in the right place. A steady pace is what makes it stick, and we’ll plan every day around it."
      cta="Continue"
      onCta={() => next()}
    />
  );
}
