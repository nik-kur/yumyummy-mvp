/**
 * Journey quest popup — shown once per session when a new quest becomes active.
 *
 * Uses a simple modal overlay; production version should use a proper bottom sheet.
 */
import { View, Pressable, StyleSheet, Modal } from 'react-native';

import { AppText } from './AppText';
import { Button } from './Button';
import { colors, radius, space } from '@/theme/tokens';
import type { QuestDef } from '@/state/journey';

interface JourneyPopupProps {
  quest: QuestDef;
  visible: boolean;
  onDismiss: () => void;
  onGo: () => void;
}

export function JourneyPopup({ quest, visible, onDismiss, onGo }: JourneyPopupProps) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onDismiss}>
      <View style={s.overlay}>
        <View style={s.sheet}>
          <View style={s.handle} />

          <AppText variant="overline" color={colors.protein}>
            DAY {quest.day} QUEST
          </AppText>
          <AppText variant="h2" style={s.headline}>{quest.label}</AppText>
          <AppText variant="body" color={colors.inkMuted} style={s.body}>
            {quest.desc}
          </AppText>
          <AppText variant="small" color={colors.inkFaint} style={s.why}>
            Small steps build lasting habits. This quest is designed to help you
            get the most out of YumYummy.
          </AppText>

          <Button label="Let's go" variant="brand" onPress={onGo} />
          <Pressable onPress={onDismiss} style={s.dismissBtn}>
            <AppText variant="small" color={colors.inkMuted}>Maybe later</AppText>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'flex-end',
    backgroundColor: colors.overlay,
  },
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
  body: { marginTop: space.md },
  why: { marginTop: space.md, marginBottom: space.lg },
  dismissBtn: { alignSelf: 'center', marginTop: space.md },
});
