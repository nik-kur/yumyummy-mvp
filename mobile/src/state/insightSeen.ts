/**
 * First-seen tracker for insight banners on Today.
 *
 * The backend recomputes insights from a rolling 7-day window, so a banner
 * like "7 days logged" wins the rule ladder every single day for an active
 * user and would sit on the home screen forever. Policy: an insight variant
 * (id + metric value) earns exactly ONE calendar day on screen — the day it
 * first appears. A new value ("6 days" → "7 days") is a new variant and gets
 * its own day.
 *
 * Only the latest variant is remembered: the backend serves one insight at a
 * time, and regressions to an older value are rare enough to just re-show.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = '@yy_insight_seen';

/** Local calendar date (YYYY-MM-DD) — banner days follow the user's clock. */
function today(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

/**
 * True while the insight variant is still within its one-day window.
 * Records the first sighting as a side effect. Fails open: a storage error
 * shows the banner (today's behavior) rather than hiding real content.
 */
export async function insightSeenToday(id: string, metricValue: string): Promise<boolean> {
  const sig = `${id}:${metricValue}`;
  try {
    const raw = await AsyncStorage.getItem(KEY);
    const stored = raw ? (JSON.parse(raw) as { sig?: string; date?: string }) : null;
    if (stored?.sig === sig) return stored.date === today();
    await AsyncStorage.setItem(KEY, JSON.stringify({ sig, date: today() }));
    return true;
  } catch {
    return true;
  }
}
