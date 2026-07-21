/**
 * One-time "science & sources" intro popup flag.
 *
 * Shown once, the first time the user lands on the Today screen: it tells
 * them that all calculations are backed by published research and where to
 * find the full citations list (Profile → Science & sources). Per-device on
 * purpose (same trade-off as the AI consent flag): after a reinstall the
 * user simply sees it once more.
 */
import * as SecureStore from 'expo-secure-store';

const STORAGE_KEY = 'yy.sources_intro_seen.v1';

let cached: boolean | null = null;

export async function hasSeenSourcesIntro(): Promise<boolean> {
  if (cached !== null) return cached;
  try {
    cached = (await SecureStore.getItemAsync(STORAGE_KEY)) !== null;
  } catch {
    // If storage is unreadable, err on NOT showing the popup rather than
    // risking it on every launch.
    cached = true;
  }
  return cached;
}

export async function markSourcesIntroSeen(): Promise<void> {
  cached = true;
  try {
    await SecureStore.setItemAsync(STORAGE_KEY, new Date().toISOString());
  } catch {
    // Best-effort — the in-memory flag hides it for this session.
  }
}
