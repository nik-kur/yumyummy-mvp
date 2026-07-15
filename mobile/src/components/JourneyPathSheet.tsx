/**
 * JourneyPathSheet — full-week overview of the activation ladder.
 *
 * Sequential-unlock rendering:
 * - complete — green check, quests listed with their states;
 * - active   — current day, quests listed;
 * - preview  — all previous days done, calendar gate remains: quest titles
 *              visible but grayed under a lock, "opens tomorrow" note;
 * - locked   — quest details hidden behind a lock with an unlock hint.
 */
import { View, Pressable, StyleSheet, Modal, ScrollView } from 'react-native';
import { X, Check, Lock } from 'lucide-react-native';

import { AppText } from './AppText';
import { colors, radius, space } from '@/theme/tokens';
import {
  LADDER,
  dayStatus,
  isCompleted,
  type JourneyState,
} from '@/state/journey';

interface JourneyPathSheetProps {
  visible: boolean;
  state: JourneyState;
  onDismiss: () => void;
}

export function JourneyPathSheet({ visible, state, onDismiss }: JourneyPathSheetProps) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onDismiss}>
      <View style={s.overlay}>
        <View style={s.sheet}>
          <View style={s.topRow}>
            <View style={s.flex}>
              <AppText variant="h2">Your first week</AppText>
              <AppText variant="small" color={colors.inkMuted}>
                One tiny step a day. Nothing resets, nothing burns out.
              </AppText>
            </View>
            <Pressable onPress={onDismiss} hitSlop={12} style={s.closeBtn}>
              <X size={22} color={colors.inkMuted} strokeWidth={1.75} />
            </Pressable>
          </View>

          <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scroll}>
            {LADDER.map((dayDef, i) => {
              const status = dayStatus(state, dayDef.day);
              const isLast = i === LADDER.length - 1;

              return (
                <View key={dayDef.day} style={[s.dayRow, !isLast && s.dayRowBorder]}>
                  <View style={s.badgeCol}>
                    {status === 'complete' ? (
                      <View style={[s.dayBadge, s.badgeComplete]}>
                        <Check size={16} color={colors.white} strokeWidth={3} />
                      </View>
                    ) : status === 'active' ? (
                      <View style={[s.dayBadge, s.badgeActive]}>
                        <AppText variant="bodyStrong" color={colors.white}>
                          {dayDef.day}
                        </AppText>
                      </View>
                    ) : (
                      <View style={[s.dayBadge, s.badgeLocked]}>
                        <Lock size={14} color={colors.inkFaint} strokeWidth={1.75} />
                      </View>
                    )}
                    <AppText variant="caption" color={colors.inkFaint}>
                      Day {dayDef.day}
                    </AppText>
                  </View>

                  <View style={s.dayContent}>
                    {status === 'locked' ? (
                      <>
                        <AppText variant="bodyStrong" color={colors.inkFaint}>
                          Locked
                        </AppText>
                        <AppText variant="caption" color={colors.inkFaint}>
                          Finish all Day {dayDef.day - 1} quests to unlock
                        </AppText>
                      </>
                    ) : (
                      <>
                        <AppText
                          variant="bodyStrong"
                          color={status === 'preview' ? colors.inkMuted : colors.ink}
                        >
                          {dayDef.title}
                        </AppText>

                        {dayDef.quests.map((q) => {
                          const done = isCompleted(state, q.id);
                          return (
                            <View key={q.id} style={s.questRow}>
                              {done ? (
                                <Check size={14} color={colors.success} strokeWidth={2.5} />
                              ) : (
                                <View
                                  style={[
                                    s.questDot,
                                    status === 'preview' && s.questDotLocked,
                                  ]}
                                />
                              )}
                              <AppText
                                variant="caption"
                                color={done || status === 'preview' ? colors.inkFaint : colors.inkMuted}
                                style={done ? s.questDone : undefined}
                              >
                                {q.title}
                              </AppText>
                            </View>
                          );
                        })}

                        {status === 'preview' ? (
                          <View style={s.previewChip}>
                            <Lock size={12} color={colors.infoBlue} strokeWidth={1.75} />
                            <AppText variant="caption" color={colors.infoBlue}>
                              Opens tomorrow — more achievements ahead
                            </AppText>
                          </View>
                        ) : null}
                      </>
                    )}
                  </View>
                </View>
              );
            })}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: colors.overlay },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    paddingTop: space.lg,
    maxHeight: '88%',
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: space.md,
    paddingHorizontal: space.lg,
    marginBottom: space.md,
  },
  flex: { flex: 1, gap: 2 },
  closeBtn: {
    width: 34,
    height: 34,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scroll: { paddingHorizontal: space.lg, paddingBottom: space.xxxl },
  dayRow: {
    flexDirection: 'row',
    gap: space.base,
    paddingVertical: space.base,
  },
  dayRowBorder: {
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.hairline,
  },
  badgeCol: { alignItems: 'center', gap: space.xs, width: 44 },
  dayBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeComplete: { backgroundColor: colors.success },
  badgeActive: { backgroundColor: colors.ink },
  badgeLocked: {
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.hairline,
  },
  dayContent: { flex: 1, gap: space.xs, paddingTop: 2 },
  questRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  questDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    borderWidth: 1.5,
    borderColor: colors.hairlineStrong,
    marginHorizontal: 1,
  },
  questDotLocked: { borderStyle: 'dashed' },
  questDone: { textDecorationLine: 'line-through' },
  previewChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    backgroundColor: colors.infoBlueSoft,
    borderRadius: radius.sm,
    paddingHorizontal: space.sm,
    paddingVertical: space.xs,
    alignSelf: 'flex-start',
    marginTop: space.xs,
  },
});
