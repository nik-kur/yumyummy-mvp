/**
 * S11 Try-it demo log — 3 preset meals the user can tap to see the scan result.
 */
import { useState } from 'react';
import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { Zap } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Card } from '@/components/Card';
import { useIntro } from '@/state/introContext';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';

interface DemoMeal {
  id: string;
  text: string;
  result: { name: string; kcal: number; p: number; f: number; c: number; source: string };
}

const DEMOS: DemoMeal[] = [
  {
    id: 'latte',
    text: 'Oat milk latte, grande',
    result: { name: 'Oat Milk Latte (Grande)', kcal: 270, p: 5, f: 7, c: 47, source: 'Starbucks menu' },
  },
  {
    id: 'chicken',
    text: 'Grilled chicken bowl with rice',
    result: { name: 'Grilled Chicken Rice Bowl', kcal: 520, p: 38, f: 12, c: 64, source: 'USDA + recipe est.' },
  },
  {
    id: 'snack',
    text: 'Kind bar dark chocolate nuts',
    result: { name: 'KIND Bar (Dark Choc.)', kcal: 200, p: 6, f: 15, c: 17, source: 'Kind nutrition label' },
  },
];

export default function TryItScreen() {
  const router = useRouter();
  const intro = useIntro();
  const [scanned, setScanned] = useState<string | null>(null);
  const demo = DEMOS.find((d) => d.id === scanned);

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.header}>
        <AppText variant="overline" color={colors.inkMuted}>Step 8 of 8</AppText>
        <AppText variant="h1" style={s.title}>Try it — tap a meal</AppText>
        <AppText variant="body" color={colors.inkMuted}>
          See how fast YumYummy finds the real numbers.
        </AppText>
      </View>

      <View style={s.presets}>
        {DEMOS.map((d) => (
          <Pressable
            key={d.id}
            onPress={() => {
              setScanned(d.id);
              track('tryit_interacted', { meal: d.id });
            }}
            style={[s.preset, scanned === d.id && s.presetActive]}
          >
            <Zap size={16} color={colors.terracotta} strokeWidth={1.5} />
            <AppText variant="body" style={s.presetText}>{d.text}</AppText>
          </Pressable>
        ))}
      </View>

      {demo && (
        <Card style={s.resultCard}>
          <AppText variant="title">{demo.result.name}</AppText>
          <View style={s.macroRow}>
            <View style={s.macro}>
              <AppText variant="h2">{demo.result.kcal}</AppText>
              <AppText variant="caption" color={colors.inkMuted}>kcal</AppText>
            </View>
            <View style={s.macro}>
              <AppText variant="macroValue" color={colors.protein}>{demo.result.p}g</AppText>
              <AppText variant="caption" color={colors.inkMuted}>protein</AppText>
            </View>
            <View style={s.macro}>
              <AppText variant="macroValue" color={colors.fat}>{demo.result.f}g</AppText>
              <AppText variant="caption" color={colors.inkMuted}>fat</AppText>
            </View>
            <View style={s.macro}>
              <AppText variant="macroValue" color={colors.carbs}>{demo.result.c}g</AppText>
              <AppText variant="caption" color={colors.inkMuted}>carbs</AppText>
            </View>
          </View>
          <AppText variant="caption" color={colors.infoBlue}>
            Source: {demo.result.source}
          </AppText>
        </Card>
      )}

      <Button
        label="Build my plan"
        variant="brand"
        disabled={!scanned}
        onPress={() => {
          track('onboarding_screen_completed', { screen: 'S11_try_it' });
          const goal = intro.goal_type;
          if (goal === 'lose' || goal === 'gain') {
            router.push('/(intro)/target-pace');
          } else {
            router.push('/(intro)/loader');
          }
        }}
        style={s.cta}
      />
    </Screen>
  );
}

const s = StyleSheet.create({
  header: { marginTop: space.xl, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  presets: { gap: space.md, marginBottom: space.lg },
  preset: {
    flexDirection: 'row', alignItems: 'center', gap: space.md,
    backgroundColor: colors.surface, borderRadius: radius.lg,
    borderWidth: 1.5, borderColor: colors.hairline, padding: space.base,
  },
  presetActive: { borderColor: colors.terracotta },
  presetText: { flex: 1 },
  resultCard: { marginBottom: space.lg },
  macroRow: { flexDirection: 'row', justifyContent: 'space-between', marginTop: space.md, marginBottom: space.sm },
  macro: { alignItems: 'center' },
  cta: { marginTop: 'auto' },
});
