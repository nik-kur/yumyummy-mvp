import { useEffect, useRef, useState } from 'react';
import {
  View,
  TextInput,
  StyleSheet,
  Pressable,
  Alert,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Animated,
  Easing,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Image } from 'expo-image';
import { X, Mic, Camera, Check, Trash2, ArrowUp } from 'lucide-react-native';
import * as Haptics from 'expo-haptics';
import * as ImagePicker from 'expo-image-picker';
import {
  useAudioRecorder,
  AudioModule,
  RecordingPresets,
  setAudioModeAsync,
} from 'expo-audio';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Chip } from '@/components/Chip';
import { usePendingMeals } from '@/state/pendingMeals';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';

type Mode = 'input' | 'accepted';

const EXAMPLES = ['2 eggs & toast', 'Chicken & rice bowl', 'Oat latte', 'Greek salad'];

/** A live-looking equalizer shown while recording (decorative, not real levels). */
function Waveform({ color }: { color: string }) {
  const bars = useRef(Array.from({ length: 26 }, () => new Animated.Value(0.3))).current;

  useEffect(() => {
    const anims = bars.map((v, i) =>
      Animated.loop(
        Animated.sequence([
          Animated.timing(v, {
            toValue: 1,
            duration: 320 + (i % 5) * 80,
            delay: (i % 7) * 45,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
          Animated.timing(v, {
            toValue: 0.28,
            duration: 320 + (i % 5) * 80,
            easing: Easing.inOut(Easing.ease),
            useNativeDriver: true,
          }),
        ]),
      ),
    );
    anims.forEach((a) => a.start());
    return () => anims.forEach((a) => a.stop());
  }, [bars]);

  return (
    <View style={styles.waveform}>
      {bars.map((v, i) => (
        <Animated.View
          key={i}
          style={[styles.waveBar, { backgroundColor: color, transform: [{ scaleY: v }] }]}
        />
      ))}
    </View>
  );
}

export default function CaptureScreen() {
  const router = useRouter();
  const params = useLocalSearchParams<{ prefill?: string; mode?: string }>();
  const { submit } = usePendingMeals();

  const [mode, setMode] = useState<Mode>('input');
  const [text, setText] = useState(typeof params.prefill === 'string' ? params.prefill : '');
  const [photo, setPhoto] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);

  // Recording timer.
  useEffect(() => {
    if (!recording) return;
    setElapsed(0);
    const started = Date.now();
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 250);
    return () => clearInterval(t);
  }, [recording]);

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

  const canSubmit = (text.trim().length > 0 || !!photo) && !recording;

  // Send path for text / photo / photo+comment. Nothing is submitted until the
  // user taps Analyze, so a photo can be reviewed and annotated first.
  const onSubmit = () => {
    if (!canSubmit) return;
    submit({ localImageUri: photo ?? undefined, text: text.trim() || undefined });
    accept();
  };

  // ---- Photo: attach as a preview (do NOT auto-submit) --------------------

  const takePhoto = async () => {
    const perm = await ImagePicker.requestCameraPermissionsAsync();
    if (!perm.granted) {
      setNote('Camera access is off. Enable it in Settings to snap your meal.');
      return;
    }
    const result = await ImagePicker.launchCameraAsync({ quality: 0.7 });
    if (result.canceled) return;
    const uri = result.assets?.[0]?.uri;
    if (uri) {
      setPhoto(uri);
      setNote(null);
    }
  };

  const pickFromLibrary = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.7,
    });
    if (result.canceled) return;
    const uri = result.assets?.[0]?.uri;
    if (uri) {
      setPhoto(uri);
      setNote(null);
    }
  };

  const onPhoto = () => {
    Alert.alert('Add a meal photo', undefined, [
      { text: 'Take Photo', onPress: () => void takePhoto() },
      { text: 'Choose from Library', onPress: () => void pickFromLibrary() },
      { text: 'Cancel', style: 'cancel' },
    ]);
  };

  // ---- Voice: fire-and-forget. Record → tap send → we transcribe + log ----

  const startRecording = async () => {
    try {
      const perm = await AudioModule.requestRecordingPermissionsAsync();
      if (!perm.granted) {
        setNote('Microphone access is off. Enable it in Settings to log by voice.');
        return;
      }
      Keyboard.dismiss();
      await setAudioModeAsync({ allowsRecording: true, playsInSilentMode: true });
      await recorder.prepareToRecordAsync();
      recorder.record();
      setNote(null);
      setRecording(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    } catch {
      setRecording(false);
      setNote('Couldn’t start recording. Try again.');
    }
  };

  const cancelRecording = async () => {
    setRecording(false);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
    try {
      await recorder.stop();
    } catch {
      // ignore — nothing to keep
    }
  };

  // Send the voice note immediately without waiting for transcription. The
  // pending-meals queue transcribes it in the background, then logs it.
  const sendVoice = async () => {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    setRecording(false);
    let uri: string | null = null;
    try {
      await recorder.stop();
      uri = recorder.uri;
    } catch {
      uri = null;
    }
    if (!uri) {
      setNote('Couldn’t save that recording. Try again.');
      return;
    }
    submit({ audioUri: uri, text: text.trim() || undefined });
    accept();
  };

  // Widget/Siri deep links land here with ?mode=… — fire the matching action once.
  const handledDeepLink = useRef(false);
  useEffect(() => {
    if (handledDeepLink.current) return;
    if (params.mode === 'photo') {
      handledDeepLink.current = true;
      onPhoto();
    } else if (params.mode === 'voice') {
      handledDeepLink.current = true;
      void startRecording();
    }
    // `text` (and any unknown value) just opens the composer — no action needed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.mode]);

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

  const mmss = `${Math.floor(elapsed / 60)}:${String(elapsed % 60).padStart(2, '0')}`;

  return (
    <Screen edges={['top', 'bottom', 'left', 'right']}>
      {/* `padding` keeps the footer (actions / recording bar) glued to the top
          of the keyboard — no dead zone between them. */}
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.topBar}>
          <View>
            <AppText variant="h2">Log a meal</AppText>
            <AppText variant="caption" color={colors.inkFaint} style={styles.subtitle}>
              AI estimate · source-checked numbers
            </AppText>
          </View>
          <Pressable onPress={() => router.back()} hitSlop={10} style={styles.close}>
            <X size={26} color={colors.inkMuted} strokeWidth={1.5} />
          </Pressable>
        </View>

        {recording ? (
          // ---- Recording: panel pinned to the bottom, like the composer ----
          <>
            <View style={styles.flex} />
            <View style={styles.recPanel}>
              <View style={styles.recStatusRow}>
                <View style={styles.recDot} />
                <AppText variant="bodyStrong">Listening…</AppText>
                <AppText variant="body" color={colors.inkMuted} style={styles.recTimer}>
                  {mmss}
                </AppText>
              </View>
              <View style={styles.recBar}>
                <Pressable
                  onPress={() => void cancelRecording()}
                  hitSlop={8}
                  style={styles.recCancel}
                >
                  <Trash2 size={20} color={colors.inkMuted} strokeWidth={1.5} />
                </Pressable>
                <View style={styles.recWaveWrap}>
                  <Waveform color={colors.terracotta} />
                </View>
                <Pressable onPress={() => void sendVoice()} style={styles.recSend}>
                  <ArrowUp size={24} color={colors.white} strokeWidth={2.5} />
                </Pressable>
              </View>
              <AppText variant="caption" color={colors.inkFaint} center>
                Tap ↑ to send — we’ll transcribe and log it for you.
              </AppText>
            </View>
          </>
        ) : (
          // ---- Composer: the input fills the screen; actions sit on the keyboard ----
          <>
            <TextInput
              style={styles.input}
              placeholder={
                photo
                  ? 'Add a note (optional) — e.g. “only ate half”'
                  : 'Just tell me what you ate…'
              }
              placeholderTextColor={colors.inkFaint}
              selectionColor={colors.terracotta}
              multiline
              autoFocus={!photo}
              value={text}
              onChangeText={setText}
            />

            <View style={styles.footer}>
              {photo ? (
                <View style={styles.photoPreview}>
                  <Image source={{ uri: photo }} style={styles.photoThumb} contentFit="cover" />
                  <View style={styles.flex}>
                    <AppText variant="bodyStrong">Photo attached</AppText>
                    <AppText variant="caption" color={colors.inkMuted}>
                      Add a note above if it helps, then tap Analyze.
                    </AppText>
                  </View>
                  <Pressable onPress={() => setPhoto(null)} hitSlop={8} style={styles.photoRemove}>
                    <X size={18} color={colors.inkMuted} strokeWidth={1.5} />
                  </Pressable>
                </View>
              ) : null}

              {note ? (
                <AppText variant="caption" color={colors.inkMuted}>
                  {note}
                </AppText>
              ) : null}

              {!text.trim() && !photo ? (
                <View style={styles.examples}>
                  {EXAMPLES.map((ex) => (
                    <Chip key={ex} label={ex} onPress={() => setText(ex)} />
                  ))}
                </View>
              ) : null}

              <View style={styles.actions}>
                <Pressable style={styles.iconButton} onPress={() => void startRecording()}>
                  <Mic size={22} color={colors.ink} strokeWidth={1.5} />
                </Pressable>
                <Pressable style={styles.iconButton} onPress={onPhoto}>
                  <Camera size={22} color={colors.ink} strokeWidth={1.5} />
                </Pressable>
                <View style={styles.analyzeWrap}>
                  <Button label="Analyze" disabled={!canSubmit} onPress={onSubmit} />
                </View>
              </View>
            </View>
          </>
        )}
      </KeyboardAvoidingView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  topBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginTop: space.lg,
    marginBottom: space.sm,
  },
  subtitle: { marginTop: space.xs },
  close: { paddingTop: space.xs },

  // The input owns all free space between the header and the footer. No
  // lineHeight on purpose: RN's iOS TextInput mis-centers text inside inflated
  // line boxes (the "floating" placeholder/text this task fixes).
  input: {
    flex: 1,
    fontFamily: fonts.serifRegular,
    fontSize: 22,
    color: colors.ink,
    textAlignVertical: 'top',
    padding: 0,
    paddingTop: space.md,
  },

  // Footer: attachment / hint / example chips / actions — pinned above the keyboard.
  footer: { gap: space.md, paddingTop: space.md, paddingBottom: space.sm },
  actions: { flexDirection: 'row', alignItems: 'center', gap: space.md },
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

  photoPreview: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.md,
    padding: space.md,
  },
  photoThumb: { width: 56, height: 56, borderRadius: radius.sm, backgroundColor: colors.surfaceAlt },
  photoRemove: {
    width: 32,
    height: 32,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
  },

  // Recording panel (bottom-pinned card).
  recPanel: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.lg,
    padding: space.base,
    gap: space.base,
    marginBottom: space.sm,
  },
  recStatusRow: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  recDot: { width: 10, height: 10, borderRadius: radius.pill, backgroundColor: colors.terracotta },
  recTimer: { marginLeft: 'auto', fontVariant: ['tabular-nums'] },
  recBar: { flexDirection: 'row', alignItems: 'center', gap: space.md },
  recCancel: {
    width: 48,
    height: 48,
    borderRadius: radius.md,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.hairline,
    alignItems: 'center',
    justifyContent: 'center',
  },
  recWaveWrap: {
    flex: 1,
    height: 48,
    justifyContent: 'center',
    paddingHorizontal: space.sm,
  },
  recSend: {
    width: 48,
    height: 48,
    borderRadius: radius.pill,
    backgroundColor: colors.terracotta,
    alignItems: 'center',
    justifyContent: 'center',
  },
  waveform: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: 28,
  },
  waveBar: { width: 3, height: 28, borderRadius: 2 },

  examples: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },

  accepted: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.md,
    paddingHorizontal: space.lg,
  },
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
