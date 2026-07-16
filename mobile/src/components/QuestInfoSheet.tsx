/**
 * QuestInfoSheet — how-to bottom sheet for an incomplete journey quest.
 * Opened by tapping a quest row on the Today card.
 */
import { View, Pressable, StyleSheet, Modal } from 'react-native';

import { AppText } from './AppText';
import { Button } from './Button';
import { colors, radius, space } from '@/theme/tokens';
import type { QuestDef, QuestId } from '@/state/journey';

interface QuestHow {
  how: string;
  cta: string;
}

const MENU_LOG_HOW: QuestHow = {
  how: 'Open My Menu and tap a saved meal to log it in one tap — no waiting, no new search. Do it daily to build the habit.',
  cta: 'Open My Menu',
};

const QUEST_HOW: Partial<Record<QuestId, QuestHow>> = {
  first_log: {
    how: 'Tap the + button and tell us what you ate — type it, say it, or snap a photo. A sentence is enough.',
    cta: 'Log a meal',
  },
  reminders: {
    how: "One tap and you're set — a gentle evening check-in plus your weekly recap. Fine-tune meal-time reminders in Settings anytime.",
    cta: 'Turn on reminders',
  },
  full_day: {
    how: 'Log 3 meals today — breakfast, lunch and dinner — to see your first complete day.',
    cta: 'Log a meal',
  },
  menu: {
    how: "Save 2 meals you eat all the time — open any logged meal and tap 'Save to My Menu'. Next time they log in one tap.",
    cta: 'Open My Menu',
  },
  photo_log: {
    how: "Snap a photo of your plate — we'll spot every dish and match verified nutrition data in ~10 seconds.",
    cta: 'Take a photo',
  },
  voice_log: {
    how: "Hold the mic and say your meal like you'd tell a friend — we'll parse dishes, portions and brands.",
    cta: 'Try a voice log',
  },
  delete_meal: {
    how: 'Logged something by mistake? Open any meal from Today and tap “Delete meal” — your day updates instantly.',
    cta: 'Go to Today',
  },
  restaurant_log: {
    how: "Eating out? Log the meal like any other — we'll match it to the cafe or restaurant's official data.",
    cta: 'Log a meal',
  },
  edit_meal: {
    how: 'Portion off? Open a logged meal from Today, tap “Edit”, and adjust the amount or macros — takes two seconds.',
    cta: 'Go to Today',
  },
  ai_question: {
    how: 'Your AI advisor knows your plan and your day. Ask what to eat next — or anything else.',
    cta: 'Open advisor',
  },
  week_trends: {
    how: 'Open the Week tab to see the patterns across your first six days of data.',
    cta: 'Open Week',
  },
  weigh_in: {
    how: "Log today's weight to close the loop — your graph shows plan vs reality.",
    cta: 'Update weight',
  },
  menu_log_3: MENU_LOG_HOW,
  menu_log_4: MENU_LOG_HOW,
  menu_log_5: MENU_LOG_HOW,
  menu_log_6: MENU_LOG_HOW,
  menu_log_7: MENU_LOG_HOW,
};

interface QuestInfoSheetProps {
  quest: QuestDef | null;
  onDismiss: () => void;
  /** "Let's go" tapped — the caller routes to the right screen. */
  onGo: (quest: QuestDef) => void;
}

export function QuestInfoSheet({ quest, onDismiss, onGo }: QuestInfoSheetProps) {
  if (!quest) return null;
  const how = QUEST_HOW[quest.id];

  return (
    <Modal visible transparent animationType="slide" onRequestClose={onDismiss}>
      <View style={s.overlay}>
        <View style={s.sheet}>
          <View style={s.handle} />

          <AppText variant="overline" color={colors.protein}>
            DAY {quest.day} QUEST
          </AppText>
          <AppText variant="h2" style={s.headline}>{quest.title}</AppText>
          <AppText variant="body" color={colors.inkMuted} style={s.body}>
            {how?.how ?? ''}
          </AppText>

          <Button
            label={how?.cta ?? "Let's go"}
            variant="brand"
            onPress={() => onGo(quest)}
          />
          <Pressable onPress={onDismiss} style={s.dismissBtn}>
            <AppText variant="small" color={colors.inkMuted}>Maybe later</AppText>
          </Pressable>
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
    paddingHorizontal: space.lg,
    paddingBottom: space.xxxl,
    paddingTop: space.md,
  },
  handle: {
    width: 36,
    height: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.hairline,
    alignSelf: 'center',
    marginBottom: space.lg,
  },
  headline: { marginTop: space.sm },
  body: { marginTop: space.md, marginBottom: space.xl, lineHeight: 22 },
  dismissBtn: { alignSelf: 'center', marginTop: space.md },
});
