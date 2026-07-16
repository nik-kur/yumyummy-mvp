/**
 * Journey progress card for the Today screen — "Your First Week".
 *
 * Header (ring + day title) opens the week-path overlay. The card lists today's
 * quests; if the user has fallen behind (earlier-day quests still open) those
 * appear first under a "Catch up" heading and the ring turns amber.
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
  overdueQuests,
  type JourneyState,
  type QuestDef,
} from '@/state/journey';

interface JourneyCardProps {
  state: JourneyState;
  /** Active (calendar) day — quests of this day are listed. */
  day: number;
  onHeaderPress: () => void;
  onQuestPress: (quest: QuestDef) => void;
}

function QuestRow({
  quest,
  done,
  showBorder,
  onPress,
}: {
  quest: QuestDef;
  done: boolean;
  showBorder: boolean;
  onPress: (q: QuestDef) => void;
}) {
  return (
    <Pressable
      disabled={done}
      onPress={() => onPress(quest)}
      style={[s.questRow, showBorder && s.questRowBorder]}
    >
      <View style={[s.checkbox, done && s.checkboxDone]}>
        {done ? <Check size={14} color={colors.white} strokeWidth={3} /> : null}
      </View>
      <AppText
        variant="body"
        color={done ? colors.inkFaint : colors.ink}
        style={[s.questLabel, done && s.questLabelDone]}
      >
        {quest.title}
      </AppText>
      {!done ? <ChevronRight size={16} color={colors.inkFaint} strokeWidth={1.5} /> : null}
    </Pressable>
  );
}

export function JourneyCard({ state, day, onHeaderPress, onQuestPress }: JourneyCardProps) {
  const done = completedCount(state);
  const total = ALL_QUESTS.length;
  const dayDef = LADDER.find((d) => d.day === day);
  if (!dayDef) return null;

  const overdue = overdueQuests(state);
  const behind = overdue.length > 0;
  const ringColor = behind ? colors.warning : colors.protein;
  const ringTrack = behind ? colors.warningSoft : colors.oliveSoft;

  return (
    <Card style={[s.card, behind && s.cardBehind]}>
      <Pressable onPress={onHeaderPress} style={s.header} hitSlop={4}>
        <Ring size={46} stroke={4} progress={done / total} color={ringColor} track={ringTrack}>
          <AppText variant="caption" color={ringColor} style={s.pct}>
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

      {behind ? (
        <View style={s.catchUp}>
          <AppText variant="overline" color={colors.warning} style={s.catchUpLabel}>
            CATCH UP
          </AppText>
          {overdue.map((q, i) => (
            <QuestRow key={q.id} quest={q} done={false} showBorder={i > 0} onPress={onQuestPress} />
          ))}
        </View>
      ) : null}

      <View style={s.list}>
        {behind ? (
          <AppText variant="overline" color={colors.inkMuted} style={s.todayLabel}>
            TODAY
          </AppText>
        ) : null}
        {dayDef.quests.map((q, i) => (
          <QuestRow
            key={q.id}
            quest={q}
            done={isCompleted(state, q.id)}
            showBorder={i > 0}
            onPress={onQuestPress}
          />
        ))}
      </View>

      <View style={[s.chip, behind ? s.chipBehind : s.chipAhead]}>
        <AppText variant="caption" color={behind ? colors.warning : colors.infoBlue}>
          {behind
            ? `You're behind — finish ${overdue.length} earlier ${
                overdue.length === 1 ? 'quest' : 'quests'
              } to get back on track.`
            : `✨ ${dayDef.unlock}`}
        </AppText>
      </View>
    </Card>
  );
}

const s = StyleSheet.create({
  card: { borderColor: colors.oliveSoft, borderWidth: 1.5 },
  cardBehind: { borderColor: colors.warningSoft },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    marginBottom: space.md,
  },
  pct: { fontSize: 11 },
  headerText: { flex: 1, gap: 2 },
  catchUp: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
    marginBottom: space.xs,
  },
  catchUpLabel: { marginTop: space.sm },
  list: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
  },
  todayLabel: { marginTop: space.sm },
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
  chip: {
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    marginTop: space.sm,
  },
  chipAhead: { backgroundColor: colors.infoBlueSoft },
  chipBehind: { backgroundColor: colors.warningSoft },
});
