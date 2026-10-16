/**
 * V3 screen 8 — Proof 2×: people with a daily food diary lost twice as much
 * weight (Hollis et al., Kaiser Permanente, Am J Prev Med 2008, n = 1,685).
 */
import { StyleSheet, Text, View } from 'react-native';

import { OnbButton } from '@/components/onb/OnbButton';
import { OnbLayout } from '@/components/onb/OnbLayout';
import { SourceLink } from '@/components/onb/SourceLink';
import { C, F } from '@/onb/theme';
import { useOnbScreen } from '@/onb/useOnbScreen';

const STUDY_URL = 'https://pubmed.ncbi.nlm.nih.gov/18617080/';

function Bar({ label, height, value, strong }: { label: string; height: number; value: string; strong?: boolean }) {
  return (
    <View style={s.col}>
      <View style={s.colLabelBox}>
        <Text style={s.colLabel}>{label}</Text>
      </View>
      <View style={s.well}>
        <View style={[s.bar, { height, backgroundColor: strong ? C.terra : C.hair }]}>
          <Text style={[s.barValue, strong ? s.barStrong : s.barWeak]}>{value}</Text>
        </View>
      </View>
    </View>
  );
}

export default function ProofScreen() {
  const { content, next, progress } = useOnbScreen('S8_proof');
  const t = (k: string, d: string) => content.texts[`proof.${k}`] ?? d;
  return (
    <OnbLayout
      progress={progress}
      title={
        <Text style={s.title}>
          People who track lose <Text style={{ color: C.terra }}>2×</Text> more weight
        </Text>
      }
      footer={<OnbButton label="Continue" onPress={() => next()} />}
    >
      <View style={s.card}>
        <View style={s.cols}>
          <Bar label={'Without a\nfood diary'} height={64} value="1×" />
          <Bar label={'With a daily\nfood diary'} height={158} value="2×" strong />
        </View>
      </View>
      <Text style={s.body}>
        {t(
          'body',
          'In a study of 1,685 adults, people who kept a daily food diary lost twice as much weight. YumYummy makes it a 10-second habit.',
        )}
      </Text>
      <SourceLink label="Kaiser Permanente study of 1,685 adults · Am J Prev Med, 2008" url={STUDY_URL} style={s.link} />
      <View style={{ flex: 1 }} />
    </OnbLayout>
  );
}

const s = StyleSheet.create({
  title: { marginTop: 24, fontFamily: F.serif, fontSize: 32, lineHeight: 38, letterSpacing: -0.32, color: C.ink },
  card: {
    marginTop: 24,
    backgroundColor: C.surface,
    borderWidth: 1,
    borderColor: C.hair,
    borderRadius: 16,
    padding: 18,
  },
  cols: { flexDirection: 'row', gap: 14 },
  col: { flex: 1, gap: 10 },
  colLabelBox: { height: 36, justifyContent: 'flex-end' },
  colLabel: { textAlign: 'center', fontFamily: F.sansSemibold, fontSize: 14, lineHeight: 18, color: C.ink },
  well: { height: 190, borderRadius: 12, backgroundColor: C.paper, padding: 8, justifyContent: 'flex-end' },
  bar: { borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  barValue: { fontFamily: F.serif },
  barWeak: { fontSize: 22, color: C.muted },
  barStrong: { fontSize: 30, color: C.white },
  body: { marginTop: 16, fontFamily: F.sans, fontSize: 15, lineHeight: 22, color: C.muted },
  link: { marginTop: 10, alignSelf: 'flex-start' },
});
