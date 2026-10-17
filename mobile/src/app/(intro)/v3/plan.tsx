/**
 * V3 screen 15 — Your plan is ready: daily calories and macros, then the goal:
 *   lose / cut  → "−6 kg by 31 December" with the stepped weight chart;
 *   gain        → "+4 kg by 20 January", the chart going up;
 *   zone        → "72 kg · your zone: 71–73 kg", a flat line in a band;
 *   recomp      → "Same weight · more muscle, less fat in 12 weeks";
 *   test O7 `plan: "ahead"` → milestones instead of the chart (moving weight only).
 * "Not medical advice" under the CTA (agreed 15 Oct, same text as sources.tsx).
 * Charts are the canvas SVGs with the person's numbers swapped in.
 */
import { useMemo } from 'react';
import { Image, StyleSheet, Text, View, useWindowDimensions } from 'react-native';
import Svg, { Path } from 'react-native-svg';

import { OnbButton } from '@/components/onb/OnbButton';
import { getOnboardingConfig } from '@/config/onboardingConfig';
import { OnbLayout } from '@/components/onb/OnbLayout';
import { SvgSpec, type SvgSpecData } from '@/components/onb/SvgSpec';
import { PLAN_CHARTS } from '@/onb/generated/planCharts';
import { direction, fmtKg, fmtStLb, formatLongDate, formatShortDate, planMode, type PlanMode } from '@/onb/plan';
import { IMG } from '@/onb/assets';
import { C, F, PAD } from '@/onb/theme';
import { useOnbScreen } from '@/onb/useOnbScreen';
import { useIntro } from '@/state/introContext';

const DISCLAIMER = 'YumYummy provides general nutrition information for healthy adults. It is not medical advice.';
const RECOMP_WEEKS = 12;

/** Swap chart labels; widen a pill drawn right under a swapped label so the text fits. */
function withLabels(spec: SvgSpecData, labels: Record<string, string>): SvgSpecData {
  const els = spec.els.map((e) => ({ ...e }));
  for (let i = 0; i < els.length; i += 1) {
    const e = els[i];
    if (e.t !== 'text' || !(e.children in labels)) continue;
    const text = labels[e.children];
    e.children = text;
    const pill = els[i - 1];
    if (pill && pill.t === 'rect' && pill.rx) {
      const right = Number(pill.x) + Number(pill.width);
      const width = Math.max(Number(pill.width), Math.round(text.length * 7 + 18));
      pill.width = String(width);
      pill.x = String(right - width);
      e.x = String(right - width / 2);
    }
  }
  return { ...spec, els };
}

function Macro({ grams, label, bg, fg }: { grams: number; label: string; bg: string; fg: string }) {
  return (
    <View style={[s.macro, { backgroundColor: bg }]}>
      <Text style={[s.macroValue, { color: fg }]}>{grams} g</Text>
      <Text style={[s.macroLabel, { color: fg }]}>{label}</Text>
    </View>
  );
}

function Milestone({ title, sub, weight, filled }: { title: string; sub: string; weight: string; filled?: boolean }) {
  return (
    <View style={s.mile}>
      <View style={[s.dot, filled && s.dotFilled]} />
      <View style={s.mileText}>
        <Text style={s.mileTitle}>{title}</Text>
        <Text style={s.mileSub}>{sub}</Text>
      </View>
      <Text style={s.mileWeight}>{weight}</Text>
    </View>
  );
}

export default function PlanScreen() {
  const intro = useIntro();
  const target = intro.target_weight_kg ?? intro.weight_kg;
  const mode: PlanMode = planMode(intro.goal_type ?? 'just_track', direction(intro.weight_kg, target));
  const { config, content, next } = useOnbScreen('S15_plan', `${mode}_${getOnboardingConfig().plan}`);
  const { width } = useWindowDimensions();
  const chartW = width - PAD.side * 2 - 34;
  const imperial = intro.units === 'imperial';
  const show = (kg: number) => (imperial ? fmtStLb(kg) : `${fmtKg(kg)} kg`);
  const moving = mode === 'lose' || mode === 'cut' || mode === 'gain';
  const ahead = config.plan === 'ahead' && moving;

  const diff = target - intro.weight_kg;
  const date = intro.target_date;
  const zoneLo = show(Math.round(intro.weight_kg) - 1);
  const zoneHi = show(Math.round(intro.weight_kg) + 1);

  const head = useMemo(() => {
    if (mode === 'recomp') return { big: 'Same weight', small: `more muscle, less fat in ${RECOMP_WEEKS} weeks`, size: 40 };
    if (mode === 'zone') return { big: show(intro.weight_kg), small: `your zone: ${zoneLo.replace(/ kg$/, '')}–${zoneHi}`, size: 52 };
    const sign = diff < 0 ? '−' : '+';
    return { big: `${sign}${show(Math.abs(diff))}`, small: date ? `by ${formatLongDate(date)}` : '', size: 52 };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, diff, date, intro.weight_kg, imperial]);

  const chart = useMemo(() => {
    if (mode === 'recomp') {
      return withLabels(PLAN_CHARTS.PlanReveal_recomp, { 'Weight ~72 kg': `Weight ~${show(intro.weight_kg)}` });
    }
    if (mode === 'zone') {
      return withLabels(PLAN_CHARTS.PlanReveal_maintain, {
        'Your zone · 71–73 kg': `Your zone · ${zoneLo.replace(/ kg$/, '')}–${zoneHi}`,
        '72 kg': show(intro.weight_kg),
      });
    }
    if (mode === 'gain') {
      return withLabels(PLAN_CHARTS.PlanReveal_gain, { '75 kg': show(intro.weight_kg), '79 kg': show(target) });
    }
    return withLabels(PLAN_CHARTS.PlanReveal, { '72 kg': show(intro.weight_kg), '66 kg': show(target) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, intro.weight_kg, target, imperial]);

  const endLabel =
    mode === 'recomp' ? `In ${RECOMP_WEEKS} weeks` : mode === 'zone' ? 'In 3 months' : date ? formatShortDate(date) : '';

  const milestones = useMemo(() => {
    if (!ahead || !date) return null;
    const today = new Date();
    const inTwo = new Date();
    inTwo.setDate(today.getDate() + 14);
    const long = (d: Date) => d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long' });
    const down = diff < 0;
    const step = Math.min(1, Math.abs(diff));
    return [
      {
        title: `Today · ${long(today)}`,
        sub: `Your plan starts: ${(intro.target_calories ?? 0).toLocaleString('en-GB')} kcal and ${intro.target_protein_g ?? 0} g protein a day.`,
        weight: show(intro.weight_kg),
      },
      {
        title: `In 2 weeks · ${long(inTwo)}`,
        sub: down ? 'Your first kilo down, and logging feels easy.' : 'Your first kilo up, and logging feels easy.',
        weight: show(intro.weight_kg + (down ? -step : step)),
      },
      {
        title: formatLongDate(date),
        sub: `Goal reached: ${show(Math.abs(diff))} ${down ? 'lighter' : 'heavier'}.`,
        weight: show(target),
        filled: true,
      },
    ];
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ahead, date, diff, intro.target_calories, intro.target_protein_g, intro.weight_kg, target, imperial]);

  return (
    <OnbLayout
      progress={null}
      footer={
        <>
          <OnbButton label="Start my plan" onPress={() => next({}, { plan_mode: mode, plan_view: ahead ? 'ahead' : 'chart' })} />
          <Text style={s.disclaimer}>{DISCLAIMER}</Text>
        </>
      }
    >
      <View style={{ flex: 0.3 }} />
      <View style={s.check}>
        <Svg width={17} height={17} viewBox="0 0 24 24" fill="none">
          <Path d="M20 6 9 17l-5-5" stroke="#FFFFFF" strokeWidth={2.6} strokeLinecap="round" strokeLinejoin="round" />
        </Svg>
      </View>
      <Text style={s.h1}>Your plan is ready</Text>

      <View style={[s.card, s.kcalCard]}>
        <View style={s.baseline}>
          <Text style={s.kcal}>{(intro.target_calories ?? 0).toLocaleString('en-GB')}</Text>
          <Text style={s.kcalUnit}>kcal a day</Text>
        </View>
        <View style={s.macros}>
          <Macro grams={intro.target_protein_g ?? 0} label="Protein" bg="#E3E6CE" fg={C.protein} />
          <Macro grams={intro.target_fat_g ?? 0} label="Fat" bg="#FBEFD6" fg={C.fat} />
          <Macro grams={intro.target_carbs_g ?? 0} label="Carbs" bg={C.infoSoft} fg={C.carbs} />
        </View>
      </View>

      <View style={[s.card, ahead ? s.aheadCard : s.goalCard]}>
        <View style={[s.baseline, s.wrap]}>
          <Text style={[s.goalBig, { fontSize: head.size, lineHeight: head.size + 4 }]}>{head.big}</Text>
          {head.small ? <Text style={s.goalSmall}>{head.small}</Text> : null}
        </View>
        {milestones ? (
          <>
            <Text style={s.aheadTitle}>See what’s ahead</Text>
            <View>
              <View style={s.rail} />
              {milestones.map((m) => (
                <Milestone key={m.title} {...m} />
              ))}
            </View>
          </>
        ) : (
          <>
            <View style={s.chart}>
              <SvgSpec spec={chart} width={chartW} />
            </View>
            <View style={s.axis}>
              <Text style={s.axisText}>Today</Text>
              <Text style={s.axisText}>{endLabel}</Text>
            </View>
          </>
        )}
      </View>

      {/* The first-week ladder (state/journey.ts) is what turns the plan into a habit. */}
      <View style={s.guide}>
        <Image source={IMG.mascot_great} style={s.guideIcon} accessibilityIgnoresInvertColors />
        <View style={s.guideText}>
          <Text style={s.guideTitle}>{content.texts['plan.guide_title'] ?? 'We designed your first 7 days'}</Text>
          <Text style={s.guideSub} numberOfLines={1} adjustsFontSizeToFit minimumFontScale={0.85}>
            {content.texts['plan.guide_sub'] ?? 'A personal start to make your plan stick'}
          </Text>
        </View>
      </View>
      <View style={{ flex: 1 }} />
    </OnbLayout>
  );
}

const s = StyleSheet.create({
  check: {
    alignSelf: 'center',
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: C.terra,
    alignItems: 'center',
    justifyContent: 'center',
  },
  h1: { marginTop: 10, textAlign: 'center', fontFamily: F.serif, fontSize: 30, lineHeight: 36, letterSpacing: -0.3, color: C.ink },
  card: { backgroundColor: C.surface, borderWidth: 1, borderColor: C.hair, borderRadius: 16 },
  kcalCard: { marginTop: 16, padding: 18 },
  goalCard: { marginTop: 10, paddingTop: 16, paddingHorizontal: 16, paddingBottom: 14 },
  aheadCard: { marginTop: 10, paddingTop: 16, paddingHorizontal: 16, paddingBottom: 6 },
  baseline: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'center', columnGap: 8 },
  wrap: { flexWrap: 'wrap' },
  kcal: { fontFamily: F.serif, fontSize: 52, lineHeight: 56, color: C.ink, fontVariant: ['tabular-nums'] },
  kcalUnit: { fontFamily: F.sans, fontSize: 15, color: C.muted },
  macros: { marginTop: 14, flexDirection: 'row', gap: 8 },
  macro: { flex: 1, borderRadius: 12, paddingVertical: 10, paddingHorizontal: 6, alignItems: 'center', gap: 1 },
  macroValue: { fontFamily: F.sansSemibold, fontSize: 17, lineHeight: 22 },
  macroLabel: { fontFamily: F.sans, fontSize: 13, lineHeight: 18 },
  goalBig: { fontFamily: F.serif, color: C.terra, fontVariant: ['tabular-nums'] },
  goalSmall: { fontFamily: F.sans, fontSize: 15, lineHeight: 22, color: C.muted },
  chart: { marginTop: 10 },
  axis: { marginTop: 4, height: 18, flexDirection: 'row', justifyContent: 'space-between' },
  axisText: { fontFamily: F.sans, fontSize: 13, lineHeight: 18, color: C.muted },
  guide: {
    marginTop: 10,
    marginBottom: 16,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: C.paper2,
    borderRadius: 16,
    paddingVertical: 10,
    paddingHorizontal: 12,
  },
  // Big on purpose; the negative margin keeps the plaque from growing as much.
  guideIcon: { width: 60, height: 60, marginVertical: -10, marginLeft: -6, marginRight: -4 },
  guideText: { flex: 1, gap: 1 },
  guideTitle: { fontFamily: F.sansSemibold, fontSize: 15, lineHeight: 20, color: C.ink },
  guideSub: { fontFamily: F.sans, fontSize: 14, lineHeight: 20, color: C.muted },
  aheadTitle: { marginTop: 14, fontFamily: F.serif, fontSize: 18, lineHeight: 24, color: C.ink },
  rail: { position: 'absolute', left: 6, top: 32, bottom: 32, width: 2, backgroundColor: C.terraSoft },
  mile: { height: 64, flexDirection: 'row', alignItems: 'center', gap: 14 },
  dot: { width: 14, height: 14, borderRadius: 7, borderWidth: 2, borderColor: C.terra, backgroundColor: C.surface },
  dotFilled: { backgroundColor: C.terra },
  mileText: { flex: 1 },
  mileTitle: { fontFamily: F.sansSemibold, fontSize: 15, lineHeight: 20, color: C.ink },
  mileSub: { fontFamily: F.sans, fontSize: 14, lineHeight: 19, color: C.muted },
  mileWeight: { fontFamily: F.sansSemibold, fontSize: 15, color: C.ink, fontVariant: ['tabular-nums'] },
  disclaimer: { marginTop: 10, textAlign: 'center', fontFamily: F.sans, fontSize: 12, lineHeight: 16, color: C.muted },
});
