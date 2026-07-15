/**
 * Journey progress card for the Today screen — "Your First Week".
 *
 * Header (ring % + day title) opens the week-path overlay. Each quest of the
 * active day renders as an equal-size row: completed rows turn gray with a
 * strikethrough; incomplete rows open a how-to sheet on tap.
 */
import { View, Pressable, StyleSheet } from 'react-native';
import { ChevronRight, Check } from 'lucide-react-native';

import { AppText } from './AppText';
import { Card } from './Card';
import { Ring } from './Ring';
import { colors, radius, space } from '@/theme/tokens';
import {
  ALL_QUESTS,
  LADDER,
  completedCount,
  isCompleted,
  type JourneyState,
  type QuestDef,
} from '@/state/journey';

interface JourneyCardProps {
  state: JourneyState;
  /** Active (highest unlocked) day — quests of this day are listed. */
  day: number;
  onHeaderPress: () => void;
  onQuestPress: (quest: QuestDef) => void;
}

export function JourneyCard({ state, day, onHeaderPress, onQuestPress }: JourneyCardProps) {
  // Ring = week quests done out of the whole ladder — shown as a count so
  // the number is self-explanatory (a bare % read as random).
  const done = completedCount(state);
  const total = ALL_QUESTS.length;
  const dayDef = LADDER.find((d) => d.day === day);
  if (!dayDef) return null;

  return (
    <Card style={s.card}>
      <Pressable onPress={onHeaderPress} style={s.header} hitSlop={4}>
        <Ring size={46} stroke={4} progress={done / total} color={colors.protein} track={colors.oliveSoft}>
          <AppText variant="caption" color={colors.protein} style={s.pct}>
            {done}/{total}
          </AppText>
        </Ring>
        <View style={s.headerText}>
          <AppText variant="overline" color={colors.terracottaText}>
            YOUR FIRST WEEK · DAY {day} OF 7
          </AppText>
          <AppText variant="title">{dayDef.title}</AppText>
        </View>
        <ChevronRight size={20} color={colors.inkFaint} strokeWidth={1.5} />
      </Pressable>

      <View style={s.list}>
        {dayDef.quests.map((q, i) => {
          const done = isCompleted(state, q.id);
          return (
            <Pressable
              key={q.id}
              disabled={done}
              onPress={() => onQuestPress(q)}
              style={[s.questRow, i > 0 && s.questRowBorder]}
            >
              <View style={[s.checkbox, done && s.checkboxDone]}>
                {done ? <Check size={14} color={colors.white} strokeWidth={3} /> : null}
              </View>
              <AppText
                variant="body"
                color={done ? colors.inkFaint : colors.ink}
                style={[s.questLabel, done && s.questLabelDone]}
              >
                {q.title}
              </AppText>
              {!done ? (
                <ChevronRight size={16} color={colors.inkFaint} strokeWidth={1.5} />
              ) : null}
            </Pressable>
          );
        })}
      </View>

      <View style={s.unlockChip}>
        <AppText variant="caption" color={colors.infoBlue}>
          ✨ {dayDef.unlock}
        </AppText>
      </View>
    </Card>
  );
}

const s = StyleSheet.create({
  card: { borderColor: colors.oliveSoft, borderWidth: 1.5 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    marginBottom: space.md,
  },
  pct: { fontSize: 11 },
  headerText: { flex: 1, gap: 2 },
  list: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
  },
  questRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    paddingVertical: space.md,
  },
  questRowBorder: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
  },
  checkbox: {
    width: 24,
    height: 24,
    borderRadius: radius.sm,
    borderWidth: 1.5,
    borderColor: colors.hairlineStrong,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxDone: {
    backgroundColor: colors.success,
    borderColor: colors.success,
  },
  questLabel: { flex: 1 },
  questLabelDone: { textDecorationLine: 'line-through' },
  unlockChip: {
    backgroundColor: colors.infoBlueSoft,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    marginTop: space.sm,
  },
});
