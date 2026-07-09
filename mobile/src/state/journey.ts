/**
 * "Your First Week" journey state machine.
 *
 * Each quest has a detection predicate and completion state.
 * The journey runs for 7 days from purchase; progress persists in AsyncStorage.
 */
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEY = '@yy_journey';

export interface QuestDef {
  day: number;
  quest: string;
  label: string;
  desc: string;
}

export interface JourneyState {
  started_at: string | null;
  completed: Record<string, boolean>;
  dismissed_popups: string[];
  last_popup_session: string | null;
}

const DEFAULT_STATE: JourneyState = {
  started_at: null,
  completed: {},
  dismissed_popups: [],
  last_popup_session: null,
};

export async function loadJourney(): Promise<JourneyState> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return DEFAULT_STATE;
    return { ...DEFAULT_STATE, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_STATE;
  }
}

export async function saveJourney(state: JourneyState): Promise<void> {
  await AsyncStorage.setItem(KEY, JSON.stringify(state)).catch(() => {});
}

export function currentDay(startedAt: string | null): number {
  if (!startedAt) return 0;
  const start = new Date(startedAt);
  const now = new Date();
  const diff = Math.floor((now.getTime() - start.getTime()) / (1000 * 60 * 60 * 24));
  return Math.min(diff + 1, 7);
}

export function activeQuest(
  quests: QuestDef[],
  state: JourneyState,
  day: number,
): QuestDef | null {
  const available = quests.filter((q) => q.day <= day && !state.completed[q.quest]);
  return available[0] ?? null;
}

export function completedCount(state: JourneyState): number {
  return Object.values(state.completed).filter(Boolean).length;
}

export function isJourneyComplete(state: JourneyState, totalQuests: number): boolean {
  return completedCount(state) >= totalQuests;
}
