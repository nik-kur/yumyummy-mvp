/**
 * Tester mark for a production install (Nikita's own iPhone).
 *
 * `yumyummy://tester?code=<code>` writes the code into the Adapty profile as
 * the custom attribute `qa_tester`. An Adapty segment matching that exact code
 * can then get its own onboarding / paywall arm — screen 16 with demo reviews,
 * any test variant — while App Review and real customers never see it.
 *
 * The app holds no secret: it stores whatever code the link carries, and only
 * the dashboard knows which value the tester segment matches. `code=off`
 * removes the mark.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { adapty } from 'react-native-adapty';

import { register, setPersonProperties, track } from '@/analytics/posthog';
import { captureException } from '@/analytics/sentry';
import { waitForAdaptyIdentify, whenAdaptyActivated } from '@/billing/adapty';

import { clearOnboardingAssignment } from './onboardingConfig';

/** Shared with `billing/adapty.ts`, which re-applies the mark to a new profile. */
export const TESTER_CODE_KEY = '@yy_qa_tester';
export const TESTER_ATTRIBUTE = 'qa_tester';

/** Adapty caps attribute values at 50 chars; keep the code URL-safe and short. */
export function sanitizeTesterCode(raw: string | undefined | null): string | null {
  if (!raw) return null;
  const code = raw.trim();
  return /^[A-Za-z0-9_-]{1,50}$/.test(code) ? code : null;
}

export type TesterResult = 'marked' | 'cleared' | 'failed';

/**
 * Apply (or with `off`, remove) the mark, then forget the stored onboarding arm
 * so the next run asks Adapty again — now as a member of the tester segment.
 */
export async function applyTesterCode(code: string): Promise<TesterResult> {
  const clearing = code === 'off';
  try {
    if (!(await whenAdaptyActivated(1200))) return 'failed';
    // A signed-in phone identifies in the background at launch; writing before
    // that lands would hit the anonymous profile (or fail with #3006).
    await waitForAdaptyIdentify();
    await adapty.updateProfile({
      codableCustomAttributes: { [TESTER_ATTRIBUTE]: clearing ? null : code },
    });
  } catch (e) {
    captureException(e, { where: 'tester_mark' });
    return 'failed';
  }
  // PostHog gets the flag, never the code itself (that is the segment's key).
  register({ qa_tester: !clearing });
  setPersonProperties({ qa_tester: !clearing });
  track(clearing ? 'qa_tester_cleared' : 'qa_tester_marked');
  if (clearing) await AsyncStorage.removeItem(TESTER_CODE_KEY).catch(() => {});
  else await AsyncStorage.setItem(TESTER_CODE_KEY, code).catch(() => {});
  await clearOnboardingAssignment();
  return clearing ? 'cleared' : 'marked';
}

export async function isTesterMarked(): Promise<boolean> {
  try {
    return Boolean(await AsyncStorage.getItem(TESTER_CODE_KEY));
  } catch {
    return false;
  }
}
