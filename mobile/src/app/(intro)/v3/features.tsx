/**
 * V3 screen 12 — Features, by answer:
 *   tracked before → the barrier from screen 10 leads ("We heard you");
 *   first time → a long-term chart by weight direction from screen 7
 *   (down: vs a traditional diet; same: vs yo-yo dieting; up: muscle vs
 *   eating by feel).
 * Copy and charts come 1:1 from the canvas (`generated/features.ts`).
 */
import { Image, StyleSheet, Text, View, useWindowDimensions } from 'react-native';

import { OnbButton } from '@/components/onb/OnbButton';
import { OnbLayout } from '@/components/onb/OnbLayout';
import { SourceLink } from '@/components/onb/SourceLink';
import { SvgSpec } from '@/components/onb/SvgSpec';
import { IMG } from '@/onb/assets';
import type { FeatureRow } from '@/onb/featuresTypes';
import { FEATURES } from '@/onb/generated/features';
import { direction } from '@/onb/plan';
import { C, F, PAD, SHADOW } from '@/onb/theme';
import { useOnbScreen } from '@/onb/useOnbScreen';
import { useIntro } from '@/state/introContext';
import type { IntroDraft } from '@/state/introDraft';

/**
 * Claims replaced after the canvas (Nikita, 16 Oct): the "80% of users…
 * maintain their weight loss" line had no source. Harvey et al. 2019 matches
 * the chart's 6-month span; the wording follows the authors' conclusion
 * (logging frequency was significantly related to weight loss).
 */
const CLAIM_OVERRIDES: Record<string, { claim: string; source: string }> = {
  Features_no: {
    claim: 'In a 6-month study of 142 adults, the people who logged their meals most often lost the most weight.',
    source: 'Log Often, Lose More · Obesity, 2019',
  },
};

const SOURCES: Record<string, string> = {
  'Log Often, Lose More · Obesity, 2019': 'https://pubmed.ncbi.nlm.nih.gov/30801989/',
  'National Weight Control Registry · Am J Clin Nutr, 2005': 'https://pubmed.ncbi.nlm.nih.gov/16002825/',
  'Meta-analysis of 49 trials · Br J Sports Med, 2018': 'https://pubmed.ncbi.nlm.nih.gov/28698222/',
};

function variantFor(d: IntroDraft): string {
  if (d.tracked_before) {
    switch (d.barrier) {
      case 'accuracy':
        return 'Features_yes_accuracy';
      case 'gave_up':
        return 'Features_yes_gave_up';
      case 'eating_out':
        return 'Features_yes_eating_out';
      case 'other':
        return 'Features_yes_other';
      default:
        return 'Features_yes';
    }
  }
  const dir = direction(d.weight_kg, d.target_weight_kg ?? d.weight_kg);
  return dir === 'down' ? 'Features_no' : dir === 'up' ? 'Features_no_up' : 'Features_no_same';
}

function icon(name: string) {
  return IMG[name as keyof typeof IMG];
}

function HeroRow({ row }: { row: FeatureRow }) {
  return (
    <View style={s.heroRow}>
      <Image source={icon(row.icon)} style={s.heroIcon} />
      <View style={s.heroText}>
        <Text style={s.heroTitle}>{row.title}</Text>
        <Text style={s.heroSub}>{row.sub}</Text>
      </View>
    </View>
  );
}

export default function FeaturesScreen() {
  const intro = useIntro();
  const key = variantFor(intro);
  const { content, next, progress } = useOnbScreen('S12_features', key.replace('Features_', ''));
  const { width } = useWindowDimensions();
  const a = { ...FEATURES[key], ...(CLAIM_OVERRIDES[key] ?? {}) };
  const claimKey = `features.${key.replace('Features_', '')}.claim`;

  return (
    <OnbLayout progress={progress} title={a.title} footer={<OnbButton label="Continue" onPress={() => next()} />}>
      {a.hero ? (
        <View style={[s.card, s.heroCard, SHADOW]}>
          <Text style={s.cardTitle}>YumYummy is different</Text>
          <View style={s.heroList}>
            {a.hero.map((row, i) => (
              <View key={row.title}>
                {i > 0 ? <View style={s.divider} /> : null}
                <HeroRow row={row} />
              </View>
            ))}
          </View>
        </View>
      ) : (
        <View style={[s.card, s.chartCard, SHADOW]}>
          <Text style={s.chartLabel}>{a.chartLabel}</Text>
          {a.chart ? (
            <View style={s.chart}>
              <SvgSpec spec={a.chart} width={width - PAD.side * 2 - 42} />
            </View>
          ) : null}
          <View style={s.months}>
            <Text style={s.month}>Month 1</Text>
            <Text style={s.month}>Month 6</Text>
          </View>
          <Text style={s.claim}>{content.texts[claimKey] ?? a.claim}</Text>
          {a.source && SOURCES[a.source] ? (
            <SourceLink label={a.source} url={SOURCES[a.source]} style={s.source} />
          ) : null}
        </View>
      )}
      <Text style={s.also}>Also in YumYummy</Text>
      <View style={s.alsoList}>
        {a.also.map((row) => (
          <View key={row.title} style={s.alsoRow}>
            <Image source={icon(row.icon)} style={s.alsoIcon} />
            <View style={s.alsoText}>
              <Text style={s.alsoTitle}>{row.title}</Text>
              <Text style={s.alsoSub}>{row.sub}</Text>
            </View>
          </View>
        ))}
      </View>
      <View style={{ flex: 1 }} />
    </OnbLayout>
  );
}

const s = StyleSheet.create({
  card: { marginTop: 20, backgroundColor: C.surface, borderWidth: 1, borderColor: C.hair, borderRadius: 16 },
  heroCard: { padding: 18 },
  chartCard: { paddingVertical: 16, paddingHorizontal: 20 },
  cardTitle: { fontFamily: F.serif, fontSize: 22, lineHeight: 28, color: C.ink },
  heroList: { marginTop: 14 },
  heroRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  heroIcon: { width: 56, height: 56 },
  heroText: { flex: 1, gap: 3 },
  heroTitle: { fontFamily: F.sansSemibold, fontSize: 17, lineHeight: 22, color: C.ink },
  heroSub: { fontFamily: F.sans, fontSize: 15, lineHeight: 21, color: C.muted },
  divider: { height: 1, backgroundColor: C.hair, marginVertical: 14 },
  chartLabel: { fontFamily: F.sansSemibold, fontSize: 15, lineHeight: 20, color: C.ink },
  chart: { marginTop: 8 },
  months: { marginTop: 6, flexDirection: 'row', justifyContent: 'space-between' },
  month: { fontFamily: F.sans, fontSize: 13, lineHeight: 18, color: C.muted },
  claim: { marginTop: 12, textAlign: 'center', fontFamily: F.sans, fontSize: 14, lineHeight: 20, color: C.muted },
  source: { marginTop: 6, alignSelf: 'center' },
  also: { marginTop: 24, fontFamily: F.sansSemibold, fontSize: 14, lineHeight: 18, color: C.muted },
  alsoList: { marginTop: 14, gap: 16 },
  alsoRow: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  alsoIcon: { width: 44, height: 44 },
  alsoText: { flex: 1, gap: 1 },
  alsoTitle: { fontFamily: F.sansSemibold, fontSize: 16, lineHeight: 21, color: C.ink },
  alsoSub: { fontFamily: F.sans, fontSize: 14, lineHeight: 19, color: C.muted },
});
