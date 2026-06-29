import { useState } from 'react';
import { View, StyleSheet, Pressable, Alert } from 'react-native';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { ChevronLeft, ShieldCheck, Trash2 } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { SourceBadge, AccuracyBadge } from '@/components/Badges';
import { useAuth } from '@/state/auth';
import * as api from '@/api/endpoints';
import type { AccuracyLevel } from '@/api/types';
import { formatInt, formatTime } from '@/utils/format';
import { colors, radius, space } from '@/theme/tokens';

function str(v: string | string[] | undefined): string {
  if (Array.isArray(v)) return v[0] ?? '';
  return v ?? '';
}
function num(v: string | string[] | undefined): number {
  return Number(str(v)) || 0;
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

export default function MealDetailScreen() {
  const router = useRouter();
  const { profile } = useAuth();
  const params = useLocalSearchParams();

  const id = num(params.id);
  const description = str(params.d);
  const calories = num(params.c);
  const protein = num(params.p);
  const fat = num(params.f);
  const carbs = num(params.cb);
  const accRaw = str(params.acc);
  const accuracy: AccuracyLevel | null =
    accRaw === 'EXACT' || accRaw === 'ESTIMATE' || accRaw === 'APPROX' ? accRaw : null;
  const source = str(params.src);
  const time = str(params.t);

  const [busy, setBusy] = useState(false);

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
        <View style={{ width: 26 }} />
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
        <View style={styles.badges}>
          {source ? <SourceBadge source={source} /> : null}
          {accuracy ? <AccuracyBadge level={accuracy} /> : null}
        </View>
      </Card>

      <View style={styles.tiles}>
        <MacroTile label="Protein" value={protein} color={colors.protein} />
        <MacroTile label="Carbs" value={carbs} color={colors.carbs} />
        <MacroTile label="Fat" value={fat} color={colors.fat} />
      </View>

      <Card flat style={styles.method}>
        <View style={styles.methodRow}>
          <ShieldCheck size={18} color={colors.infoBlue} strokeWidth={1.5} />
          <AppText variant="bodyStrong" color={colors.ink}>
            How we got this
          </AppText>
        </View>
        <AppText variant="caption" color={colors.inkMuted}>
          {source
            ? `Source: ${source}. `
            : ''}
          {accuracy
            ? `Confidence: ${accuracy.toLowerCase()}. `
            : ''}
          Numbers come from the AI workflow’s source‑checked lookup. Ingredient‑level breakdown is
          available for AI‑logged meals.
        </AppText>
      </Card>

      <View style={styles.actions}>
        <Button label="Save to My Menu" variant="secondary" loading={busy} onPress={onSave} />
        <Button
          label="Log similar"
          variant="ghost"
          haptic={false}
          onPress={() => router.push({ pathname: '/capture', params: { prefill: description } })}
        />
        <Pressable onPress={onDelete} style={styles.delete}>
          <Trash2 size={18} color={colors.error} strokeWidth={1.5} />
          <AppText variant="bodyStrong" color={colors.error}>
            Delete meal
          </AppText>
        </Pressable>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
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
  method: { marginTop: space.base, gap: space.sm, backgroundColor: colors.infoBlueSoft, borderColor: colors.infoBlueSoft },
  methodRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  actions: { marginTop: 'auto', paddingTop: space.xl, gap: space.sm },
  delete: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: space.sm, paddingVertical: space.md },
});
