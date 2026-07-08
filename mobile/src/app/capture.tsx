import { useEffect, useRef, useState } from 'react';
import {
  View,
  TextInput,
  StyleSheet,
  Pressable,
  Alert,
  Keyboard,
  ScrollView,
  Animated,
  Easing,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { Image } from 'expo-image';
import { X, Mic, Camera, Check, Trash2, ArrowUp, Plus } from 'lucide-react-native';
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
import { useKeyboardHeight } from '@/utils/keyboard';
import { colors, radius, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';

type Mode = 'input' | 'accepted';

const EXAMPLES = ['2 eggs & toast', 'Chicken & rice bowl', 'Oat latte', 'Greek salad'];

/** Photos per meal cap — mirrors the server's multi-photo limit. */
const MAX_PHOTOS = 4;

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
  const keyboardHeight = useKeyboardHeight();

  const [mode, setMode] = useState<Mode>('input');
  const [text, setText] = useState(typeof params.prefill === 'string' ? params.prefill : '');
  const [photos, setPhotos] = useState<string[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);

  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);

  useEffect(() => {
    if (!recording) return;
    setElapsed(0);
    const started = Date.now();
    const t = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 250);
    return () => clearInterval(t);
  }, [recording]);

  useEffect(() => {
    if (mode !== 'accepted') return;
    const t = setTimeout(() => router.back(), 850);
    return () => clearTimeout(t);
  }, [mode, router]);

  const accept = () => {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    setMode('accepted');
  };

  const canSubmit = (text.trim().length > 0 || photos.length > 0) && !recording;

  const onSubmit = () => {
    if (!canSubmit) return;
    submit({
      localImageUri: photos[0],
      localImageUris: photos.slice(1),
      text: text.trim() || undefined,
    });
    accept();
  };

  const addPhotos = (uris: string[]) => {
    if (uris.length === 0) return;
    setPhotos((prev) => Array.from(new Set([...prev, ...uris])).slice(0, MAX_PHOTOS));
    setNote(null);
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
    if (uri) addPhotos([uri]);
  };

  const pickFromLibrary = async () => {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      quality: 0.7,
      allowsMultipleSelection: true,
      selectionLimit: MAX_PHOTOS - photos.length,
    });
    if (result.canceled) return;
    addPhotos((result.assets ?? []).map((a) => a.uri).filter(Boolean));
  };

  const onPhoto = () => {
    if (photos.length >= MAX_PHOTOS) {
      setNote(`Up to ${MAX_PHOTOS} photos per meal — remove one to add another.`);
      return;
    }
    Alert.alert('Add a meal photo', undefined, [
      { text: 'Take Photo', onPress: () => void takePhoto() },
      { text: 'Choose from Library', onPress: () => void pickFromLibrary() },
      { text: 'Cancel', style: 'cancel' },
    ]);
  };

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
      // ignore
    }
  };

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

  // Layout: header | scrollable input | docked footer. The footer is NOT inside
  // the flex input column — it sits in its own row and moves up with
  // marginBottom = keyboard height so Mic / Camera / Analyze stay visible.
  return (
    <Screen edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.flex}>
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
          <>
            <View style={styles.flex} />
            <View style={[styles.recPanel, keyboardHeight > 0 && { marginBottom: keyboardHeight }]}>
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
          <>
            <ScrollView
              style={styles.flex}
              contentContainerStyle={styles.inputScroll}
              keyboardShouldPersistTaps="handled"
              keyboardDismissMode="interactive"
              showsVerticalScrollIndicator={false}
            >
              <TextInput
                style={styles.input}
                placeholder={
                  photos.length > 0
                    ? 'Add a note (optional) — e.g. “only ate half”'
                    : 'Just tell me what you ate…'
                }
                placeholderTextColor={colors.inkFaint}
                selectionColor={colors.terracotta}
                multiline
                autoFocus={photos.length === 0}
                value={text}
                onChangeText={setText}
              />
            </ScrollView>

            <View style={[styles.footerDock, keyboardHeight > 0 && { marginBottom: keyboardHeight }]}>
              {photos.length > 0 ? (
                <View style={styles.photoPreview}>
                  <View style={styles.photoRow}>
                    {photos.map((uri) => (
                      <View key={uri}>
                        <Image source={{ uri }} style={styles.photoThumb} contentFit="cover" />
                        <Pressable
                          onPress={() => setPhotos((prev) => prev.filter((p) => p !== uri))}
                          hitSlop={8}
                          style={styles.photoRemove}
                        >
                          <X size={12} color={colors.white} strokeWidth={2.5} />
                        </Pressable>
                      </View>
                    ))}
                    {photos.length < MAX_PHOTOS ? (
                      <Pressable onPress={onPhoto} style={styles.photoAdd}>
                        <Plus size={20} color={colors.inkMuted} strokeWidth={1.5} />
                      </Pressable>
                    ) : null}
                  </View>
                  <AppText variant="caption" color={colors.inkMuted}>
                    {photos.length > 1
                      ? `${photos.length} photos of one meal — I’ll combine them.`
                      : 'Add the label or another angle with +, then tap Analyze.'}
                  </AppText>
                </View>
              ) : null}

              {note ? (
                <AppText variant="caption" color={colors.inkMuted}>
                  {note}
                </AppText>
              ) : null}

              {!text.trim() && photos.length === 0 ? (
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
      </View>
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

  inputScroll: { flexGrow: 1 },
  input: {
    minHeight: 120,
    fontFamily: fonts.serifRegular,
    fontSize: 22,
    color: colors.ink,
    textAlignVertical: 'top',
    padding: 0,
    paddingTop: space.md,
  },

  footerDock: { gap: space.md, paddingTop: space.md },
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
    gap: space.sm,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.md,
    padding: space.md,
  },
  photoRow: { flexDirection: 'row', gap: space.sm },
  photoThumb: { width: 56, height: 56, borderRadius: radius.sm, backgroundColor: colors.surfaceAlt },
  photoRemove: {
    position: 'absolute',
    top: -6,
    right: -6,
    width: 20,
    height: 20,
    borderRadius: radius.pill,
    backgroundColor: colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
  },
  photoAdd: {
    width: 56,
    height: 56,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: colors.hairline,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
  },

  recPanel: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.lg,
    padding: space.base,
    gap: space.base,
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
