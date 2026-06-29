import { useCallback, useState } from 'react';
import { View, StyleSheet, Pressable, ActivityIndicator } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { SourceBadge, AccuracyBadge } from '@/components/Badges';
import { useAuth } from '@/state/auth';
import * as api from '@/api/endpoints';
import type { DaySummary } from '@/api/types';
import { formatInt, formatTime } from '@/utils/format';
import { colors, radius, space } from '@/theme/tokens';

const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const CHART_HEIGHT = 110;

function lastNDates(n: number): string[] {
  const out: string[] = [];
  const today = new Date();
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

function dayOfWeek(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  return WEEKDAYS[d.getDay()] ?? '';
}
function dayOfMonth(iso: string): number {
  return new Date(`${iso}T00:00:00`).getDate();
}

export default function WeekScreen() {
  const router = useRouter();
  const { profile } = useAuth();
  const dates = lastNDates(7);
  const todayIso = dates[dates.length - 1] ?? '';
  const [days, setDays] = useState<Record<string, DaySummary>>({});
  const [selected, setSelected] = useState<string>(todayIso);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const results = await Promise.all(dates.map((d) => api.getToday(d)));
      const map: Record<string, DaySummary> = {};
      dates.forEach((d, i) => {
        const r = results[i];
        if (r) map[d] = { ...r, date: d };
      });
      setDays(map);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const target = profile?.target_calories ?? 0;
  const maxCal = Math.max(target, ...dates.map((d) => days[d]?.total_calories ?? 0), 1);
  const selectedDay = days[selected];

  return (
    <Screen scroll>
      <View style={styles.header}>
        <AppText variant="overline" color={colors.inkMuted}>
          Last 7 days
        </AppText>
        <AppText variant="h1" style={styles.title}>
          Your week
        </AppText>
      </View>

      <Card>
        <View style={styles.chart}>
          {dates.map((d) => {
            const cal = days[d]?.total_calories ?? 0;
            const h = Math.max(6, (cal / maxCal) * CHART_HEIGHT);
            const isSel = d === selected;
            const overTarget = target > 0 && cal > target;
            return (
              <Pressable key={d} style={styles.barCol} onPress={() => setSelected(d)}>
                <View style={styles.barTrack}>
                  <View
                    style={[
                      styles.bar,
                      {
                        height: h,
                        backgroundColor: overTarget
                          ? colors.terracottaText
                          : isSel
                            ? colors.terracotta
                            : colors.terracottaSoft,
                      },
                    ]}
                  />
                </View>
                <AppText variant="overline" color={isSel ? colors.ink : colors.inkFaint}>
                  {dayOfWeek(d)}
                </AppText>
                <AppText variant="caption" color={isSel ? colors.ink : colors.inkFaint}>
                  {dayOfMonth(d)}
                </AppText>
              </Pressable>
            );
          })}
        </View>
        {target > 0 ? (
          <AppText variant="caption" color={colors.inkMuted} center style={styles.targetLine}>
            Goal · {formatInt(target)} kcal/day
          </AppText>
        ) : null}
      </Card>

      <View style={styles.dayHeader}>
        <AppText variant="overline" color={colors.inkMuted}>
          {selected === todayIso ? 'Today' : selected}
        </AppText>
        {selectedDay ? (
          <AppText variant="caption" color={colors.inkFaint}>
            {formatInt(selectedDay.total_calories)} kcal · {Math.round(selectedDay.total_protein_g)}g P
          </AppText>
        ) : null}
      </View>

      {loading && !selectedDay ? (
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
  chart: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between', height: CHART_HEIGHT + 36 },
  barCol: { flex: 1, alignItems: 'center', gap: 4 },
  barTrack: { height: CHART_HEIGHT, justifyContent: 'flex-end' },
  bar: { width: 22, borderRadius: radius.sm },
  targetLine: { marginTop: space.md },
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
