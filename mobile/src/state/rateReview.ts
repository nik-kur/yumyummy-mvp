/**
 * In-app rating prompt (Apple SKStoreReviewController via expo-store-review).
 *
 * Best practices we follow:
 * - Only ask at genuinely positive moments (a closed day, the Week 1 Report),
 *   never mid-flow and never after an error.
 * - Never nag: at most one prompt every 90 days and 3 lifetime, on top of
 *   Apple's own system cap (the OS silently ignores extra requests anyway).
 * - The native sheet decides whether to actually appear — we can't detect the
 *   result, so we optimistically record the attempt.
 *
 * A "Rate YumYummy" row in the profile calls `openStoreReviewFromSettings()`,
 * which is allowed to prompt on demand (an explicit user action).
 */
import * as SecureStore from 'expo-secure-store';
import * as StoreReview from 'expo-store-review';
import { Linking } from 'react-native';

import { track } from '@/analytics/posthog';

const LAST_KEY = 'yy.review.last_prompt.v1';
const COUNT_KEY = 'yy.review.count.v1';

const MIN_DAYS_BETWEEN = 90;
const MAX_LIFETIME_PROMPTS = 3;

// App Store id (from eas.json submit.ascAppId) — used for the explicit
// "Rate YumYummy" settings row so it opens the write-review page directly.
const APP_STORE_ID = '6785363037';
const WRITE_REVIEW_URL = `https://apps.apple.com/app/id${APP_STORE_ID}?action=write-review`;

async function readNumber(key: string): Promise<number> {
  try {
    const raw = await SecureStore.getItemAsync(key);
    const n = raw ? Number(raw) : 0;
    return Number.isFinite(n) ? n : 0;
  } catch {
    return 0;
  }
}

async function recordPrompt(): Promise<void> {
  const count = await readNumber(COUNT_KEY);
  try {
    await SecureStore.setItemAsync(LAST_KEY, String(Date.now()));
    await SecureStore.setItemAsync(COUNT_KEY, String(count + 1));
  } catch {
    // Best-effort — a missed write just means we might ask once more later.
  }
}

/**
 * Ask for a review at a positive moment, respecting our own frequency caps.
 * Silently does nothing when review isn't available or we've asked recently.
 */
export async function maybeRequestReview(reason: string): Promise<void> {
  try {
    if (!(await StoreReview.hasAction())) return;

    const count = await readNumber(COUNT_KEY);
    if (count >= MAX_LIFETIME_PROMPTS) return;

    const last = await readNumber(LAST_KEY);
    if (last > 0) {
      const days = (Date.now() - last) / (1000 * 60 * 60 * 24);
      if (days < MIN_DAYS_BETWEEN) return;
    }

    track('review_prompt_requested', { reason });
    await recordPrompt();
    await StoreReview.requestReview();
  } catch {
    // Never let a rating prompt break the calling flow.
  }
}

/**
 * Explicit "Rate YumYummy" action from settings — always tries to act:
 * open the App Store review page if configured, otherwise the native sheet.
 */
export async function openStoreReviewFromSettings(): Promise<void> {
  try {
    track('review_prompt_requested', { reason: 'settings' });
    const url = (await StoreReview.storeUrl()) || WRITE_REVIEW_URL;
    if (await Linking.canOpenURL(url)) {
      await Linking.openURL(url);
      return;
    }
    if (await StoreReview.hasAction()) {
      await StoreReview.requestReview();
    }
  } catch {
    // No-op on failure.
  }
}
