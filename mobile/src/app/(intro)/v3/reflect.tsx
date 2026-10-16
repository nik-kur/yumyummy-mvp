/**
 * V3 screen 3 — Reflect-back by goal: "many people here want the same, you're
 * in the right place". Copy can be overridden from `onb_content.texts`
 * (`reflect.<goal>.before|accent|after|sub`).
 */
import { MascotMessage } from '@/components/onb/MascotMessage';
import { IMG } from '@/onb/assets';
import { useOnbScreen } from '@/onb/useOnbScreen';
import { useIntro } from '@/state/introContext';
import type { GoalType } from '@/utils/calories';

type Copy = { before: string; accent: string; after?: string; sub: string };

const COPY: Record<GoalType, Copy> = {
  lose: {
    before: 'Most people here want to lose ',
    accent: '5–10 kg',
    sub: 'You’re in the right place. We’ll plan around the food you already love.',
  },
  maintain: {
    before: 'Lots of people here want to eat better ',
    accent: 'without dieting',
    sub: 'You’re in the right place to do it. We’ll plan around the food you already love.',
  },
  gain: {
    before: 'Lots of people here are ',
    accent: 'building muscle',
    sub: 'Protein is where it starts. You’re in the right place.',
  },
  just_track: {
    before: 'Lots of people here start by ',
    accent: 'just seeing what they eat',
    sub: 'That alone changes a lot. You’re in the right place.',
  },
};

const KEY: Record<GoalType, string> = { lose: 'lose', maintain: 'maintain', gain: 'gain', just_track: 'track' };

export default function ReflectScreen() {
  const goal = useIntro().goal_type ?? 'lose';
  const { content, next, progress } = useOnbScreen('S3_reflect', KEY[goal]);
  const base = COPY[goal];
  const t = (part: keyof Copy) => content.texts[`reflect.${KEY[goal]}.${part}`] ?? base[part];
  return (
    <MascotMessage
      progress={progress}
      mascot={IMG.mascot_heart}
      motion="beat"
      before={t('before') ?? ''}
      accent={t('accent') ?? ''}
      after={t('after')}
      sub={t('sub') ?? ''}
      cta="Continue"
      onCta={() => next()}
    />
  );
}
