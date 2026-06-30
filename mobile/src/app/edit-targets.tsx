import { useMemo, useState } from 'react';
import { View, StyleSheet, TextInput, Pressable, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { ChevronLeft } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { useAuth } from '@/state/auth';
import * as api from '@/api/endpoints';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';

/** Parse a user-typed number; '' / junk -> 0, never negative. */
function toNum(s: string): number {
  const n = Math.round(Number(s.replace(',', '.')));
  return Number.isFinite(n) && n > 0 ? n : 0;
}

function initial(v: number | null | undefined): string {
  return v ? String(Math.round(v)) : '';
}

function Field({
  label,
  unit,
  value,
  onChangeText,
  tint,
}: {
  label: string;
  unit: string;
  value: string;
  onChangeText: (t: string) => void;
  tint?: string;
}) {
  return (
    <View style={styles.field}>
      <AppText variant="overline" color={tint ?? colors.inkMuted}>
        {label}
      </AppText>
      <View style={styles.inputWrap}>
        <TextInput
          style={styles.input}
          value={value}
          onChangeText={onChangeText}
          keyboardType="number-pad"
          placeholder="0"
          placeholderTextColor={colors.inkFaint}
          maxLength={5}
          selectTextOnFocus
        />
        <AppText variant="caption" color={colors.inkFaint}>
          {unit}
        </AppText>
      </View>
    </View>
  );
}

export default function EditTargetsScreen() {
  const router = useRouter();
  const { profile, applyProfile } = useAuth();

  const [calories, setCalories] = useState(initial(profile?.target_calories));
  const [protein, setProtein] = useState(initial(profile?.target_protein_g));
  const [carbs, setCarbs] = useState(initial(profile?.target_carbs_g));
  const [fat, setFat] = useState(initial(profile?.target_fat_g));
  const [saving, setSaving] = useState(false);

  // Calories implied by the macro split, so the user can sanity-check that the
  // numbers roughly add up (4/4/9 kcal per gram).
  const macroKcal = useMemo(
    () => toNum(protein) * 4 + toNum(carbs) * 4 + toNum(fat) * 9,
    [protein, carbs, fat],
  );
  const cals = toNum(calories);
  const mismatch = cals > 0 && macroKcal > 0 && Math.abs(macroKcal - cals) > Math.max(80, cals * 0.1);

  const onSave = async () => {
    if (cals <= 0) {
      Alert.alert('Enter your calorie target', 'Daily calories must be greater than zero.');
      return;
    }
    setSaving(true);
    try {
      const updated = await api.updateMe({
        target_calories: cals,
        target_protein_g: toNum(protein),
        target_carbs_g: toNum(carbs),
        target_fat_g: toNum(fat),
      });
      applyProfile(updated);
      router.back();
    } catch {
      Alert.alert('Could not save', 'Please check your connection and try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={26} color={colors.inkMuted} strokeWidth={1.5} />
        </Pressable>
        <AppText variant="overline" color={colors.inkMuted}>
          Edit targets
        </AppText>
        <View style={{ width: 26 }} />
      </View>

      <AppText variant="h1" style={styles.title}>
        Set your targets
      </AppText>
      <AppText variant="body" color={colors.inkMuted} style={styles.subtitle}>
        Enter your daily goals by hand. This overrides the values calculated from the questionnaire.
      </AppText>

      <Card style={styles.card}>
        <Field label="Calories" unit="kcal" value={calories} onChangeText={setCalories} tint={colors.terracottaText} />
        {macroKcal > 0 ? (
          <AppText variant="caption" color={mismatch ? colors.warning : colors.inkFaint}>
            ≈ {macroKcal} kcal from macros{mismatch ? ' — these don’t quite match your calories' : ''}
          </AppText>
        ) : null}
        <View style={styles.sep} />
        <Field label="Protein" unit="g" value={protein} onChangeText={setProtein} tint={colors.protein} />
        <Field label="Carbs" unit="g" value={carbs} onChangeText={setCarbs} tint={colors.carbs} />
        <Field label="Fat" unit="g" value={fat} onChangeText={setFat} tint={colors.fat} />
      </Card>

      <View style={styles.actions}>
        <Button label="Save targets" loading={saving} onPress={onSave} />
        <Button
          label="Use the questionnaire instead"
          variant="ghost"
          haptic={false}
          onPress={() => router.replace('/(onboarding)/goal')}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: space.sm,
  },
  title: { marginTop: space.base },
  subtitle: { marginTop: space.xs, marginBottom: space.lg },
  card: { gap: space.base },
  field: { gap: space.xs },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.sm,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.md,
    paddingHorizontal: space.base,
    minHeight: 52,
  },
  input: {
    flex: 1,
    fontFamily: fonts.serifSemibold,
    fontSize: 22,
    color: colors.ink,
    fontVariant: ['tabular-nums'],
  },
  sep: { height: StyleSheet.hairlineWidth, backgroundColor: colors.hairline },
  actions: { marginTop: 'auto', paddingTop: space.xl, gap: space.sm },
});
