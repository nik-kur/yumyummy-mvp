/**
 * Journey completion popup — one at a time, with why-it-matters copy.
 */
import { View, Pressable, StyleSheet, Modal, Linking } from 'react-native';
import { CircleCheck, ExternalLink } from 'lucide-react-native';

import { AppText } from './AppText';
import { Button } from './Button';
import { colors, radius, space } from '@/theme/tokens';
import { QUEST_WHY, type QuestId } from '@/state/journey';

interface JourneyPopupProps {
  questId: QuestId;
  visible: boolean;
  onDismiss: () => void;
}

export function JourneyPopup({ questId, visible, onDismiss }: JourneyPopupProps) {
  const copy = QUEST_WHY[questId];

  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onDismiss}>
      <View style={s.overlay}>
        <View style={s.sheet}>
          <View style={s.handle} />
          <View style={s.iconWrap}>
            <CircleCheck size={28} color={colors.white} strokeWidth={2.5} />
          </View>

          <AppText variant="overline" color={colors.protein} center>
            QUEST COMPLETE
          </AppText>
          <AppText variant="h2" center style={s.headline}>
            {copy?.title ?? questId}
          </AppText>
          <AppText variant="body" color={colors.inkMuted} center style={s.body}>
            {copy?.why ?? ''}
          </AppText>
          {copy?.sourceUrl ? (
            <Pressable
              onPress={() => Linking.openURL(copy.sourceUrl!).catch(() => {})}
              hitSlop={8}
              style={s.sourceLink}
            >
              <ExternalLink size={12} color={colors.infoBlue} strokeWidth={1.5} />
              <AppText variant="caption" color={colors.infoBlue}>
                View the study
              </AppText>
            </Pressable>
          ) : null}

          <Button label="Nice — keep going" variant="brand" onPress={onDismiss} />
          <Pressable onPress={onDismiss} style={s.dismissBtn}>
            <AppText variant="small" color={colors.inkMuted}>Dismiss</AppText>
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
  iconWrap: {
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#16A34A',
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'center',
    marginBottom: space.md,
  },
  headline: { marginTop: space.sm },
  body: { marginTop: space.md, marginBottom: space.lg, lineHeight: 22 },
  sourceLink: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.xs,
    marginBottom: space.lg,
    marginTop: -space.sm,
  },
  dismissBtn: { alignSelf: 'center', marginTop: space.md },
});
