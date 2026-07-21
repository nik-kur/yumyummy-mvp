/**
 * Week 1 Report — shown at the end of the first week activation journey.
 *
 * Fetches aggregated stats from `/app/report/week1` and displays them in a
 * shareable card-like layout.
 */
import { useEffect, useState } from 'react';
import { View, StyleSheet, ActivityIndicator } from 'react-native';
import { useRouter } from 'expo-router';
import { ChevronLeft } from 'lucide-react-native';
import { Pressable } from 'react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { Button } from '@/components/Button';
import { SourcesLink } from '@/components/SourcesLink';
import * as api from '@/api/endpoints';
import { colors, radius, space } from '@/theme/tokens';
import { track } from '@/analytics/posthog';
import { maybeRequestReview } from '@/state/rateReview';

export default function Week1ReportScreen() {
  const router = useRouter();
  const [report, setReport] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getWeek1Report()
      .then((r) => {
        setReport(r);
        // Finishing the first week is a high point — a good, non-intrusive
        // moment to ask for a rating (guarded so it never nags).
        if (r?.has_data) void maybeRequestReview('week1_report');
      })
      .finally(() => setLoading(false));
    track('week1_report_viewed');
  }, []);

  if (loading || !report) {
    return (
      <Screen grow edges={['top', 'bottom', 'left', 'right']}>
        <View style={s.center}>
          <ActivityIndicator color={colors.terracotta} />
        </View>
      </Screen>
    );
  }

  const hasData = report.has_data as boolean;

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={s.topBar}>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={26} color={colors.inkMuted} strokeWidth={1.5} />
        </Pressable>
        <AppText variant="overline" color={colors.inkMuted}>WEEK 1 REPORT</AppText>
        <View style={{ width: 26 }} />
      </View>

      <AppText variant="display" style={s.title}>Your first week</AppText>

      {!hasData ? (
        <Card style={s.emptyCard}>
          <AppText variant="body" color={colors.inkMuted} center>
            {report.summary as string}
          </AppText>
        </Card>
      ) : (
        <>
          <View style={s.stats}>
            <StatCard label="Days logged" value={String(report.days_logged ?? 0)} />
            <StatCard label="Meals tracked" value={String(report.total_meals ?? 0)} />
            <StatCard label="Avg calories" value={`${report.avg_calories ?? 0}`} unit="kcal" />
            <StatCard label="On target" value={`${report.on_target_days ?? 0}/${report.days_logged ?? 0}`} unit="days" />
          </View>

          <Card style={s.macroCard}>
            <AppText variant="title" center>Average macros</AppText>
            <View style={s.macroRow}>
              <MacroStat label="Protein" value={report.avg_protein_g as number} color={colors.protein} />
              <MacroStat label="Fat" value={report.avg_fat_g as number} color={colors.fat} />
              <MacroStat label="Carbs" value={report.avg_carbs_g as number} color={colors.carbs} />
            </View>
          </Card>

          {(report.target_adjustment as any)?.suggested_calories && (
            <Card style={s.adjustCard}>
              <AppText variant="title">Target adjustment</AppText>
              <AppText variant="body" color={colors.inkMuted} style={s.adjustBody}>
                {(report.target_adjustment as any).reason}
              </AppText>
              <SourcesLink label="How we calculate targets — see sources" />
            </Card>
          )}

          <Card style={s.summaryCard}>
            <AppText variant="body" color={colors.inkMuted}>
              {report.summary as string}
            </AppText>
            <AppText variant="caption" color={colors.inkFaint} style={s.reportDisclaimer}>
              Informational only — not medical advice.
            </AppText>
          </Card>
        </>
      )}

      <Button
        label="Continue"
        onPress={() => router.back()}
        style={s.cta}
      />
    </Screen>
  );
}

function StatCard({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <Card style={s.statCard}>
      <AppText variant="h2" center>{value}</AppText>
      {unit && <AppText variant="caption" color={colors.inkMuted} center>{unit}</AppText>}
      <AppText variant="caption" color={colors.inkMuted} center>{label}</AppText>
    </Card>
  );
}

function MacroStat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <View style={s.macroStat}>
      <AppText variant="macroValue" color={color}>{Math.round(value)}g</AppText>
      <AppText variant="caption" color={colors.inkMuted}>{label}</AppText>
    </View>
  );
}

const s = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  topBar: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    marginTop: space.sm,
  },
  title: { marginTop: space.base, marginBottom: space.lg },
  stats: {
    flexDirection: 'row', flexWrap: 'wrap', gap: space.md, marginBottom: space.lg,
  },
  statCard: { flex: 1, minWidth: '45%' as any, alignItems: 'center', gap: 2 },
  macroCard: { marginBottom: space.lg },
  macroRow: { flexDirection: 'row', justifyContent: 'space-around', marginTop: space.md },
  macroStat: { alignItems: 'center', gap: 2 },
  adjustCard: { marginBottom: space.lg, borderColor: colors.warningSoft, borderWidth: 1.5, gap: space.sm },
  adjustBody: { marginTop: space.sm },
  summaryCard: { marginBottom: space.lg, gap: space.sm },
  reportDisclaimer: { marginTop: space.xs },
  emptyCard: { marginBottom: space.lg },
  cta: { marginTop: 'auto' },
});
