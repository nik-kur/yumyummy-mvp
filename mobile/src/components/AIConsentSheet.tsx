/**
 * AIConsentSheet — one-time bottom sheet shown before the first AI-powered
 * action (meal capture or advisor chat). Satisfies App Review Guidelines
 * 5.1.1(i)/5.1.2(i): disclose what is sent, to whom, and get permission first.
 */
import { View, Pressable, StyleSheet, Modal, Linking } from 'react-native';
import { Sparkles } from 'lucide-react-native';

import { AppText } from './AppText';
import { Button } from './Button';
import { AI_PROVIDERS_LABEL } from '@/state/aiConsent';
import { colors, radius, space } from '@/theme/tokens';

const BULLETS: { t: string; d: string }[] = [
  {
    t: 'What we send',
    d: 'Your meal descriptions, voice recordings and food photos — plus your nutrition questions in Advisor.',
  },
  {
    t: 'Who processes it',
    d: `Our AI partners — currently ${AI_PROVIDERS_LABEL} — analyze it to estimate nutrition and answer you.`,
  },
  {
    t: 'What we never do',
    d: 'Your data isn’t sold and isn’t used to train their public models.',
  },
];

interface AIConsentSheetProps {
  visible: boolean;
  /** User agreed — persist consent and continue the original action. */
  onAgree: () => void;
  /** User backed out — close without consent (AI features stay gated). */
  onDismiss: () => void;
}

export function AIConsentSheet({ visible, onAgree, onDismiss }: AIConsentSheetProps) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onDismiss}>
      <View style={s.overlay}>
        <View style={s.sheet}>
          <View style={s.handle} />

          <View style={s.medallion}>
            <Sparkles size={26} color={colors.terracotta} strokeWidth={1.5} />
          </View>
          <AppText variant="h2" center>
            AI does the math
          </AppText>
          <AppText variant="body" color={colors.inkMuted} center style={s.lede}>
            YumYummy uses AI services to turn what you log into nutrition numbers.
          </AppText>

          <View style={s.bullets}>
            {BULLETS.map((b) => (
              <View key={b.t} style={s.bullet}>
                <AppText variant="bodyStrong">{b.t}</AppText>
                <AppText variant="body" color={colors.inkMuted} style={s.bulletBody}>
                  {b.d}
                </AppText>
              </View>
            ))}
          </View>

          <AppText variant="caption" color={colors.inkFaint} center style={s.policy}>
            Details in our{' '}
            <AppText
              variant="caption"
              color={colors.infoBlue}
              onPress={() => Linking.openURL('https://yumyummy.ai/privacy.html')}
            >
              Privacy Policy
            </AppText>
            .
          </AppText>

          <Button label="Agree & continue" variant="brand" onPress={onAgree} />
          <Pressable onPress={onDismiss} style={s.dismissBtn} hitSlop={8}>
            <AppText variant="small" color={colors.inkMuted}>
              Not now
            </AppText>
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
  medallion: {
    width: 56,
    height: 56,
    borderRadius: radius.pill,
    backgroundColor: colors.terracottaSoft,
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'center',
    marginBottom: space.md,
  },
  lede: { marginTop: space.xs, marginBottom: space.lg },
  bullets: { gap: space.md, marginBottom: space.lg },
  bullet: { gap: 2 },
  bulletBody: { lineHeight: 21 },
  policy: { marginBottom: space.md },
  dismissBtn: { alignSelf: 'center', marginTop: space.md },
});
