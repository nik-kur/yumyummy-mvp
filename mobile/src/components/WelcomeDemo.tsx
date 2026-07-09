/**
 * S1 Welcome autoplay demo — ported from onboarding_prototype_v3.html.
 *
 * Cycles Photo → Voice → Text logging modes with a result card, illustrating
 * verified sources (USDA, Starbucks, Joe & The Juice).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { View, StyleSheet, Animated, Easing } from 'react-native';
import { Camera, Mic, Keyboard } from 'lucide-react-native';

import { AppText } from './AppText';
import { SourceBadge } from './Badges';
import { colors, radius, space } from '@/theme/tokens';

type Mode = 0 | 1 | 2;

interface Phase {
  mode: Mode;
  name: string;
  kcal: number;
  macros: string;
  source: string;
  delayMs: number;
  typeText?: string;
}

const PHASES: Phase[] = [
  {
    mode: 0,
    name: 'Avocado toast & eggs',
    kcal: 412,
    macros: 'P 22g · F 24g · C 28g',
    source: 'USDA',
    delayMs: 1350,
  },
  {
    mode: 1,
    name: 'Cappuccino & butter croissant',
    kcal: 350,
    macros: 'P 11g · F 18g · C 38g',
    source: 'Starbucks',
    delayMs: 1350,
  },
  {
    mode: 2,
    name: 'Tunacado sandwich',
    kcal: 570,
    macros: 'P 25g · F 40g · C 29g',
    source: 'Joe & The Juice',
    delayMs: 1700,
    typeText: 'tunacado from joe & the juice',
  },
];

const MODE_LABELS: { mode: Mode; label: string; Icon: typeof Camera }[] = [
  { mode: 0, label: 'Photo', Icon: Camera },
  { mode: 1, label: 'Voice', Icon: Mic },
  { mode: 2, label: 'Text', Icon: Keyboard },
];

const WAVE_DELAYS = [0, 100, 200, 50, 150, 250, 100];
const CYCLE_MS = 3300;

function CornerBracket({ pos }: { pos: 'tl' | 'tr' | 'bl' | 'br' }) {
  const corner = {
    tl: { top: 10, left: 10, borderTopWidth: 2.5, borderLeftWidth: 2.5 },
    tr: { top: 10, right: 10, borderTopWidth: 2.5, borderRightWidth: 2.5 },
    bl: { bottom: 10, left: 10, borderBottomWidth: 2.5, borderLeftWidth: 2.5 },
    br: { bottom: 10, right: 10, borderBottomWidth: 2.5, borderRightWidth: 2.5 },
  }[pos];
  return (
    <View
      style={[
        s.bracket,
        corner,
        pos === 'tl' && { borderTopLeftRadius: 6 },
        pos === 'tr' && { borderTopRightRadius: 6 },
        pos === 'bl' && { borderBottomLeftRadius: 6 },
        pos === 'br' && { borderBottomRightRadius: 6 },
      ]}
    />
  );
}

function PhotoStage({ scanY }: { scanY: Animated.AnimatedInterpolation<number> }) {
  return (
    <View style={s.stageInner}>
      <AppText style={s.plateEmoji}>🥑🍳🍞</AppText>
      <Animated.View style={[s.scanLine, { transform: [{ translateY: scanY }] }]} />
      <CornerBracket pos="tl" />
      <CornerBracket pos="tr" />
      <CornerBracket pos="bl" />
      <CornerBracket pos="br" />
    </View>
  );
}

function VoiceStage() {
  return (
    <View style={s.voiceWrap}>
      <AppText variant="body" style={s.voiceQuote}>
        “Starbucks cappuccino and a butter croissant”
      </AppText>
      <View style={s.wave}>
        {WAVE_DELAYS.map((delay, i) => (
          <WaveBar key={i} delay={delay} />
        ))}
      </View>
    </View>
  );
}

function WaveBar({ delay }: { delay: number }) {
  const h = useRef(new Animated.Value(8)).current;
  useEffect(() => {
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(h, { toValue: 32, duration: 425, delay, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
        Animated.timing(h, { toValue: 8, duration: 425, easing: Easing.inOut(Easing.ease), useNativeDriver: false }),
      ]),
    );
    anim.start();
    return () => anim.stop();
  }, [delay, h]);
  return <Animated.View style={[s.waveBar, { height: h }]} />;
}

function TextStage({ text }: { text: string }) {
  const [shown, setShown] = useState('');
  const [cursorOn, setCursorOn] = useState(true);
  useEffect(() => {
    setShown('');
    let i = 0;
    const type = setInterval(() => {
      i += 1;
      setShown(text.slice(0, i));
      if (i >= text.length) clearInterval(type);
    }, 45);
    const blink = setInterval(() => setCursorOn((v) => !v), 500);
    return () => { clearInterval(type); clearInterval(blink); };
  }, [text]);
  return (
    <View style={s.typeBox}>
      <AppText variant="title" center>
        {shown}
        {cursorOn ? <AppText variant="title" color={colors.terracotta}>|</AppText> : null}
      </AppText>
    </View>
  );
}

export function WelcomeDemo() {
  const [phaseIdx, setPhaseIdx] = useState(0);
  const [resultVisible, setResultVisible] = useState(false);
  const resultOpacity = useRef(new Animated.Value(0)).current;
  const resultY = useRef(new Animated.Value(8)).current;
  const scanAnim = useRef(new Animated.Value(0)).current;

  const phase = PHASES[phaseIdx];
  const activeMode = phase.mode;

  const showResult = useCallback((p: Phase) => {
    setResultVisible(true);
    Animated.parallel([
      Animated.timing(resultOpacity, { toValue: 1, duration: 350, useNativeDriver: true }),
      Animated.timing(resultY, { toValue: 0, duration: 350, useNativeDriver: true }),
    ]).start();
  }, [resultOpacity, resultY]);

  const hideResult = useCallback(() => {
    setResultVisible(false);
    resultOpacity.setValue(0);
    resultY.setValue(8);
  }, [resultOpacity, resultY]);

  const runPhase = useCallback((idx: number) => {
    const p = PHASES[idx];
    hideResult();
    const t = setTimeout(() => showResult(p), p.delayMs);
    return () => clearTimeout(t);
  }, [hideResult, showResult]);

  useEffect(() => {
    return runPhase(phaseIdx);
  }, [phaseIdx, runPhase]);

  useEffect(() => {
    const id = setInterval(() => {
      setPhaseIdx((i) => (i + 1) % PHASES.length);
    }, CYCLE_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (activeMode !== 0) return;
    scanAnim.setValue(0);
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(scanAnim, { toValue: 1, duration: 1250, easing: Easing.inOut(Easing.ease), useNativeDriver: true }),
        Animated.timing(scanAnim, { toValue: 0.3, duration: 400, useNativeDriver: true }),
      ]),
    );
    anim.start();
    return () => anim.stop();
  }, [activeMode, phaseIdx, scanAnim]);

  const scanY = scanAnim.interpolate({
    inputRange: [0, 0.55, 1],
    outputRange: [0, 72, 20],
  });

  return (
    <View style={s.shell}>
      <View style={s.modes}>
        {MODE_LABELS.map(({ mode, label, Icon }) => (
          <View key={mode} style={[s.modePill, activeMode === mode && s.modePillOn]}>
            <Icon size={12} color={activeMode === mode ? colors.white : colors.inkMuted} strokeWidth={1.5} />
            <AppText
              variant="caption"
              color={activeMode === mode ? colors.white : colors.inkMuted}
              style={s.modeLabel}
            >
              {label}
            </AppText>
          </View>
        ))}
      </View>

      <View style={s.stage}>
        {activeMode === 0 && <PhotoStage scanY={scanY} />}
        {activeMode === 1 && <VoiceStage />}
        {activeMode === 2 && phase.typeText && <TextStage text={phase.typeText} />}
      </View>

      {resultVisible && (
        <Animated.View
          style={[
            s.result,
            { opacity: resultOpacity, transform: [{ translateY: resultY }] },
          ]}
        >
          <View>
            <AppText variant="h2">
              {phase.kcal}
              <AppText variant="caption" color={colors.inkMuted}> kcal</AppText>
            </AppText>
            <AppText variant="caption" color={colors.inkMuted}>{phase.name}</AppText>
          </View>
          <View style={s.resultRight}>
            <SourceBadge source={phase.source} />
            <AppText variant="caption" color={colors.inkMuted} style={s.macros}>
              {phase.macros}
            </AppText>
          </View>
        </Animated.View>
      )}
    </View>
  );
}

const s = StyleSheet.create({
  shell: {
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
    borderRadius: radius.xl,
    padding: space.md,
    marginVertical: space.md,
  },
  modes: { flexDirection: 'row', justifyContent: 'center', gap: space.sm, marginBottom: space.md },
  modePill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: space.md,
    paddingVertical: 5,
    borderRadius: radius.pill,
    backgroundColor: colors.bg,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
  },
  modePillOn: { backgroundColor: colors.terracotta, borderColor: colors.terracotta },
  modeLabel: { fontWeight: '600' },
  stage: {
    height: 128,
    borderRadius: radius.md,
    backgroundColor: '#F2EADB',
    overflow: 'hidden',
    justifyContent: 'center',
    alignItems: 'center',
  },
  stageInner: { ...StyleSheet.absoluteFillObject, justifyContent: 'center', alignItems: 'center' },
  plateEmoji: { fontSize: 42, letterSpacing: 3 },
  scanLine: {
    position: 'absolute',
    left: '8%',
    right: '8%',
    height: 3,
    borderRadius: 3,
    backgroundColor: colors.terracotta,
    opacity: 0.85,
    top: '12%',
  },
  bracket: {
    position: 'absolute',
    width: 20,
    height: 20,
    borderColor: colors.terracotta,
    opacity: 0.9,
  },
  voiceWrap: { alignItems: 'center', gap: space.md, paddingHorizontal: space.lg },
  voiceQuote: { fontStyle: 'italic', textAlign: 'center' },
  wave: { flexDirection: 'row', alignItems: 'center', gap: 4, height: 36 },
  waveBar: { width: 5, borderRadius: 3, backgroundColor: colors.terracotta },
  typeBox: { paddingHorizontal: space.lg },
  result: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.hairline,
    borderLeftWidth: 3,
    borderLeftColor: colors.terracotta,
    borderRadius: radius.md,
    paddingHorizontal: space.base,
    paddingVertical: space.md,
    marginTop: space.md,
  },
  resultRight: { alignItems: 'flex-end', gap: 4 },
  macros: { marginTop: 2 },
});
