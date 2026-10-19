/**
 * Whether this install carries the tester mark (`config/testerMark.ts`), and
 * the tester-only placements a marked install reads. A leaf module: Adapty,
 * the onboarding config and the paywall arms all ask it.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

/** Shared with `billing/adapty.ts`, which re-applies the mark to a new profile. */
export const TESTER_CODE_KEY = '@yy_qa_tester';

let marked: boolean | null = null;

export async function isTesterDevice(): Promise<boolean> {
  if (marked === null) {
    try {
      marked = Boolean(await AsyncStorage.getItem(TESTER_CODE_KEY));
    } catch {
      marked = false;
    }
  }
  return marked;
}

/** The mark was just set or removed. */
export function setTesterDevice(value: boolean): void {
  marked = value;
}

/**
 * A marked install reads `<placement>_qa` first: placements that exist for
 * Nikita's phone only, so their flows can be switched while he tests without
 * touching anyone else (a live A/B test included). Everyone else: `null`.
 */
export async function testerPlacement(placement: string): Promise<string | null> {
  return (await isTesterDevice()) ? `${placement}_qa` : null;
}
