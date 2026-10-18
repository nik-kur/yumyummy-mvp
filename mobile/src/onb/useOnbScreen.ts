/**
 * Shared plumbing of a V3 quiz screen: the screen-view event, the effective
 * onboarding config, the intro draft, and `next()` that follows the branching
 * rules in `flow.ts`.
 *
 * PostHog: `onboarding_screen_viewed` / `onboarding_screen_completed` with a
 * stable `screen` id and the screen's `variant` (the event names the pre-V3
 * onboarding already uses, so both arms of T0 read in one funnel; the arm's
 * variation and `onboarding_version` ride along as super properties).
 */
import { useCallback, useEffect, useRef } from 'react';
import { useRouter } from 'expo-router';

import { setPersonProperties, track } from '@/analytics/posthog';
import { useOnboardingConfig } from '@/config/onboardingConfig';
import { useIntro } from '@/state/introContext';
import type { IntroDraft } from '@/state/introDraft';

import { nextScreen, PROGRESS, type ScreenId } from './flow';

export function useOnbScreen(id: ScreenId, variant?: string) {
  const router = useRouter();
  const intro = useIntro();
  const { config, content } = useOnboardingConfig();
  const introRef = useRef(intro);
  introRef.current = intro;
  const leaving = useRef(false);

  useEffect(() => {
    track('onboarding_screen_viewed', { screen: id, variant: variant ?? null });
    // Only once per mount: a variant that depends on async content is logged as first rendered.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  /**
   * Save `patch`, log the answer, go to the next screen. `answer` lands in the
   * event and, when `person` is set, in the PostHog person properties too.
   */
  const next = useCallback(
    (
      patch: Partial<IntroDraft> = {},
      answer: Record<string, unknown> = {},
      person?: Record<string, unknown>,
      opts: { replace?: boolean } = {},
    ) => {
      if (leaving.current) return;
      leaving.current = true;
      setTimeout(() => {
        leaving.current = false;
      }, 600);
      // The stamp tells the next launch this draft is V3's, not a pre-V3 one to finish in v1.
      const stamped: Partial<IntroDraft> = { ...patch, flow: 'v3' };
      if (Object.keys(patch).length > 0 || introRef.current.flow !== 'v3') introRef.current.set(stamped);
      track('onboarding_screen_completed', { screen: id, variant: variant ?? null, ...answer });
      if (person) setPersonProperties(person);
      const draft = { ...introRef.current, ...stamped } as IntroDraft;
      const to = nextScreen(id, draft, config, content) as never;
      if (opts.replace) router.replace(to);
      else router.push(to);
    },
    [config, content, id, router, variant],
  );

  return { intro, config, content, next, progress: PROGRESS[id] ?? null, router };
}
