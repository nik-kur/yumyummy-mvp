/**
 * One-time popup on the user's first visit to the Today screen: points to the
 * "Science & sources" page in Profile (citations for all health information —
 * App Review Guideline 1.4.1) without linking out, so the first-session flow
 * isn't interrupted. Styled after JourneyPopup.
 */
import { View, StyleSheet, Modal } from 'react-native';
import { BookOpen } from 'lucide-react-native';

import { AppText } from './AppText';
import { Button } from './Button';
import { colors, radius, space } from '@/theme/tokens';

interface SourcesIntroPopupProps {
  visible: boolean;
  onDismiss: () => void;
}

export function SourcesIntroPopup({ visible, onDismiss }: SourcesIntroPopupProps) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onDismiss}>
      <View style={s.overlay}>
        <View style={s.sheet}>
          <View style={s.handle} />
          <View style={s.iconWrap}>
            <BookOpen size={26} color={colors.white} strokeWidth={2} />
          </View>

          <AppText variant="overline" color={colors.infoBlue} center>
            BACKED BY SCIENCE
          </AppText>
          <AppText variant="h2" center style={s.headline}>
            Where our numbers come from
          </AppText>
          <AppText variant="body" color={colors.inkMuted} center style={s.body}>
            Your calorie and macro targets — and every recommendation in YumYummy — are based on
            published research and public health guidelines. The full list of sources is always
            available in Profile → Science & sources.
          </AppText>
          <AppText variant="caption" color={colors.inkFaint} center style={s.note}>
            YumYummy provides nutrition information, not medical advice.
          </AppText>

          <Button label="OK" variant="brand" onPress={onDismiss} />
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
    backgroundColor: colors.infoBlue,
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'center',
    marginBottom: space.md,
  },
  headline: { marginTop: space.sm },
  body: { marginTop: space.md, lineHeight: 22 },
  note: { marginTop: space.sm, marginBottom: space.lg },
});
