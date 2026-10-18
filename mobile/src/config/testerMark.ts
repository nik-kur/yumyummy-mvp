/**
 * Tester mark for a production install (Nikita's own iPhone).
 *
 * `yumyummy://tester?code=<code>` marks the install. A marked install reads
 * tester-only placements first (`onb_main_qa`, `onb_content_qa`, `pw_main_qa`,
 * `pw_after_cancel_qa`; see `testerDevice.ts`), whose flows are switched for
 * that phone alone — screen 16 with demo reviews, any paywall or offer
 * variant — while App Review and real customers never see them.
 *
 * Only one code is accepted: the app holds its SHA-256, the code itself is
 * Nikita's. The code also goes to the Adapty profile as the custom attribute
 * `qa_tester` (for a dashboard segment, if one is ever wanted). `code=off`
 * removes the mark.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';
import { adapty } from 'react-native-adapty';

import { register, setPersonProperties, track } from '@/analytics/posthog';
import { captureException } from '@/analytics/sentry';
import { waitForAdaptyIdentify, whenAdaptyActivated } from '@/billing/adapty';
import { sha256Hex } from '@/utils/sha256';

import { clearOnboardingAssignment } from './onboardingConfig';
import { isTesterDevice, setTesterDevice, TESTER_CODE_KEY } from './testerDevice';

export { TESTER_CODE_KEY };
export const TESTER_ATTRIBUTE = 'qa_tester';
/** SHA-256 (hex) of the one tester code that marks an install. */
const TESTER_CODE_SHA256 = '1fe957d0c77da96ecf5d8a4db21da434160dff6b473134792513a1fa26e385a0';

/** Adapty caps attribute values at 50 chars; keep the code URL-safe and short. */
export function sanitizeTesterCode(raw: string | undefined | null): string | null {
  if (!raw) return null;
  const code = raw.trim();
  return /^[A-Za-z0-9_-]{1,50}$/.test(code) ? code : null;
}

export type TesterResult = 'marked' | 'cleared' | 'failed' | 'invalid';

/**
 * Apply (or with `off`, remove) the mark, then forget the stored onboarding arm
 * so the next run asks Adapty again — now as a member of the tester segment.
 */
export async function applyTesterCode(code: string): Promise<TesterResult> {
  const clearing = code === 'off';
  if (!clearing && sha256Hex(code) !== TESTER_CODE_SHA256) return 'invalid';
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
  setTesterDevice(!clearing);
  await clearOnboardingAssignment();
  return clearing ? 'cleared' : 'marked';
}

export function isTesterMarked(): Promise<boolean> {
  return isTesterDevice();
}
