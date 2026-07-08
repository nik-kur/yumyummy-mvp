import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { View, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { ChevronLeft, ChevronRight, Flame } from 'lucide-react-native';
import * as Haptics from 'expo-haptics';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { SourceBadge, AccuracyBadge } from '@/components/Badges';
import { useAuth } from '@/state/auth';
import * as api from '@/api/endpoints';
import type { DaySummary, DayTotals } from '@/api/types';
import { formatInt, formatTime } from '@/utils/format';
import { colors, radius, space } from '@/theme/tokens';

const WEEKDAY_LETTERS = ['M', 'T', 'W', 'T', 'F', 'S', 'S']; // Monday-first
const WEEKDAY_SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const CHART_HEIGHT = 118;
const HISTORY_DAYS = 63; // look-back window for the logging streak
/** A day counts as "on target" when calories land within +10% of the goal. */
const ON_TARGET_MULT = 1.1;

// ---- local-date helpers (avoid the UTC shift of toISOString) -------------

function toISO(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}
function fromISO(iso: string): Date {
  return new Date(`${iso}T00:00:00`);
}
function addDays(d: Date, n: number): Date {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
}
/** Monday of the week containing `d`. */
function startOfWeekMonday(d: Date): Date {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const mondayIndex = (x.getDay() + 6) % 7; // Mon=0 … Sun=6
  return addDays(x, -mondayIndex);
}

function fmtRange(startISO: string, endISO: string): string {
  const s = fromISO(startISO);
  const e = fromISO(endISO);
  const sm = MONTHS[s.getMonth()];
  const em = MONTHS[e.getMonth()];
  return s.getMonth() === e.getMonth()
    ? `${sm} ${s.getDate()} – ${e.getDate()}`
    : `${sm} ${s.getDate()} – ${em} ${e.getDate()}`;
}
function fmtDayLabel(iso: string): string {
  const d = fromISO(iso);
  return `${WEEKDAY_SHORT[d.getDay()]}, ${MONTHS[d.getMonth()]} ${d.getDate()}`;
}

function sumField(days: DaySummary[], key: 'total_calories' | 'total_protein_g' | 'total_fat_g' | 'total_carbs_g'): number {
  return days.reduce((acc, d) => acc + (d[key] ?? 0), 0);
}
function isLogged(d: DaySummary): boolean {
  return d.meals.length > 0 || d.total_calories > 0;
}

/** Consecutive days (ending today) with at least one logged meal. Today not yet
 *  logged doesn't break the streak — we count from yesterday in that case. */
function computeStreak(history: DayTotals[], todayISO: string): number {
  const logged = new Set(history.filter((h) => h.meal_count > 0).map((h) => h.date));
  let cursor = fromISO(todayISO);
  if (!logged.has(todayISO)) cursor = addDays(cursor, -1);
  let count = 0;
  while (logged.has(toISO(cursor))) {
    count += 1;
    cursor = addDays(cursor, -1);
  }
  return count;
}

interface StatTileProps {
  label: string;
  value: string;
  sub?: string | null;
}
function StatTile({ label, value, sub }: StatTileProps) {
  return (
    <View style={styles.statTile}>
      <AppText variant="overline" color={colors.inkFaint}>
        {label}
      </AppText>
      <AppText variant="macroValue" style={styles.statValue}>
        {value}
      </AppText>
      {sub ? (
        <AppText variant="caption" color={colors.inkFaint}>
          {sub}
        </AppText>
      ) : null}
    </View>
  );
}

export default function WeekScreen() {
  const router = useRouter();
  const { profile } = useAuth();

  const today = useMemo(() => new Date(), []);
  const todayISO = useMemo(() => toISO(today), [today]);
  const currentWeekStart = useMemo(() => startOfWeekMonday(today), [today]);

  // 0 = current week, negative = weeks in the past. The future is out of reach.
  const [weekOffset, setWeekOffset] = useState(0);
  const [weeks, setWeeks] = useState<Record<string, DaySummary[]>>({});
  const [history, setHistory] = useState<DayTotals[]>([]);
  const [selected, setSelected] = useState<string>(todayISO);
  const [loadingWeek, setLoadingWeek] = useState(true);

  const viewWeekStart = useMemo(() => addDays(currentWeekStart, weekOffset * 7), [currentWeekStart, weekOffset]);
  const viewStartISO = useMemo(() => toISO(viewWeekStart), [viewWeekStart]);
  const dates = useMemo(() => Array.from({ length: 7 }, (_, i) => toISO(addDays(viewWeekStart, i))), [viewWeekStart]);
  const isCurrentWeek = weekOffset === 0;
  const canGoForward = weekOffset < 0;

  const weeksRef = useRef(weeks);
  weeksRef.current = weeks;

  const loadWeek = useCallback(async (startISO: string) => {
    if (!weeksRef.current[startISO]) setLoadingWeek(true);
    try {
      const days = await api.getWeek(startISO);
      setWeeks((prev) => ({ ...prev, [startISO]: days }));
    } finally {
      setLoadingWeek(false);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    const start = toISO(addDays(today, -(HISTORY_DAYS - 1)));
    try {
      const rows = await api.getHistory(start, todayISO);
      setHistory(rows);
    } catch {
      // streak is best-effort; leave prior value on failure
    }
  }, [today, todayISO]);

  // Fetch the viewed week whenever it changes.
  useEffect(() => {
    void loadWeek(viewStartISO);
  }, [viewStartISO, loadWeek]);

  // Refresh the current week + streak whenever the tab regains focus (a meal
  // may have been logged elsewhere). Past weeks are immutable, so no refetch.
  useFocusEffect(
    useCallback(() => {
      void loadHistory();
      void loadWeek(toISO(currentWeekStart));
    }, [loadHistory, loadWeek, currentWeekStart]),
  );

  // When the week's data arrives (or we navigate), keep the selection sensible:
  // don't clobber a manual pick inside the week; otherwise default to today (this
  // week) or the most recent logged day (past weeks).
  useEffect(() => {
    const days = weeks[viewStartISO];
    if (!days || dates.includes(selected)) return;
    const logged = days.filter(isLogged);
    const fallback = dates[dates.length - 1] ?? todayISO;
    const pick = isCurrentWeek
      ? dates.includes(todayISO)
        ? todayISO
        : fallback
      : logged.length
        ? logged[logged.length - 1].date
        : fallback;
    setSelected(pick);
  }, [weeks, viewStartISO, dates, selected, isCurrentWeek, todayISO]);

  const goPrev = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    setWeekOffset((o) => o - 1);
  }, []);
  const goNext = useCallback(() => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    setWeekOffset((o) => Math.min(0, o + 1));
  }, []);

  // Horizontal swipe = change week; vertical stays with the scroll view.
  const swipe = useMemo(
    () =>
      Gesture.Pan()
        .activeOffsetX([-20, 20])
        .failOffsetY([-14, 14])
        .runOnJS(true)
        .onEnd((e) => {
          if (e.translationX > 45) goPrev();
          else if (e.translationX < -45 && canGoForward) goNext();
        }),
    [goPrev, goNext, canGoForward],
  );

  const target = profile?.target_calories ?? 0;
  const hasTarget = target > 0;
  const weekDays = weeks[viewStartISO] ?? [];
  const loggedDays = weekDays.filter(isLogged);
  const maxCal = Math.max(target, ...weekDays.map((d) => d.total_calories ?? 0), 1);
  const goalY = hasTarget ? Math.min(CHART_HEIGHT, (target / maxCal) * CHART_HEIGHT) : 0;

  const avg = (key: Parameters<typeof sumField>[1]) =>
    loggedDays.length ? Math.round(sumField(loggedDays, key) / loggedDays.length) : 0;
  const avgCal = avg('total_calories');
  const avgP = avg('total_protein_g');
  const avgF = avg('total_fat_g');
  const avgC = avg('total_carbs_g');

  const onTargetCount = hasTarget
    ? loggedDays.filter((d) => d.total_calories <= target * ON_TARGET_MULT).length
    : 0;

  const streak = useMemo(() => computeStreak(history, todayISO), [history, todayISO]);
  const selectedDay = weekDays.find((d) => d.date === selected);

  const proteinTarget = profile?.target_protein_g ?? 0;
  const fatTarget = profile?.target_fat_g ?? 0;
  const carbsTarget = profile?.target_carbs_g ?? 0;

  return (
    <Screen scroll>
      <View style={styles.header}>
        <AppText variant="overline" color={colors.inkMuted}>
          Insights
        </AppText>
        <AppText variant="h1" style={styles.title}>
          Your week
        </AppText>
      </View>

      <GestureDetector gesture={swipe}>
        <View>
          <Card>
          <View style={styles.nav}>
            <Pressable onPress={goPrev} hitSlop={12} style={styles.navBtn}>
              <ChevronLeft size={22} color={colors.inkMuted} strokeWidth={1.75} />
            </Pressable>
            <View style={styles.navCenter}>
              <AppText variant="bodyStrong">
                {isCurrentWeek ? 'This week' : fmtRange(dates[0] ?? viewStartISO, dates[6] ?? viewStartISO)}
              </AppText>
              <AppText variant="caption" color={colors.inkFaint}>
                {isCurrentWeek ? fmtRange(dates[0] ?? viewStartISO, dates[6] ?? viewStartISO) : `${loggedDays.length}/7 days logged`}
              </AppText>
            </View>
            <Pressable onPress={goNext} hitSlop={12} disabled={!canGoForward} style={styles.navBtn}>
              <ChevronRight
                size={22}
                color={canGoForward ? colors.inkMuted : colors.hairlineStrong}
                strokeWidth={1.75}
              />
            </Pressable>
          </View>

          <View style={styles.chart}>
            {hasTarget ? (
              <View pointerEvents="none" style={[styles.goalLine, { top: CHART_HEIGHT - goalY }]} />
            ) : null}
            {dates.map((d, i) => {
              const day = weekDays.find((x) => x.date === d);
              const cal = day?.total_calories ?? 0;
              const h = cal > 0 ? Math.max(6, (cal / maxCal) * CHART_HEIGHT) : 0;
              const isSel = d === selected;
              const isToday = d === todayISO;
              const isFuture = d > todayISO;
              const overTarget = hasTarget && cal > target * ON_TARGET_MULT;
              const barColor = overTarget
                ? colors.terracottaText
                : isSel
                  ? colors.terracotta
                  : colors.terracottaSoft;
              const labelColor = isSel
                ? colors.ink
                : isFuture
                  ? colors.hairlineStrong
                  : isToday
                    ? colors.inkMuted
                    : colors.inkFaint;
              return (
                <Pressable key={d} style={styles.barCol} onPress={() => setSelected(d)} disabled={isFuture}>
                  <View style={styles.barTrack}>
                    {h > 0 ? <View style={[styles.bar, { height: h, backgroundColor: barColor }]} /> : null}
                  </View>
                  <AppText variant="overline" color={labelColor}>
                    {WEEKDAY_LETTERS[i]}
                  </AppText>
                  <AppText variant="caption" color={isSel ? colors.ink : isFuture ? colors.hairlineStrong : colors.inkFaint}>
                    {fromISO(d).getDate()}
                  </AppText>
                </Pressable>
              );
            })}
          </View>

          {hasTarget ? (
            <AppText variant="caption" color={colors.inkMuted} center style={styles.goalCaption}>
              Goal · {formatInt(target)} kcal/day
            </AppText>
          ) : null}
          </Card>
        </View>
      </GestureDetector>

      {/* Weekly averages (over the days you logged) */}
      <Card flat style={styles.statsCard}>
        <View style={styles.statsRow}>
          <StatTile label="Avg kcal" value={loggedDays.length ? formatInt(avgCal) : '—'} sub={hasTarget ? `of ${formatInt(target)}` : null} />
          <StatTile label="Protein" value={loggedDays.length ? `${avgP}g` : '—'} sub={proteinTarget ? `of ${Math.round(proteinTarget)}g` : null} />
          <StatTile label="Fat" value={loggedDays.length ? `${avgF}g` : '—'} sub={fatTarget ? `of ${Math.round(fatTarget)}g` : null} />
          <StatTile label="Carbs" value={loggedDays.length ? `${avgC}g` : '—'} sub={carbsTarget ? `of ${Math.round(carbsTarget)}g` : null} />
        </View>
        <AppText variant="caption" color={colors.inkFaint} style={styles.statsFootnote}>
          {loggedDays.length ? `Average per logged day (${loggedDays.length} of 7)` : 'No meals logged this week yet'}
        </AppText>
      </Card>

      {/* Streak + on-target dots */}
      <Card flat style={styles.streakCard}>
        <View style={styles.streakLeft}>
          <View style={styles.flameWrap}>
            <Flame size={22} color={streak > 0 ? colors.terracotta : colors.inkFaint} strokeWidth={1.75} />
          </View>
          <View style={styles.streakText}>
            <AppText variant="bodyStrong">
              {streak > 0 ? `${streak}-day streak` : 'No streak yet'}
            </AppText>
            <AppText variant="caption" color={colors.inkFaint}>
              {streak > 0 ? 'Days in a row you logged' : 'Log a meal today to start one'}
            </AppText>
          </View>
        </View>
        <View style={styles.dotsWrap}>
          <View style={styles.dotsRow}>
            {dates.map((d) => {
              const day = weekDays.find((x) => x.date === d);
              const logged = day ? isLogged(day) : false;
              const onTarget = logged && hasTarget && (day?.total_calories ?? 0) <= target * ON_TARGET_MULT;
              const dotColor = !logged
                ? colors.hairlineStrong
                : !hasTarget
                  ? colors.ink
                  : onTarget
                    ? colors.success
                    : colors.terracotta;
              return <View key={d} style={[styles.dot, { backgroundColor: dotColor }]} />;
            })}
          </View>
          <AppText variant="caption" color={colors.inkFaint}>
            {hasTarget ? `${onTargetCount}/7 in goal` : `${loggedDays.length}/7 logged`}
          </AppText>
        </View>
      </Card>

      <View style={styles.dayHeader}>
        <AppText variant="overline" color={colors.inkMuted}>
          {selected === todayISO ? 'Today' : fmtDayLabel(selected)}
        </AppText>
        {selectedDay && isLogged(selectedDay) ? (
          <AppText variant="caption" color={colors.inkFaint}>
            {formatInt(selectedDay.total_calories)} kcal · {Math.round(selectedDay.total_protein_g)}g P
          </AppText>
        ) : null}
      </View>

      {loadingWeek && !selectedDay ? (
        <View style={styles.loading}>
          <ActivityIndicator color={colors.terracotta} />
        </View>
      ) : !selectedDay || selectedDay.meals.length === 0 ? (
        <Card flat style={styles.emptyDay}>
          <AppText variant="body" color={colors.inkMuted} center>
            No meals logged on this day.
          </AppText>
        </Card>
      ) : (
        <Card padded={false} style={styles.mealsCard}>
          {selectedDay.meals.map((m, i) => (
            <Pressable
              key={m.id}
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
              style={({ pressed }) => [styles.mealRow, pressed && styles.pressed]}
            >
              {i > 0 ? <View style={styles.sep} /> : null}
              <View style={styles.mealInfo}>
                <AppText variant="bodyStrong" numberOfLines={1}>
                  {m.description_user}
                </AppText>
                <View style={styles.badgeRow}>
                  <AppText variant="caption" color={colors.inkMuted}>
                    {formatTime(m.eaten_at)}
                  </AppText>
                  {m.source ? <SourceBadge source={m.source} /> : null}
                  {m.accuracy_level ? <AccuracyBadge level={m.accuracy_level} /> : null}
                </View>
              </View>
              <AppText variant="title">{formatInt(m.calories)}</AppText>
            </Pressable>
          ))}
        </Card>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { marginTop: space.sm, marginBottom: space.lg },
  title: { marginTop: space.xs },

  nav: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: space.md },
  navBtn: { padding: space.xs },
  navCenter: { alignItems: 'center', gap: 2 },

  chart: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    height: CHART_HEIGHT + 36,
    position: 'relative',
  },
  goalLine: {
    position: 'absolute',
    left: 0,
    right: 0,
    height: 0,
    borderTopWidth: 1,
    borderStyle: 'dashed',
    borderColor: colors.hairlineStrong,
  },
  barCol: { flex: 1, alignItems: 'center', gap: 4 },
  barTrack: { height: CHART_HEIGHT, justifyContent: 'flex-end' },
  bar: { width: 22, borderRadius: radius.sm },
  goalCaption: { marginTop: space.md },

  statsCard: { marginTop: space.base },
  statsRow: { flexDirection: 'row', justifyContent: 'space-between' },
  statTile: { flex: 1, alignItems: 'center', gap: 2 },
  statValue: { marginTop: 2 },
  statsFootnote: { marginTop: space.md, textAlign: 'center' },

  streakCard: {
    marginTop: space.base,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.md,
  },
  streakLeft: { flexDirection: 'row', alignItems: 'center', gap: space.md, flex: 1 },
  flameWrap: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: colors.terracottaSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  streakText: { flex: 1, gap: 2 },
  dotsWrap: { alignItems: 'flex-end', gap: 6 },
  dotsRow: { flexDirection: 'row', gap: 6 },
  dot: { width: 8, height: 8, borderRadius: radius.pill },

  dayHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: space.xl,
    marginBottom: space.sm,
  },
  loading: { paddingVertical: space.xxl, alignItems: 'center' },
  emptyDay: { paddingVertical: space.xl },
  mealsCard: { overflow: 'hidden' },
  mealRow: { flexDirection: 'row', alignItems: 'center', gap: space.base, padding: space.base },
  pressed: { backgroundColor: colors.surfaceAlt },
  mealInfo: { flex: 1, gap: 4 },
  badgeRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexWrap: 'wrap' },
  sep: { position: 'absolute', top: 0, left: space.base, right: 0, height: StyleSheet.hairlineWidth, backgroundColor: colors.hairline },
});
