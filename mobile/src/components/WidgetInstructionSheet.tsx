/**
 * WidgetInstructionSheet — bottom-sheet modal that walks the user through
 * adding the YumYummy home-screen widget (quest "add_widget", Day 6).
 */
import { View, StyleSheet, Modal, Pressable } from 'react-native';
import { Smartphone, Plus, CheckCircle } from 'lucide-react-native';

import { AppText } from './AppText';
import { Button } from './Button';
import { colors, radius, space } from '@/theme/tokens';

interface Props {
  visible: boolean;
  onDismiss: () => void;
  onDone: () => void;
}

const STEPS = [
  {
    icon: Smartphone,
    title: 'Long-press your home screen',
    body: 'Tap and hold anywhere on your home screen until the icons start wiggling.',
  },
  {
    icon: Plus,
    title: 'Tap the + button',
    body: 'Look for the "+" in the top-left corner, then search for "YumYummy".',
  },
  {
    icon: CheckCircle,
    title: 'Pick a widget and add it',
    body: 'Choose Balance, Quick Log, or the combo — whichever fits your workflow.',
  },
];

export function WidgetInstructionSheet({ visible, onDismiss, onDone }: Props) {
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onDismiss}>
      <View style={s.overlay}>
        <View style={s.sheet}>
          <View style={s.handle} />

          <AppText variant="overline" color={colors.protein}>
            DAY 6 QUEST
          </AppText>
          <AppText variant="h2" style={s.headline}>Add the home widget</AppText>
          <AppText variant="body" color={colors.inkMuted} style={s.subtitle}>
            Track at a glance without opening the app.
          </AppText>

          <View style={s.steps}>
            {STEPS.map((step, i) => {
              const Icon = step.icon;
              return (
                <View key={i} style={s.stepRow}>
                  <View style={s.stepIcon}>
                    <Icon size={20} color={colors.protein} strokeWidth={1.5} />
                  </View>
                  <View style={s.stepText}>
                    <AppText variant="bodyStrong">{step.title}</AppText>
                    <AppText variant="caption" color={colors.inkMuted}>{step.body}</AppText>
                  </View>
                </View>
              );
            })}
          </View>

          <Button label="I've added it" variant="brand" onPress={onDone} />
          <Pressable onPress={onDismiss} style={s.dismissBtn}>
            <AppText variant="small" color={colors.inkMuted}>I’ll do it later</AppText>
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
    width: 36, height: 4, borderRadius: radius.pill,
    backgroundColor: colors.hairline, alignSelf: 'center', marginBottom: space.lg,
  },
  headline: { marginTop: space.sm },
  subtitle: { marginTop: space.sm, marginBottom: space.lg },
  steps: { gap: space.lg, marginBottom: space.xl },
  stepRow: { flexDirection: 'row', gap: space.md, alignItems: 'flex-start' },
  stepIcon: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: colors.oliveSoft,
    alignItems: 'center', justifyContent: 'center',
  },
  stepText: { flex: 1, gap: 4 },
  dismissBtn: { alignSelf: 'center', marginTop: space.md },
});
