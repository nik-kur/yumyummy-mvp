import { useEffect, useState, type ComponentType } from 'react';
import { View, StyleSheet, Pressable, ActivityIndicator, Image } from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import {
  X,
  Flame,
  Trophy,
  Utensils,
  Zap,
  Dumbbell,
  Sunrise,
  Moon,
  Target,
  Sun,
  Notebook,
  Sparkles,
} from 'lucide-react-native';
import Animated, { ZoomIn, FadeInDown } from 'react-native-reanimated';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import * as api from '@/api/endpoints';
import type { RecapHighlight, WeeklyRecap } from '@/api/types';
import { formatInt } from '@/utils/format';
import { colors, radius, space } from '@/theme/tokens';

const BUCKETS: { key: keyof WeeklyRecap['meal_time_split']; label: string }[] = [
  { key: 'morning', label: 'Morning' },
  { key: 'midday', label: 'Midday' },
  { key: 'evening', label: 'Evening' },
  { key: 'night', label: 'Night' },
];

// ── mood art ────────────────────────────────────────────────────────────────
// A little emotional read on the week (à la Duolingo): the mascot celebrates a
// full week and turns thoughtful — never scolding — when logs are sparse.

const MOOD_ART = {
  stellar: require('../../assets/recap/mood_stellar.png'),
  great: require('../../assets/recap/mood_great.png'),
  okay: require('../../assets/recap/mood_okay.png'),
  quiet: require('../../assets/recap/mood_quiet.png'),
} as const;

function moodFor(recap: WeeklyRecap): keyof typeof MOOD_ART {
  if (recap.days_logged >= 6) return 'stellar';
  if (recap.days_logged >= 4) return 'great';
  if (recap.days_logged >= 2) return 'okay';
  return 'quiet';
}

// ── highlights ──────────────────────────────────────────────────────────────

type IconType = ComponentType<{ size?: number; color?: string; strokeWidth?: number }>;

const HIGHLIGHT_ICONS: Record<string, IconType> = {
  trophy: Trophy,
  utensils: Utensils,
  zap: Zap,
  dumbbell: Dumbbell,
  sunrise: Sunrise,
  moon: Moon,
  target: Target,
  flame: Flame,
  sun: Sun,
  notebook: Notebook,
};

function HighlightCard({ highlight, index }: { highlight: RecapHighlight; index: number }) {
  const Icon = HIGHLIGHT_ICONS[highlight.icon] ?? Sparkles;
  return (
    <Animated.View entering={FadeInDown.delay(150 + index * 90).springify().damping(16)}>
      <Card flat style={styles.highlightCard}>
        <View style={styles.highlightIcon}>
          <Icon size={20} color={colors.terracotta} strokeWidth={1.75} />
        </View>
        <View style={styles.flex}>
          <AppText variant="overline" color={colors.inkFaint}>
            {highlight.title}
          </AppText>
          <AppText variant="title" style={styles.highlightValue}>
            {highlight.value}
          </AppText>
          {highlight.caption ? (
            <AppText variant="caption" color={colors.inkFaint}>
              {highlight.caption}
            </AppText>
          ) : null}
        </View>
      </Card>
    </Animated.View>
  );
}

// ── screen ──────────────────────────────────────────────────────────────────

export default function RecapScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ week?: string }>();
  const week = typeof params.week === 'string' ? params.week : undefined;

  const [recap, setRecap] = useState<WeeklyRecap | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setFailed(false);
    (async () => {
      try {
        const data = await api.getRecap(week);
        if (active) setRecap(data);
      } catch {
        if (active) setFailed(true);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [week]);

  const hasData = !!recap?.has_data;
  const target = recap?.target_calories ?? 0;
  const highlights = recap?.highlights ?? [];

  return (
    <Screen scroll edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} hitSlop={12} style={styles.iconBtn}>
          <X size={24} color={colors.inkMuted} strokeWidth={1.75} />
        </Pressable>
        <AppText variant="overline" color={colors.inkMuted}>
          Week in Recap
        </AppText>
        <View style={styles.iconBtn} />
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator color={colors.terracotta} />
        </View>
      ) : failed || !recap ? (
        <Card flat style={styles.stateCard}>
          <AppText variant="body" color={colors.inkMuted} center>
            We couldn’t load your recap. Please try again in a moment.
          </AppText>
        </Card>
      ) : (
        <View style={styles.content}>
          <Card style={styles.hero}>
            <View style={styles.heroTop}>
              <View style={styles.flex}>
                <AppText variant="eyebrow" color={colors.terracottaSoft}>
                  {recap.date_range}
                </AppText>
                {hasData ? (
                  <>
                    <View style={styles.heroNumRow}>
                      <AppText variant="hero" color={colors.white}>
                        {recap.days_logged}
                      </AppText>
                      <AppText variant="h2" color={colors.terracottaSoft} style={styles.heroDenom}>
                        /7
                      </AppText>
                    </View>
                    <AppText variant="bodyStrong" color={colors.white}>
                      days logged
                    </AppText>
                    {recap.streak > 0 ? (
                      <View style={styles.heroStreak}>
                        <Flame size={16} color={colors.white} strokeWidth={2} />
                        <AppText variant="caption" color={colors.white}>
                          {recap.streak}-day streak
                        </AppText>
                      </View>
                    ) : null}
                  </>
                ) : (
                  <AppText variant="h2" color={colors.white} style={styles.heroEmpty}>
                    A fresh week ahead
                  </AppText>
                )}
              </View>
              <Animated.View
                entering={ZoomIn.delay(120).springify().damping(12)}
                style={styles.moodBadge}
              >
                <Image source={MOOD_ART[moodFor(recap)]} style={styles.moodImage} />
              </Animated.View>
            </View>
            <AppText variant="body" color={colors.white} style={styles.summary}>
              {recap.summary}
            </AppText>
          </Card>

          {hasData ? (
            <>
              <Card flat style={styles.block}>
                <AppText variant="overline" color={colors.inkMuted} style={styles.blockLabel}>
                  Average day
                </AppText>
                <View style={styles.statsRow}>
                  <StatBox label="Kcal" value={formatInt(recap.avg_calories)} />
                  <StatBox label="Protein" value={`${Math.round(recap.avg_protein_g)}g`} />
                  <StatBox label="Fat" value={`${Math.round(recap.avg_fat_g)}g`} />
                  <StatBox label="Carbs" value={`${Math.round(recap.avg_carbs_g)}g`} />
                </View>
                {target > 0 ? (
                  <AppText variant="caption" color={colors.inkFaint} style={styles.blockFootnote}>
                    Goal · {formatInt(target)} kcal/day
                  </AppText>
                ) : null}
              </Card>

              {highlights.map((h, i) => (
                <HighlightCard key={h.id} highlight={h} index={i} />
              ))}

              <Card flat style={styles.block}>
                <AppText variant="overline" color={colors.inkMuted} style={styles.blockLabel}>
                  When you ate
                </AppText>
                <MealTimeSplitChart split={recap.meal_time_split} />
              </Card>
            </>
          ) : null}

          <AppText variant="eyebrow" color={colors.inkFaint} center style={styles.brand}>
            YumYummy
          </AppText>
        </View>
      )}
    </Screen>
  );
}

function StatBox({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.statBox}>
      <AppText variant="overline" color={colors.inkFaint}>
        {label}
      </AppText>
      <AppText variant="macroValue" style={styles.statValue}>
        {value}
      </AppText>
    </View>
  );
}

function MealTimeSplitChart({ split }: { split: WeeklyRecap['meal_time_split'] }) {
  const values = BUCKETS.map((b) => Math.max(0, split[b.key] ?? 0));
  const total = values.reduce((a, v) => a + v, 0);
  const max = Math.max(...values, 1);
  return (
    <View style={styles.splitRow}>
      {BUCKETS.map((b, i) => {
        const v = values[i];
        const pct = total > 0 ? Math.round((v / total) * 100) : 0;
        const h = v > 0 ? Math.max(6, (v / max) * 84) : 0;
        return (
          <View key={b.key} style={styles.splitCol}>
            <AppText variant="caption" color={colors.inkFaint}>
              {pct}%
            </AppText>
            <View style={styles.splitTrack}>
              {h > 0 ? <View style={[styles.splitBar, { height: h }]} /> : null}
            </View>
            <AppText variant="overline" color={colors.inkFaint}>
              {b.label}
            </AppText>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: space.sm,
    marginBottom: space.base,
  },
  iconBtn: { padding: space.xs, minWidth: 30 },
  center: { paddingVertical: space.xxxl, alignItems: 'center' },
  stateCard: { paddingVertical: space.xl },

  content: { gap: space.base, paddingBottom: space.base },

  hero: {
    backgroundColor: colors.terracotta,
    borderColor: colors.terracotta,
    paddingVertical: space.xl,
  },
  heroTop: { flexDirection: 'row', alignItems: 'flex-start', gap: space.base },
  heroNumRow: { flexDirection: 'row', alignItems: 'baseline', gap: space.xs, marginTop: space.sm },
  heroDenom: { marginBottom: 4 },
  heroEmpty: { marginTop: space.sm },
  heroStreak: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    marginTop: space.xs,
  },
  moodBadge: {
    width: 96,
    height: 96,
    borderRadius: radius.pill,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  // Oversized inside the circle to crop the artwork's generous margins.
  moodImage: { width: 132, height: 132 },
  summary: { marginTop: space.md, opacity: 0.95 },

  block: { gap: space.md },
  blockLabel: { marginBottom: space.xs },
  blockFootnote: { marginTop: space.md, textAlign: 'center' },

  statsRow: { flexDirection: 'row', justifyContent: 'space-between' },
  statBox: { flex: 1, alignItems: 'center', gap: 2 },
  statValue: { marginTop: 2 },

  highlightCard: { flexDirection: 'row', alignItems: 'center', gap: space.base },
  highlightIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.md,
    backgroundColor: colors.terracottaSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  highlightValue: { marginTop: 2 },

  splitRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', height: 120 },
  splitCol: { flex: 1, alignItems: 'center', gap: space.xs, justifyContent: 'flex-end' },
  splitTrack: { height: 84, justifyContent: 'flex-end' },
  splitBar: { width: 26, borderRadius: radius.sm, backgroundColor: colors.terracottaSoft },

  brand: { marginTop: space.sm, letterSpacing: 2 },
});
