import { useEffect, useMemo, useState } from 'react';
import { View, StyleSheet, Pressable, Alert, Linking } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ChevronLeft, ShieldCheck, Trash2, Pencil, ExternalLink } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { AccuracyBadge } from '@/components/Badges';
import {
  MealEditSheet,
  ItemEditSheet,
  scaleItem,
  sumItems,
  type MacroTotals,
} from '@/components/mealEdit';
import { useAuth } from '@/state/auth';
import * as api from '@/api/endpoints';
import type { AccuracyLevel, MealItem, MealRead } from '@/api/types';
import { formatInt, formatTime } from '@/utils/format';
import { assessmentText } from '@/utils/assessment';
import { colors, radius, space } from '@/theme/tokens';

function str(v: string | string[] | undefined): string {
  if (Array.isArray(v)) return v[0] ?? '';
  return v ?? '';
}
function num(v: string | string[] | undefined): number {
  return Number(str(v)) || 0;
}

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url.replace(/^https?:\/\//, '').split('/')[0] ?? url;
  }
}

function openUrl(url: string) {
  Linking.openURL(url).catch(() => Alert.alert('Could not open link', url));
}

function MacroTile({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={styles.tile}>
      <AppText variant="h2" color={color}>
        {Math.round(value)}
        <AppText variant="caption" color={colors.inkFaint}>
          g
        </AppText>
      </AppText>
      <AppText variant="overline" color={colors.inkMuted}>
        {label}
      </AppText>
    </View>
  );
}

// Row tap now opens the component editor; the source link moved onto the
// little external-link icon so both actions stay reachable.
function ItemRow({ item, onEdit }: { item: MealItem; onEdit?: () => void }) {
  const grams = item.grams ? `${Math.round(item.grams)} g` : null;
  const macros = [
    item.protein_g != null ? `P ${Math.round(item.protein_g)}` : null,
    item.fat_g != null ? `F ${Math.round(item.fat_g)}` : null,
    item.carbs_g != null ? `C ${Math.round(item.carbs_g)}` : null,
  ]
    .filter(Boolean)
    .join(' · ');
  return (
    <Pressable
      disabled={!onEdit}
      onPress={onEdit}
      style={({ pressed }) => [styles.itemRow, pressed && onEdit ? styles.pressed : null]}
    >
      <View style={styles.itemInfo}>
        <View style={styles.itemNameRow}>
          <AppText variant="bodyStrong" numberOfLines={2} style={styles.flex}>
            {item.name}
          </AppText>
          {item.source_url ? (
            <Pressable hitSlop={10} onPress={() => item.source_url && openUrl(item.source_url)}>
              <ExternalLink size={15} color={colors.infoBlue} strokeWidth={1.5} />
            </Pressable>
          ) : null}
        </View>
        <AppText variant="caption" color={colors.inkMuted}>
          {[grams, macros].filter(Boolean).join('  ·  ')}
        </AppText>
      </View>
      {item.calories_kcal != null ? (
        <View style={styles.itemKcal}>
          <AppText variant="bodyStrong">{formatInt(item.calories_kcal)}</AppText>
          <AppText variant="overline" color={colors.inkFaint}>
            kcal
          </AppText>
        </View>
      ) : null}
    </Pressable>
  );
}

export default function MealDetailScreen() {
  const router = useRouter();
  const { profile } = useAuth();
  const params = useLocalSearchParams();

  const id = num(params.id);

  // Render instantly from the params the list passed, then hydrate the full
  // record (with ingredient breakdown + sources) from the API.
  const [meal, setMeal] = useState<MealRead | null>(null);
  const [busy, setBusy] = useState(false);
  const [repeating, setRepeating] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editItemIndex, setEditItemIndex] = useState<number | null>(null);

  useEffect(() => {
    if (!id) return;
    let alive = true;
    api
      .getMeal(id)
      .then((m) => {
        if (alive) setMeal(m);
      })
      .catch(() => {
        /* keep param-based fallback */
      });
    return () => {
      alive = false;
    };
  }, [id]);

  const description = meal?.description_user || str(params.d);
  const calories = meal?.calories ?? num(params.c);
  const protein = meal?.protein_g ?? num(params.p);
  const fat = meal?.fat_g ?? num(params.f);
  const carbs = meal?.carbs_g ?? num(params.cb);
  const accRaw = (meal?.accuracy_level ?? str(params.acc)) || '';
  const accuracy: AccuracyLevel | null =
    accRaw === 'EXACT' || accRaw === 'ESTIMATE' || accRaw === 'APPROX' ? accRaw : null;
  const time = meal?.eaten_at || str(params.t);
  const items = meal?.items ?? [];

  // De-duplicated source links: the meal-level source plus any per-item ones.
  const sources = useMemo(() => {
    const urls = new Set<string>();
    if (meal?.source_url) urls.add(meal.source_url);
    for (const it of items) if (it.source_url) urls.add(it.source_url);
    return Array.from(urls);
  }, [meal?.source_url, items]);

  // Base record for optimistic edits (params fallback until hydration lands).
  const current: MealRead = meal ?? {
    id,
    eaten_at: time,
    description_user: description,
    calories,
    protein_g: protein,
    fat_g: fat,
    carbs_g: carbs,
    accuracy_level: accuracy,
    items: [],
  };

  /** Optimistically apply `optimistic`, then reconcile with the server. */
  const applyUpdate = async (update: Parameters<typeof api.updateMeal>[1], optimistic: MealRead) => {
    if (!id) return;
    const before = meal;
    setMeal(optimistic);
    try {
      const serverMeal = await api.updateMeal(id, update);
      setMeal(serverMeal);
    } catch {
      setMeal(before);
      Alert.alert('Could not save changes', 'Please check your connection and try again.');
    }
  };

  const onEditSave = (portion: number, totals: MacroTotals) => {
    setEditOpen(false);
    const scaled = {
      calories: Math.round(calories * portion),
      protein: Math.round(protein * portion),
      fat: Math.round(fat * portion),
      carbs: Math.round(carbs * portion),
    };
    const stepperOnly =
      totals.calories === scaled.calories &&
      totals.protein === scaled.protein &&
      totals.fat === scaled.fat &&
      totals.carbs === scaled.carbs;

    if (stepperOnly && portion === 1) return; // nothing changed

    if (stepperOnly && items.length > 0) {
      // Pure portion change: rescale the components so the breakdown stays true.
      const nextItems = items.map((it) => scaleItem(it, portion));
      const t = sumItems(nextItems);
      void applyUpdate(
        { items: nextItems },
        { ...current, items: nextItems, calories: t.calories, protein_g: t.protein, fat_g: t.fat, carbs_g: t.carbs },
      );
      return;
    }
    void applyUpdate(
      {
        calories: totals.calories,
        protein_g: totals.protein,
        fat_g: totals.fat,
        carbs_g: totals.carbs,
      },
      {
        ...current,
        calories: totals.calories,
        protein_g: totals.protein,
        fat_g: totals.fat,
        carbs_g: totals.carbs,
      },
    );
  };

  const onItemSave = (next: MealItem) => {
    if (editItemIndex == null) return;
    const nextItems = items.map((it, i) => (i === editItemIndex ? next : it));
    setEditItemIndex(null);
    const t = sumItems(nextItems);
    void applyUpdate(
      { items: nextItems },
      { ...current, items: nextItems, calories: t.calories, protein_g: t.protein, fat_g: t.fat, carbs_g: t.carbs },
    );
  };

  const onItemRemove = () => {
    if (editItemIndex == null) return;
    const idx = editItemIndex;
    if (items.length <= 1) {
      setEditItemIndex(null);
      Alert.alert(
        'Last component',
        'This is the only component left. Delete the whole meal instead?',
        [
          { text: 'Cancel', style: 'cancel' },
          { text: 'Delete meal', style: 'destructive', onPress: () => onDelete() },
        ],
      );
      return;
    }
    Alert.alert('Remove component', `Remove “${items[idx]?.name}” from this meal?`, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Remove',
        style: 'destructive',
        onPress: () => {
          setEditItemIndex(null);
          const nextItems = items.filter((_, i) => i !== idx);
          const t = sumItems(nextItems);
          void applyUpdate(
            { items: nextItems },
            { ...current, items: nextItems, calories: t.calories, protein_g: t.protein, fat_g: t.fat, carbs_g: t.carbs },
          );
        },
      },
    ]);
  };

  const onRepeat = async () => {
    if (!id) return;
    setRepeating(true);
    try {
      await api.repeatMeal(id);
      Alert.alert('Logged again', 'Added to today exactly as before — no new search.');
      router.back();
    } catch {
      Alert.alert('Could not repeat', 'Please try again.');
    } finally {
      setRepeating(false);
    }
  };

  const onSave = async () => {
    setBusy(true);
    try {
      await api.createSavedMeal({
        user_id: profile?.user_id ?? 1,
        name: description,
        total_calories: calories,
        total_protein_g: protein,
        total_fat_g: fat,
        total_carbs_g: carbs,
        // Keep the breakdown so the saved meal stays editable per component.
        items,
      });
      Alert.alert('Saved to My Menu', 'Log it again anytime in one tap.');
    } catch {
      Alert.alert('Could not save', 'Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const onDelete = () =>
    Alert.alert('Delete meal', 'Remove this meal from your diary?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await api.deleteMeal(id);
          } finally {
            router.back();
          }
        },
      },
    ]);

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={26} color={colors.inkMuted} strokeWidth={1.5} />
        </Pressable>
        <AppText variant="overline" color={colors.inkMuted}>
          {time ? formatTime(time) : 'Meal'}
        </AppText>
        <Pressable onPress={() => setEditOpen(true)} hitSlop={10}>
          <Pencil size={20} color={colors.inkMuted} strokeWidth={1.5} />
        </Pressable>
      </View>

      <AppText variant="h1" style={styles.title}>
        {description || 'Meal'}
      </AppText>

      <Card style={styles.hero}>
        <AppText variant="hero" color={colors.terracotta}>
          {formatInt(calories)}
        </AppText>
        <AppText variant="overline" color={colors.inkMuted}>
          kcal
        </AppText>
        {accuracy ? (
          <View style={styles.badges}>
            <AccuracyBadge level={accuracy} />
          </View>
        ) : null}
      </Card>

      <View style={styles.tiles}>
        <MacroTile label="Protein" value={protein} color={colors.protein} />
        <MacroTile label="Fat" value={fat} color={colors.fat} />
        <MacroTile label="Carbs" value={carbs} color={colors.carbs} />
      </View>

      {items.length > 0 ? (
        <View style={styles.section}>
          <AppText variant="overline" color={colors.inkMuted} style={styles.sectionLabel}>
            Breakdown — tap to edit
          </AppText>
          <Card padded={false} style={styles.breakdownCard}>
            {items.map((it, i) => (
              <View key={`${it.name}-${i}`}>
                {i > 0 ? <View style={styles.sep} /> : null}
                <ItemRow item={it} onEdit={() => setEditItemIndex(i)} />
              </View>
            ))}
          </Card>
        </View>
      ) : null}

      <Card flat style={styles.method}>
        <View style={styles.methodRow}>
          <ShieldCheck size={18} color={colors.infoBlue} strokeWidth={1.5} />
          <AppText variant="bodyStrong" color={colors.ink}>
            How we got this
          </AppText>
        </View>
        <AppText variant="caption" color={colors.inkMuted}>
          {meal?.assessment
            ? assessmentText(meal.assessment)
            : `${accuracy ? `Confidence: ${accuracy.toLowerCase()}. ` : ''}Numbers come from the AI workflow’s source‑checked lookup.${
                sources.length === 0 && items.length === 0
                  ? ' Ingredient‑level breakdown is available for AI‑logged meals.'
                  : ''
              }`}
        </AppText>
        {sources.length > 0 ? (
          <View style={styles.sourceList}>
            <AppText variant="overline" color={colors.infoBlue}>
              {sources.length > 1 ? 'Sources' : 'Source'}
            </AppText>
            {sources.map((url) => (
              <Pressable
                key={url}
                onPress={() => openUrl(url)}
                style={({ pressed }) => [styles.sourceLink, pressed && styles.pressed]}
              >
                <AppText variant="bodyStrong" color={colors.infoBlue} numberOfLines={1} style={styles.flex}>
                  {hostnameOf(url)}
                </AppText>
                <ExternalLink size={18} color={colors.infoBlue} strokeWidth={1.75} />
              </Pressable>
            ))}
          </View>
        ) : null}
      </Card>

      <View style={styles.actions}>
        <Button label="Repeat this meal" loading={repeating} onPress={onRepeat} />
        <Button
          label="Log similar"
          variant="secondary"
          haptic={false}
          onPress={() => router.push({ pathname: '/capture', params: { prefill: description } })}
        />
        <Button label="Save to My Menu" variant="ghost" loading={busy} onPress={onSave} />
        <Pressable onPress={onDelete} style={styles.delete}>
          <Trash2 size={18} color={colors.error} strokeWidth={1.5} />
          <AppText variant="bodyStrong" color={colors.error}>
            Delete meal
          </AppText>
        </Pressable>
      </View>

      <MealEditSheet
        visible={editOpen}
        title={description || 'Edit meal'}
        initial={{ calories, protein, fat, carbs }}
        hasItems={items.length > 0}
        onClose={() => setEditOpen(false)}
        onSave={onEditSave}
      />
      <ItemEditSheet
        visible={editItemIndex != null}
        item={editItemIndex != null ? items[editItemIndex] ?? null : null}
        onClose={() => setEditItemIndex(null)}
        onSave={onItemSave}
        onRemove={onItemRemove}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  topBar: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: space.sm },
  title: { marginTop: space.base, marginBottom: space.lg },
  hero: { alignItems: 'center', paddingVertical: space.xl, gap: space.xs },
  badges: { flexDirection: 'row', gap: space.sm, marginTop: space.sm },
  tiles: { flexDirection: 'row', gap: space.md, marginTop: space.base },
  tile: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
    alignItems: 'center',
    paddingVertical: space.lg,
    gap: 2,
  },
  section: { marginTop: space.xl },
  sectionLabel: { marginBottom: space.sm },
  breakdownCard: { overflow: 'hidden' },
  itemRow: { flexDirection: 'row', alignItems: 'center', gap: space.base, padding: space.base },
  itemInfo: { flex: 1, gap: 3 },
  itemNameRow: { flexDirection: 'row', alignItems: 'center', gap: space.xs },
  itemKcal: { alignItems: 'flex-end' },
  pressed: { opacity: 0.6 },
  sep: { height: StyleSheet.hairlineWidth, backgroundColor: colors.hairline, marginLeft: space.base },
  method: { marginTop: space.xl, gap: space.sm, backgroundColor: colors.infoBlueSoft, borderColor: colors.infoBlueSoft },
  methodRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  sourceList: { marginTop: space.sm, gap: space.sm },
  sourceLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.infoBlue,
    paddingVertical: space.md,
    paddingHorizontal: space.base,
  },
  actions: { marginTop: 'auto', paddingTop: space.xl, gap: space.sm },
  delete: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.sm, paddingVertical: space.md },
});
