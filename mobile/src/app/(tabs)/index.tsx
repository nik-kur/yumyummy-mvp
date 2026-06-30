import { useCallback, useEffect, useState } from 'react';
import { View, StyleSheet, Pressable, ActivityIndicator, Alert } from 'react-native';
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
import { formatInt, formatTime } from '@/utils/format';
import { colors, radius, space } from '@/theme/tokens';

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

function PendingRow({ item, onPress }: { item: PendingMeal; onPress: () => void }) {
  const isError = item.status === 'error';
  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.mealRow, pressed && styles.pressed]}>
      <View style={styles.mealInfo}>
        <AppText
          variant="bodyStrong"
          numberOfLines={1}
          color={isError ? colors.terracottaText : colors.ink}
        >
          {item.label}
        </AppText>
        <View style={styles.badgeRow}>
          <AppText variant="caption" color={colors.inkMuted}>
            {isError ? 'Tap to retry' : 'Analyzing on the web…'}
          </AppText>
        </View>
      </View>
      <View style={styles.mealKcal}>
        {isError ? (
          <CircleAlert size={22} color={colors.terracottaText} strokeWidth={1.5} />
        ) : (
          <ActivityIndicator color={colors.terracotta} />
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

  const load = useCallback(async () => {
    try {
      const d = await api.getToday();
      setDay(d);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

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
          'We’re checking the web for accurate calories and macros. This usually takes 1–2 minutes — your meal updates here automatically when it’s ready.',
          [{ text: 'Got it' }],
        );
      }
    },
    [retry, dismiss],
  );

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

  const meals = day?.meals ?? [];

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
              <MacroBar label="Carbs" macro="carbs" value={day?.total_carbs_g ?? 0} target={profile?.target_carbs_g} />
              <MacroBar label="Fat" macro="fat" value={day?.total_fat_g ?? 0} target={profile?.target_fat_g} />
            </View>
          </Card>

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
              glyph={'\u{1F37D}'}
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
  pressed: { backgroundColor: colors.surfaceAlt },
  mealInfo: { flex: 1, gap: 4 },
  badgeRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm, flexWrap: 'wrap' },
  mealKcal: { alignItems: 'flex-end' },
  sep: { height: StyleSheet.hairlineWidth, backgroundColor: colors.hairline, marginLeft: space.base },
});
