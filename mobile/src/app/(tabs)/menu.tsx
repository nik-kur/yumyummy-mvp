import { useCallback, useState } from 'react';
import { View, StyleSheet, ActivityIndicator, Pressable, Alert } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { Repeat, CircleCheck, Pencil } from 'lucide-react-native';
import * as Haptics from 'expo-haptics';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { SourceBadge } from '@/components/Badges';
import { EmptyState } from '@/components/EmptyState';
import {
  SavedMealEditSheet,
  ItemEditSheet,
  sumItems,
  type MacroTotals,
} from '@/components/mealEdit';
import * as api from '@/api/endpoints';
import { reportJourneyEvent } from '@/state/journey';
import type { MealItem, SavedMealListItem } from '@/api/types';
import { formatInt } from '@/utils/format';
import { colors, radius, space } from '@/theme/tokens';

export default function MenuScreen() {
  const [items, setItems] = useState<SavedMealListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [justLogged, setJustLogged] = useState<number | null>(null);
  // Editing state: which saved meal is open, and (optionally) which of its
  // components is being edited in the nested sheet.
  const [editing, setEditing] = useState<SavedMealListItem | null>(null);
  const [editItemIndex, setEditItemIndex] = useState<number | null>(null);

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
    try {
      // Server-side log keeps the component breakdown and bumps use_count.
      await api.logSavedMeal(item.id);
    } catch {
      Alert.alert('Could not log', 'Please check your connection and try again.');
      return;
    }
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    void reportJourneyEvent({ type: 'log_created', source: 'saved' }).catch(() => {});
    setJustLogged(item.id);
    setItems((cur) =>
      cur.map((s) => (s.id === item.id ? { ...s, use_count: s.use_count + 1 } : s)),
    );
    setTimeout(() => setJustLogged((cur) => (cur === item.id ? null : cur)), 1600);
  };

  /** Optimistically apply the patch locally, then sync with the server. */
  const applyUpdate = async (id: number, update: Parameters<typeof api.updateSavedMeal>[1]) => {
    const before = items;
    setItems((cur) =>
      cur.map((s) => {
        if (s.id !== id) return s;
        const next = { ...s };
        if (update.name) next.name = update.name;
        if (update.items) {
          next.items = update.items;
          const t = sumItems(update.items);
          next.total_calories = t.calories;
          next.total_protein_g = t.protein;
          next.total_fat_g = t.fat;
          next.total_carbs_g = t.carbs;
        }
        if (update.total_calories != null) next.total_calories = update.total_calories;
        if (update.total_protein_g != null) next.total_protein_g = update.total_protein_g;
        if (update.total_fat_g != null) next.total_fat_g = update.total_fat_g;
        if (update.total_carbs_g != null) next.total_carbs_g = update.total_carbs_g;
        return next;
      }),
    );
    try {
      await api.updateSavedMeal(id, update);
    } catch {
      setItems(before);
      Alert.alert('Could not save changes', 'Please check your connection and try again.');
    }
  };

  const onSheetSave = (name: string, totals: MacroTotals | null) => {
    if (!editing) return;
    const id = editing.id;
    setEditing(null);
    const update: Parameters<typeof api.updateSavedMeal>[1] = { name };
    if (totals) {
      update.total_calories = totals.calories;
      update.total_protein_g = totals.protein;
      update.total_fat_g = totals.fat;
      update.total_carbs_g = totals.carbs;
    }
    void applyUpdate(id, update);
  };

  const onDelete = () => {
    if (!editing) return;
    const target = editing;
    Alert.alert('Remove from My Menu', `Remove “${target.name}”? Meals already in your diary stay.`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: async () => {
          setEditing(null);
          const before = items;
          setItems((cur) => cur.filter((s) => s.id !== target.id));
          try {
            await api.deleteSavedMeal(target.id);
          } catch {
            setItems(before);
            Alert.alert('Could not remove', 'Please check your connection and try again.');
          }
        },
      },
    ]);
  };

  const editingItems: MealItem[] = editing?.items ?? [];

  const onItemSave = (next: MealItem) => {
    if (!editing || editItemIndex == null) return;
    const nextItems = editingItems.map((it, i) => (i === editItemIndex ? next : it));
    setEditItemIndex(null);
    setEditing((cur) => (cur ? { ...cur, items: nextItems } : cur));
    void applyUpdate(editing.id, { items: nextItems });
  };

  /** Confirm + remove one component (from the row's minus or the nested sheet). */
  const onItemRemoveAt = (idx: number) => {
    if (!editing) return;
    const target = editing;
    if (editingItems.length <= 1) {
      setEditItemIndex(null);
      Alert.alert('Last component', 'To remove the whole meal, use “Remove from My Menu”.');
      return;
    }
    Alert.alert('Remove component', `Remove “${editingItems[idx]?.name}” from this meal?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: () => {
          const nextItems = editingItems.filter((_, i) => i !== idx);
          setEditItemIndex(null);
          setEditing((cur) => (cur ? { ...cur, items: nextItems } : cur));
          void applyUpdate(target.id, { items: nextItems });
        },
      },
    ]);
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
                    <AppText variant="caption" color={colors.fat}>
                      F {Math.round(item.total_fat_g)}g
                    </AppText>
                    <AppText variant="caption" color={colors.carbs}>
                      C {Math.round(item.total_carbs_g)}g
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
                <View style={styles.cardMeta}>
                  <View style={styles.useCount}>
                    <Repeat size={14} color={colors.inkFaint} strokeWidth={1.5} />
                    <AppText variant="caption" color={colors.inkFaint}>
                      Logged {item.use_count}×
                    </AppText>
                  </View>
                  <Pressable
                    onPress={() => setEditing(item)}
                    hitSlop={8}
                    style={({ pressed }) => [styles.editBtn, pressed && styles.pressed]}
                  >
                    <Pencil size={14} color={colors.inkMuted} strokeWidth={1.5} />
                    <AppText variant="caption" color={colors.inkMuted}>
                      Edit
                    </AppText>
                  </Pressable>
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

      <SavedMealEditSheet
        visible={editing != null && editItemIndex == null}
        name={editing?.name ?? ''}
        totals={{
          calories: editing?.total_calories ?? 0,
          protein: editing?.total_protein_g ?? 0,
          fat: editing?.total_fat_g ?? 0,
          carbs: editing?.total_carbs_g ?? 0,
        }}
        items={editingItems}
        onClose={() => setEditing(null)}
        onSave={onSheetSave}
        onDelete={onDelete}
        onEditItem={(i) => setEditItemIndex(i)}
        onRemoveItem={onItemRemoveAt}
      />
      <ItemEditSheet
        visible={editItemIndex != null && editing != null}
        item={editItemIndex != null ? editingItems[editItemIndex] ?? null : null}
        onClose={() => setEditItemIndex(null)}
        onSave={onItemSave}
        onRemove={() => {
          if (editItemIndex != null) onItemRemoveAt(editItemIndex);
        }}
      />
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
  cardMeta: { flexDirection: 'row', alignItems: 'center', gap: space.base },
  useCount: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  editBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingVertical: 4,
    paddingHorizontal: space.sm,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.hairline,
    backgroundColor: colors.surfaceAlt,
  },
  pressed: { opacity: 0.6 },
  added: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  logBtn: { paddingHorizontal: space.lg },
});
