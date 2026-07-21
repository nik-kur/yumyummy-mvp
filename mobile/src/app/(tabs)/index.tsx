import { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  StyleSheet,
  Pressable,
  ActivityIndicator,
  Alert,
  Animated,
  Easing,
} from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { Sparkles, ChevronRight, CircleAlert } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Ring } from '@/components/Ring';
import { MacroBar } from '@/components/MacroBar';
import { SourceBadge, AccuracyBadge } from '@/components/Badges';
import { EmptyState } from '@/components/EmptyState';
import { useAuth } from '@/state/auth';
import { usePendingMeals, type PendingMeal } from '@/state/pendingMeals';
import * as api from '@/api/endpoints';
import type { DaySummary, MealRead } from '@/api/types';
import { updateWidgetSnapshot } from '@/widgets/snapshot';
import { JourneyCard } from '@/components/JourneyCard';
import { JourneyPopup } from '@/components/JourneyPopup';
import { JourneyPathSheet } from '@/components/JourneyPathSheet';
import { QuestInfoSheet } from '@/components/QuestInfoSheet';
import { InsightCard } from '@/components/InsightCard';
import { SourcesIntroPopup } from '@/components/SourcesIntroPopup';
import { WidgetInstructionSheet } from '@/components/WidgetInstructionSheet';
import { loadJourney, reconcileJourney, rawDay, activeDay, takeNextPopup, subscribeJourney, reportJourneyEvent, type JourneyState, type QuestDef, type QuestId } from '@/state/journey';
import { hasSeenSourcesIntro, markSourcesIntroSeen } from '@/state/sourcesIntro';
import { requestPermission, syncFromPrefs } from '@/notifications/scheduler';
import { loadPrefs, savePrefs } from '@/notifications/prefs';
import { maybeRequestReview } from '@/state/rateReview';
import { isAnyWidgetInstalled } from '../../../modules/widget-status';
import { formatInt, formatTime } from '@/utils/format';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function MealRow({ meal, onPress }: { meal: MealRead; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.mealRow, pressed && styles.pressed]}>
      <View style={styles.mealInfo}>
        <AppText variant="bodyStrong" numberOfLines={1}>
          {meal.description_user}
        </AppText>
        <View style={styles.badgeRow}>
          <AppText variant="caption" color={colors.inkMuted}>
            {formatTime(meal.eaten_at)}
          </AppText>
          {meal.source ? <SourceBadge source={meal.source} /> : null}
          {meal.accuracy_level ? <AccuracyBadge level={meal.accuracy_level} /> : null}
        </View>
      </View>
      <View style={styles.mealKcal}>
        <AppText variant="title">{formatInt(meal.calories)}</AppText>
        <AppText variant="overline" color={colors.inkFaint}>
          kcal
        </AppText>
      </View>
    </Pressable>
  );
}

// The agent usually answers in ~3–15 s. Instead of a bare spinner we show a
// progress bar tuned to ~10 s plus rotating stage captions (they mirror what
// the agent actually does, in order). Past 10 s the copy softens to
// "almost there" and the bar parks near the end — it never claims "done".
const PENDING_STAGES: Record<PendingMeal['kind'], string[]> = {
  text: ['Reading your meal…', 'Searching the web…', 'Checking sources…', 'Counting calories…'],
  photo: [
    'Looking at your photo…',
    'Spotting the foods…',
    'Searching the web…',
    'Checking sources…',
    'Counting calories…',
  ],
  voice: ['Transcribing your note…', 'Reading your meal…', 'Searching the web…', 'Counting calories…'],
};
const STAGE_MS = 2500;
const LONG_WAIT_MS = 10_000;
const LONG_WAIT_LABEL = 'Almost there — double-checking sources…';

function usePendingCaption(item: PendingMeal): string {
  const [now, setNow] = useState(Date.now());
  const processing = item.status === 'processing';
  useEffect(() => {
    if (!processing) return;
    const t = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(t);
  }, [processing]);

  const elapsed = now - item.createdAt;
  if (elapsed >= LONG_WAIT_MS) return LONG_WAIT_LABEL;
  const stages = PENDING_STAGES[item.kind];
  return stages[Math.min(Math.floor(elapsed / STAGE_MS), stages.length - 1)] ?? '';
}

function PendingProgress({ createdAt }: { createdAt: number }) {
  const progress = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    // Resume mid-flight if the row re-mounts (tab switch, refetch).
    const elapsed = Date.now() - createdAt;
    progress.setValue(Math.min(elapsed / LONG_WAIT_MS, 1) * 0.9);
    const anims: Animated.CompositeAnimation[] = [];
    if (elapsed < LONG_WAIT_MS) {
      anims.push(
        Animated.timing(progress, {
          toValue: 0.9,
          duration: LONG_WAIT_MS - elapsed,
          easing: Easing.out(Easing.quad),
          useNativeDriver: false,
        }),
      );
    }
    // Slow crawl for long waits so the bar keeps breathing but never finishes.
    anims.push(
      Animated.timing(progress, {
        toValue: 0.97,
        duration: 60_000,
        easing: Easing.linear,
        useNativeDriver: false,
      }),
    );
    const seq = Animated.sequence(anims);
    seq.start();
    return () => seq.stop();
  }, [createdAt, progress]);

  const width = progress.interpolate({ inputRange: [0, 1], outputRange: ['0%', '100%'] });
  return (
    <View style={styles.progressTrack}>
      <Animated.View style={[styles.progressFill, { width }]} />
    </View>
  );
}

function PendingRow({ item, onPress }: { item: PendingMeal; onPress: () => void }) {
  const caption = usePendingCaption(item);
  const isError = item.status === 'error';
  // While processing, dim the whole row (bank-style "pending" treatment) so it
  // reads as in-flight, not a finished entry.
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.mealRow, !isError && styles.pendingRow, pressed && styles.pressed]}
    >
      <View style={styles.mealInfo}>
        <AppText
          variant="bodyStrong"
          numberOfLines={1}
          color={isError ? colors.terracottaText : colors.inkMuted}
        >
          {item.label}
        </AppText>
        {isError ? (
          <View style={styles.badgeRow}>
            <AppText variant="caption" color={colors.terracottaText}>
              Tap to retry
            </AppText>
          </View>
        ) : (
          <>
            <AppText variant="caption" color={colors.inkFaint}>
              {caption}
            </AppText>
            <PendingProgress createdAt={item.createdAt} />
          </>
        )}
      </View>
      <View style={styles.mealKcal}>
        {isError ? (
          <CircleAlert size={22} color={colors.terracottaText} strokeWidth={1.5} />
        ) : (
          <ActivityIndicator size="small" color={colors.inkFaint} />
        )}
      </View>
    </Pressable>
  );
}

export default function TodayScreen() {
  const router = useRouter();
  const { profile } = useAuth();
  const { pending, lastSettledAt, retry, dismiss } = usePendingMeals();
  const [day, setDay] = useState<DaySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [journey, setJourney] = useState<JourneyState | null>(null);
  const [insight, setInsight] = useState<Record<string, unknown> | null>(null);
  const [popupQuestId, setPopupQuestId] = useState<QuestId | null>(null);
  const [widgetSheetVisible, setWidgetSheetVisible] = useState(false);
  const [pathSheetVisible, setPathSheetVisible] = useState(false);
  const [infoQuest, setInfoQuest] = useState<QuestDef | null>(null);
  const [sourcesIntroVisible, setSourcesIntroVisible] = useState(false);

  // One-time "backed by science" popup on the very first visit to Today
  // (Guideline 1.4.1 — tells the user where the citations live). Quest popups
  // hold back while it's on screen so two sheets never stack.
  useEffect(() => {
    let active = true;
    void hasSeenSourcesIntro().then((seen) => {
      if (active && !seen) setSourcesIntroVisible(true);
    });
    return () => {
      active = false;
    };
  }, []);

  const dismissSourcesIntro = useCallback(() => {
    setSourcesIntroVisible(false);
    void markSourcesIntroSeen();
    track('sources_intro_dismissed');
  }, []);

  const load = useCallback(async () => {
    try {
      const [d, journeyRaw, ins] = await Promise.all([
        api.getToday(),
        // Settle any actions done earlier whose day has unlocked overnight
        // (a day can open at midnight without a fresh domain event).
        reconcileJourney().catch(() => {}).then(() => loadJourney()),
        api.getLatestInsight().catch(() => null),
      ]);
      setDay(d);
      let j = journeyRaw;
      // Real insights only (no 'motivation' fallback), and only from journey
      // Day 3 onward. After the first week we also drop the low-value
      // "N days logged" consistency banner so it doesn't linger forever.
      const rd = j.started_at ? rawDay(j.started_at) : null;
      const insightUnlocked = rd === null || rd >= 3;
      const consistencyStale = rd !== null && rd > 7 && ins?.id === 'consistency';
      if (ins && ins.id !== 'motivation' && insightUnlocked && !consistencyStale) {
        setInsight(ins);
      } else {
        setInsight(null);
      }

      if (j.started_at) {
        const journeyDay = rawDay(j.started_at);
        if (journeyDay >= 1 && journeyDay <= 7) {
          const mealCount = d?.meals?.length ?? 0;
          if (mealCount > 0) {
            await reportJourneyEvent({
              type: 'log_created',
              source: 'unknown',
              todayCount: mealCount,
            }).catch(() => {});
            j = await loadJourney();
          }

          const hasWidget = await isAnyWidgetInstalled();
          if (hasWidget) {
            await reportJourneyEvent({ type: 'widget_installed' }).catch(() => {});
            j = await loadJourney();
          }

          const popup = await takeNextPopup();
          if (popup) setPopupQuestId(popup);
        }
      }
      setJourney(j);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  useEffect(() => subscribeJourney(() => { void load(); }), [load]);

  // Refetch whenever a background meal finishes so the new entry appears.
  useEffect(() => {
    if (lastSettledAt) load();
  }, [lastSettledAt, load]);

  // Keep the home/lock-screen widgets in sync with today's numbers.
  useEffect(() => {
    updateWidgetSnapshot(day, profile);
  }, [day, profile]);

  const onPendingPress = useCallback(
    (item: PendingMeal) => {
      if (item.status === 'error') {
        Alert.alert('Couldn’t log this', item.error ?? 'Something went wrong.', [
          { text: 'Try again', onPress: () => retry(item.id) },
          { text: 'Remove', style: 'destructive', onPress: () => dismiss(item.id) },
          { text: 'Cancel', style: 'cancel' },
        ]);
      } else {
        Alert.alert(
          'Finding exact numbers',
          'We’re checking the web for accurate calories and macros. This usually takes ~10 seconds — your meal appears here automatically when it’s ready.',
          [{ text: 'Got it' }],
        );
      }
    },
    [retry, dismiss],
  );

  const dismissPopup = useCallback(() => {
    // Closing a full day is the first big "it works" moment — ask for a rating
    // right after the celebratory popup (guarded so it never nags).
    if (popupQuestId === 'full_day') void maybeRequestReview('full_day_closed');
    setPopupQuestId(null);
  }, [popupQuestId]);

  const onWidgetDone = useCallback(async () => {
    setWidgetSheetVisible(false);
    await reportJourneyEvent({ type: 'widget_installed' }).catch(() => {});
    void load();
  }, [load]);

  // One-tap reminder enable (no per-meal choices in onboarding): ask the OS,
  // flip the master switch, schedule the default set. Only when permission is
  // denied do we fall back to the Notifications screen (it shows the
  // "blocked → Open Settings" card).
  const enableRemindersOneTap = useCallback(async () => {
    try {
      const granted = await requestPermission();
      if (!granted) {
        router.push('/notifications');
        return;
      }
      const prefs = await loadPrefs();
      prefs.enabled = true;
      await savePrefs(prefs);
      await syncFromPrefs(prefs);
      await reportJourneyEvent({ type: 'push_permission_granted' }).catch(() => {});
    } catch {
      router.push('/notifications');
    }
  }, [router]);

  const onQuestGo = useCallback(
    (quest: QuestDef) => {
      setInfoQuest(null);
      switch (quest.id) {
        case 'widget':
          setWidgetSheetVisible(true);
          break;
        case 'reminders':
          void enableRemindersOneTap();
          break;
        case 'ai_question':
          router.push('/advisor');
          break;
        case 'week_trends':
          router.push('/(tabs)/week');
          break;
        case 'menu':
          router.push('/(tabs)/menu');
          break;
        case 'weigh_in':
          router.push('/(tabs)/profile');
          break;
        case 'delete_meal':
        case 'edit_meal':
          // Both are done from a logged meal — send the user to Today's list.
          router.push('/(tabs)');
          break;
        default:
          if (quest.id.startsWith('menu_log')) router.push('/(tabs)/menu');
          else router.push('/capture');
      }
    },
    [router, enableRemindersOneTap],
  );

  const onQuestPress = useCallback((quest: QuestDef) => {
    track('quest_info_opened', { quest: quest.id, day: quest.day });
    if (quest.id === 'widget') {
      setWidgetSheetVisible(true);
    } else {
      setInfoQuest(quest);
    }
  }, []);

  const now = new Date();
  const hour = now.getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const dateLabel = `${WEEKDAYS[now.getDay()] ?? ''}, ${MONTHS[now.getMonth()] ?? ''} ${now.getDate()}`;

  const target = profile?.target_calories ?? 0;
  const hasTarget = target > 0;
  const consumed = Math.round(day?.total_calories ?? 0);
  const remaining = Math.round(target - consumed);
  const over = remaining < 0;
  const progress = hasTarget ? consumed / target : 0;

  // Newest first (like a message feed) — the backend returns the day ascending.
  const meals = [...(day?.meals ?? [])].sort((a, b) => {
    const ta = Date.parse(a.eaten_at ?? '');
    const tb = Date.parse(b.eaten_at ?? '');
    if (Number.isFinite(ta) && Number.isFinite(tb) && ta !== tb) return tb - ta;
    return (b.id ?? 0) - (a.id ?? 0);
  });

  return (
    <Screen scroll>
      <View style={styles.header}>
        <AppText variant="overline" color={colors.inkMuted}>
          {dateLabel}
        </AppText>
        <AppText variant="h1" style={styles.greeting}>
          {greeting}
        </AppText>
      </View>

      {loading && !day ? (
        <View style={styles.loading}>
          <ActivityIndicator color={colors.terracotta} />
        </View>
      ) : (
        <>
          <Card style={styles.hero}>
            <Ring progress={progress} color={over ? colors.terracottaText : colors.terracotta} size={200}>
              <View style={styles.ringCenter}>
                {hasTarget ? (
                  <>
                    <AppText variant="heroNum" color={over ? colors.terracottaText : colors.ink}>
                      {formatInt(Math.abs(remaining))}
                    </AppText>
                    <AppText variant="overline" color={colors.inkMuted}>
                      {over ? 'kcal over' : 'kcal left'}
                    </AppText>
                  </>
                ) : (
                  <>
                    <AppText variant="heroNum" color={colors.ink}>
                      {formatInt(consumed)}
                    </AppText>
                    <AppText variant="overline" color={colors.inkMuted}>
                      kcal today
                    </AppText>
                  </>
                )}
              </View>
            </Ring>
            <AppText variant="small" color={colors.inkMuted} style={styles.heroCaption}>
              {hasTarget
                ? `${formatInt(consumed)} eaten · ${formatInt(target)} goal`
                : 'No target set — tracking only'}
            </AppText>

            <View style={styles.macros}>
              <MacroBar label="Protein" macro="protein" value={day?.total_protein_g ?? 0} target={profile?.target_protein_g} />
              <MacroBar label="Fat" macro="fat" value={day?.total_fat_g ?? 0} target={profile?.target_fat_g} />
              <MacroBar label="Carbs" macro="carbs" value={day?.total_carbs_g ?? 0} target={profile?.target_carbs_g} />
            </View>
          </Card>

          {journey && journey.started_at && !journey.dismissed && rawDay(journey.started_at) <= 7 && (
            <View style={styles.journeyWrap}>
              <JourneyCard
                state={journey}
                day={activeDay(journey)}
                onHeaderPress={() => {
                  track('journey_path_opened');
                  setPathSheetVisible(true);
                }}
                onQuestPress={onQuestPress}
              />
            </View>
          )}

          {insight && (
            <View style={styles.insightWrap}>
              <InsightCard
                insight={insight as { id?: string; icon?: string; title?: string; body?: string }}
              />
            </View>
          )}

          <Pressable onPress={() => router.push('/advisor')}>
            <Card style={styles.advisorCard} flat>
              <View style={styles.advisorIcon}>
                <Sparkles size={20} color={colors.infoBlue} strokeWidth={1.5} />
              </View>
              <View style={styles.advisorText}>
                <AppText variant="bodyStrong">What should I eat next?</AppText>
                <AppText variant="caption" color={colors.inkMuted}>
                  Ask your AI advisor for a meal that fits your budget
                </AppText>
              </View>
              <ChevronRight size={20} color={colors.inkFaint} strokeWidth={1.5} />
            </Card>
          </Pressable>

          <View style={styles.mealsHeader}>
            <AppText variant="overline" color={colors.inkMuted}>
              Today’s meals
            </AppText>
            {meals.length > 0 || pending.length > 0 ? (
              <AppText variant="caption" color={colors.inkFaint}>
                {meals.length} logged{pending.length > 0 ? ` · ${pending.length} analyzing` : ''}
              </AppText>
            ) : null}
          </View>

          {meals.length === 0 && pending.length === 0 ? (
            <EmptyState
              mascot="hungry"
              title="Nothing logged yet"
              subtitle="Tap the + below and tell me what you ate — a sentence is enough."
              ctaLabel="Log something"
              onCta={() => router.push('/capture')}
            />
          ) : (
            <>
              {pending.length > 0 ? (
                <Card padded={false} style={styles.mealsCard}>
                  {pending.map((p, i) => (
                    <View key={p.id}>
                      {i > 0 ? <View style={styles.sep} /> : null}
                      <PendingRow item={p} onPress={() => onPendingPress(p)} />
                    </View>
                  ))}
                </Card>
              ) : null}

              {meals.length > 0 ? (
                <Card padded={false} style={[styles.mealsCard, pending.length > 0 ? styles.mealsCardStacked : null]}>
                  {meals.map((m, i) => (
                    <View key={m.id}>
                      {i > 0 ? <View style={styles.sep} /> : null}
                      <MealRow
                        meal={m}
                        onPress={() =>
                          router.push({
                            pathname: '/meal/[id]',
                            params: {
                              id: String(m.id),
                              d: m.description_user,
                              c: String(m.calories),
                              p: String(m.protein_g),
                              f: String(m.fat_g),
                              cb: String(m.carbs_g),
                              acc: m.accuracy_level ?? '',
                              src: m.source ?? '',
                              t: m.eaten_at,
                            },
                          })
                        }
                      />
                    </View>
                  ))}
                </Card>
              ) : null}
            </>
          )}
        </>
      )}

      <SourcesIntroPopup visible={sourcesIntroVisible} onDismiss={dismissSourcesIntro} />

      {/* Mount at most one bottom sheet at a time — the sources intro takes
          priority; a pending quest popup appears right after it's dismissed. */}
      {popupQuestId && !sourcesIntroVisible && (
        <JourneyPopup
          questId={popupQuestId}
          visible={!!popupQuestId}
          onDismiss={dismissPopup}
        />
      )}

      <WidgetInstructionSheet
        visible={widgetSheetVisible}
        onDismiss={() => setWidgetSheetVisible(false)}
        onDone={onWidgetDone}
      />

      {journey && (
        <JourneyPathSheet
          visible={pathSheetVisible}
          state={journey}
          onDismiss={() => setPathSheetVisible(false)}
        />
      )}

      <QuestInfoSheet
        quest={infoQuest}
        onDismiss={() => setInfoQuest(null)}
        onGo={onQuestGo}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { marginTop: space.sm, marginBottom: space.lg },
  greeting: { marginTop: space.xs },
  loading: { paddingVertical: space.xxxl, alignItems: 'center' },
  hero: { alignItems: 'center', paddingVertical: space.xl },
  ringCenter: { alignItems: 'center', justifyContent: 'center' },
  heroCaption: { marginTop: space.md },
  macros: { alignSelf: 'stretch', gap: space.md, marginTop: space.lg },
  journeyWrap: { marginTop: space.base },
  insightWrap: { marginTop: space.base },
  advisorCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    marginTop: space.base,
    backgroundColor: colors.infoBlueSoft,
    borderColor: colors.infoBlueSoft,
  },
  advisorIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    alignItems: 'center',
    justifyContent: 'center',
  },
  advisorText: { flex: 1, gap: 2 },
  mealsHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: space.xl,
    marginBottom: space.sm,
  },
  mealsCard: { overflow: 'hidden' },
  mealsCardStacked: { marginTop: space.sm },
  mealRow: { flexDirection: 'row', alignItems: 'center', gap: space.base, padding: space.base },
  pendingRow: { opacity: 0.85 },
  pressed: { backgroundColor: colors.surfaceAlt },
  mealInfo: { flex: 1, gap: 4 },
  badgeRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexWrap: 'wrap' },
  mealKcal: { alignItems: 'flex-end' },
  progressTrack: {
    height: 3,
    borderRadius: radius.pill,
    backgroundColor: colors.hairline,
    overflow: 'hidden',
    marginTop: space.xs,
  },
  progressFill: { height: '100%', borderRadius: radius.pill, backgroundColor: colors.terracotta },
  sep: { height: StyleSheet.hairlineWidth, backgroundColor: colors.hairline, marginLeft: space.base },
});
