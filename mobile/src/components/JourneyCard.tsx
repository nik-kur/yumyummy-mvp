/**
 * Journey progress card for the Today screen — "Your First Week" widget.
 *
 * Shows the current active quest, overall progress, and a CTA.
 * Olive accent per spec (protein color #5A6A3A / oliveSoft #E3E6CE).
 */
import { View, Pressable, StyleSheet } from 'react-native';
import { ChevronRight, CircleCheck, Circle } from 'lucide-react-native';

import { AppText } from './AppText';
import { Card } from './Card';
import { colors, radius, space } from '@/theme/tokens';
import type { QuestDef, JourneyState } from '@/state/journey';
import { completedCount } from '@/state/journey';

interface JourneyCardProps {
  quests: QuestDef[];
  state: JourneyState;
  activeQuest: QuestDef | null;
  day: number;
  onPress: () => void;
}

export function JourneyCard({
  quests,
  state,
  activeQuest: active,
  day,
  onPress,
}: JourneyCardProps) {
  const done = completedCount(state);
  const total = quests.length;
  const progress = total > 0 ? done / total : 0;

  return (
    <Pressable onPress={onPress}>
      <Card style={s.card}>
        <View style={s.header}>
          <View style={s.dayBadge}>
            <AppText variant="overline" color={colors.protein}>
              DAY {day} OF 7
            </AppText>
          </View>
          <AppText variant="caption" color={colors.inkMuted}>
            {done}/{total} quests
          </AppText>
        </View>

        <AppText variant="title" style={s.title}>Your First Week</AppText>

        {/* Progress bar */}
        <View style={s.progressTrack}>
          <View style={[s.progressFill, { width: `${progress * 100}%` as any }]} />
        </View>

        {/* Active quest */}
        {active && (
          <View style={s.questRow}>
            <Circle size={18} color={colors.protein} strokeWidth={1.5} />
            <View style={s.questText}>
              <AppText variant="bodyStrong">{active.label}</AppText>
              <AppText variant="caption" color={colors.inkMuted}>{active.desc}</AppText>
            </View>
            <ChevronRight size={18} color={colors.inkFaint} strokeWidth={1.5} />
          </View>
        )}

        {/* Recent completions */}
        {done > 0 && (
          <View style={s.completedList}>
            {quests
              .filter((q) => state.completed[q.quest])
              .slice(-2)
              .map((q) => (
                <View key={q.quest} style={s.completedRow}>
                  <CircleCheck size={16} color={colors.success} strokeWidth={1.5} />
                  <AppText variant="caption" color={colors.inkMuted}>{q.label}</AppText>
                </View>
              ))}
          </View>
        )}
      </Card>
    </Pressable>
  );
}

const s = StyleSheet.create({
  card: { borderColor: colors.oliveSoft, borderWidth: 1.5 },
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: space.sm },
  dayBadge: {
    backgroundColor: colors.oliveSoft,
    paddingHorizontal: space.sm,
    paddingVertical: 2,
    borderRadius: radius.sm,
  },
  title: { marginBottom: space.md },
  progressTrack: {
    height: 6,
    backgroundColor: colors.oliveSoft,
    borderRadius: radius.pill,
    marginBottom: space.md,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: colors.protein,
    borderRadius: radius.pill,
  },
  questRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.md,
    padding: space.md,
    marginBottom: space.sm,
  },
  questText: { flex: 1, gap: 2 },
  completedList: { gap: space.xs, marginTop: space.xs },
  completedRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
});
