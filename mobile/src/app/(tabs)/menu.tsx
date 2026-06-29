import { useCallback, useState } from 'react';
import { View, StyleSheet, ActivityIndicator } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { Repeat, CircleCheck } from 'lucide-react-native';
import * as Haptics from 'expo-haptics';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { SourceBadge } from '@/components/Badges';
import { EmptyState } from '@/components/EmptyState';
import * as api from '@/api/endpoints';
import type { SavedMealListItem } from '@/api/types';
import { formatInt, todayISO } from '@/utils/format';
import { colors, radius, space } from '@/theme/tokens';

export default function MenuScreen() {
  const [items, setItems] = useState<SavedMealListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [justLogged, setJustLogged] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.getSavedMeals();
      setItems(res.items);
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const logAgain = async (item: SavedMealListItem) => {
    await api.createMeal({
      date: todayISO(),
      description_user: item.name,
      calories: item.total_calories,
      protein_g: item.total_protein_g,
      fat_g: item.total_fat_g,
      carbs_g: item.total_carbs_g,
      accuracy_level: 'ESTIMATE',
    });
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    setJustLogged(item.id);
    setTimeout(() => setJustLogged((cur) => (cur === item.id ? null : cur)), 1600);
  };

  return (
    <Screen scroll grow>
      <View style={styles.header}>
        <AppText variant="overline" color={colors.inkMuted}>
          Saved meals
        </AppText>
        <AppText variant="h1" style={styles.title}>
          My Menu
        </AppText>
        <AppText variant="body" color={colors.inkMuted}>
          Your go‑to meals — log them again in one tap.
        </AppText>
      </View>

      {loading && items.length === 0 ? (
        <View style={styles.loading}>
          <ActivityIndicator color={colors.terracotta} />
        </View>
      ) : items.length === 0 ? (
        <View style={styles.emptyWrap}>
          <EmptyState
            glyph={'\u{1F4D2}'}
            title="No saved meals yet"
            subtitle="When you log a meal you eat often, save it here for one‑tap logging."
          />
        </View>
      ) : (
        <View style={styles.list}>
          {items.map((item) => (
            <Card key={item.id} style={styles.card}>
              <View style={styles.cardTop}>
                <View style={styles.cardInfo}>
                  <AppText variant="title" numberOfLines={1}>
                    {item.name}
                  </AppText>
                  <View style={styles.macroRow}>
                    <AppText variant="caption" color={colors.protein}>
                      P {Math.round(item.total_protein_g)}g
                    </AppText>
                    <AppText variant="caption" color={colors.carbs}>
                      C {Math.round(item.total_carbs_g)}g
                    </AppText>
                    <AppText variant="caption" color={colors.fat}>
                      F {Math.round(item.total_fat_g)}g
                    </AppText>
                  </View>
                  <SourceBadge source="Estimate" />
                </View>
                <View style={styles.kcal}>
                  <AppText variant="title">{formatInt(item.total_calories)}</AppText>
                  <AppText variant="overline" color={colors.inkFaint}>
                    kcal
                  </AppText>
                </View>
              </View>

              <View style={styles.cardBottom}>
                <View style={styles.useCount}>
                  <Repeat size={14} color={colors.inkFaint} strokeWidth={1.5} />
                  <AppText variant="caption" color={colors.inkFaint}>
                    Logged {item.use_count}×
                  </AppText>
                </View>
                {justLogged === item.id ? (
                  <View style={styles.added}>
                    <CircleCheck size={18} color={colors.success} strokeWidth={1.5} />
                    <AppText variant="caption" color={colors.success}>
                      Added to today
                    </AppText>
                  </View>
                ) : (
                  <Button
                    label="Log again"
                    size="md"
                    fullWidth={false}
                    onPress={() => logAgain(item)}
                    style={styles.logBtn}
                  />
                )}
              </View>
            </Card>
          ))}
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { marginTop: space.sm, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  loading: { paddingVertical: space.xxxl, alignItems: 'center' },
  emptyWrap: { flexGrow: 1, justifyContent: 'center' },
  list: { gap: space.md },
  card: { gap: space.md },
  cardTop: { flexDirection: 'row', alignItems: 'flex-start', gap: space.base },
  cardInfo: { flex: 1, gap: space.sm },
  macroRow: { flexDirection: 'row', gap: space.base },
  kcal: { alignItems: 'flex-end' },
  cardBottom: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
    paddingTop: space.md,
  },
  useCount: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  added: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  logBtn: { paddingHorizontal: space.lg },
});
