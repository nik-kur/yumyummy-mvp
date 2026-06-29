import { useEffect, useState } from 'react';
import {
  View,
  TextInput,
  StyleSheet,
  Pressable,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { X, Mic, Camera, Check } from 'lucide-react-native';
import * as Haptics from 'expo-haptics';
import * as ImagePicker from 'expo-image-picker';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Chip } from '@/components/Chip';
import { usePendingMeals } from '@/state/pendingMeals';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';

type Mode = 'input' | 'accepted';

const EXAMPLES = ['2 eggs & toast', 'Chicken & rice bowl', 'Oat latte', 'Greek salad'];

export default function CaptureScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ prefill?: string }>();
  const { submit } = usePendingMeals();

  const [mode, setMode] = useState<Mode>('input');
  const [text, setText] = useState(typeof params.prefill === 'string' ? params.prefill : '');
  const [note, setNote] = useState<string | null>(null);

  // After accepting, briefly show a confirmation, then collapse the sheet.
  useEffect(() => {
    if (mode !== 'accepted') return;
    const t = setTimeout(() => router.back(), 850);
    return () => clearTimeout(t);
  }, [mode, router]);

  const accept = () => {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    setMode('accepted');
  };

  const submitText = () => {
    const value = text.trim();
    if (!value) return;
    submit({ text: value });
    accept();
  };

  const submitPhoto = (uri: string) => {
    submit({ localImageUri: uri, text: text.trim() || undefined });
    accept();
  };

  const takePhoto = async () => {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      setNote('Camera access is off. Enable it in Settings to snap your meal.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (result.canceled) return;
    const uri = result.assets?.[0]?.uri;
    if (uri) submitPhoto(uri);
  };

  const pickFromLibrary = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.7,
    });
    if (result.canceled) return;
    const uri = result.assets?.[0]?.uri;
    if (uri) submitPhoto(uri);
  };

  const onPhoto = () => {
    Alert.alert('Add a meal photo', undefined, [
      { text: 'Take Photo', onPress: () => void takePhoto() },
      { text: 'Choose from Library', onPress: () => void pickFromLibrary() },
      { text: 'Cancel', style: 'cancel' },
    ]);
  };

  const onVoice = () => {
    setNote('Voice logging arrives with the next build — type it for now.');
  };

  if (mode === 'accepted') {
    return (
      <Screen edges={['top', 'bottom', 'left', 'right']}>
        <View style={styles.accepted}>
          <View style={styles.tick}>
            <Check size={44} color={colors.white} strokeWidth={2.5} />
          </View>
          <AppText variant="h2" center>
            Got it
          </AppText>
          <AppText variant="body" color={colors.inkMuted} center>
            Analyzing in the background — it’ll appear on Today in a moment.
          </AppText>
        </View>
      </Screen>
    );
  }

  return (
    <Screen edges={['top', 'bottom', 'left', 'right']}>
      <KeyboardAvoidingView
        style={styles.kav}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.topBar}>
          <AppText variant="h2">Log a meal</AppText>
          <Pressable onPress={() => router.back()} hitSlop={10}>
            <X size={26} color={colors.inkMuted} strokeWidth={1.5} />
          </Pressable>
        </View>

        <TextInput
          style={styles.bigInput}
          placeholder="Just tell me what you ate…"
          placeholderTextColor={colors.inkFaint}
          multiline
          autoFocus
          value={text}
          onChangeText={setText}
        />

        <View style={styles.examples}>
          {EXAMPLES.map((ex) => (
            <Chip key={ex} label={ex} onPress={() => setText(ex)} />
          ))}
        </View>

        {note ? (
          <AppText variant="caption" color={colors.inkMuted} style={styles.note}>
            {note}
          </AppText>
        ) : null}

        <View style={styles.actions}>
          <Pressable style={styles.iconButton} onPress={onVoice}>
            <Mic size={22} color={colors.ink} strokeWidth={1.5} />
          </Pressable>
          <Pressable style={styles.iconButton} onPress={onPhoto}>
            <Camera size={22} color={colors.ink} strokeWidth={1.5} />
          </Pressable>
          <View style={styles.analyzeWrap}>
            <Button label="Analyze" disabled={text.trim().length === 0} onPress={submitText} />
          </View>
        </View>
        <AppText variant="caption" color={colors.inkFaint} center style={styles.poweredBy}>
          AI estimate · source-checked numbers
        </AppText>
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  kav: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: space.lg,
    marginBottom: space.base,
  },
  // flex:1 makes the input absorb the free space, so there's no empty gap and
  // the action bar sits just above the keyboard.
  bigInput: {
    flex: 1,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.lg,
    padding: space.base,
    fontFamily: fonts.serifRegular,
    fontSize: 22,
    lineHeight: 30,
    color: colors.ink,
    textAlignVertical: 'top',
  },
  examples: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm, marginTop: space.base },
  note: { marginTop: space.md },
  actions: { flexDirection: 'row', alignItems: 'center', gap: space.md, marginTop: space.base },
  iconButton: {
    width: 54,
    height: 54,
    borderRadius: radius.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.hairline,
    alignItems: 'center',
    justifyContent: 'center',
  },
  analyzeWrap: { flex: 1 },
  poweredBy: { marginTop: space.base },
  accepted: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: space.md, paddingHorizontal: space.lg },
  tick: {
    width: 88,
    height: 88,
    borderRadius: radius.pill,
    backgroundColor: colors.success,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: space.sm,
  },
});
