/**
 * Science & sources — citations for every calculation and recommendation the
 * app makes (App Review Guideline 1.4.1: apps with health information must
 * cite their sources, and the citations must be easy to find).
 *
 * Linked from Profile → Support, both plan screens, the target-pace screen,
 * the AI advisor and the Week 1 report.
 */
import { View, StyleSheet, Pressable, Linking, Alert } from 'react-native';
import { useRouter } from 'expo-router';
import { ChevronLeft, ExternalLink } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Card } from '@/components/Card';
import { colors, space } from '@/theme/tokens';

interface Source {
  title: string;
  detail: string;
  url: string;
}

interface Section {
  heading: string;
  blurb: string;
  sources: Source[];
}

const SECTIONS: Section[] = [
  {
    heading: 'Calorie & macro targets',
    blurb:
      'Your daily calorie target starts from the Mifflin–St Jeor resting-energy equation, scaled by a standard activity factor. Macro targets follow accepted reference ranges.',
    sources: [
      {
        title: 'Mifflin–St Jeor equation',
        detail:
          'Mifflin MD, St Jeor ST, et al. Am J Clin Nutr, 1990 — the resting-energy formula behind your calorie target',
        url: 'https://pubmed.ncbi.nlm.nih.gov/2305711/',
      },
      {
        title: 'Activity multipliers (TDEE)',
        detail: 'FAO/WHO/UNU — Human Energy Requirements, 2004',
        url: 'https://www.fao.org/4/y5686e/y5686e00.htm',
      },
      {
        title: 'Macronutrient ranges',
        detail:
          'Institute of Medicine — Dietary Reference Intakes for Energy, Carbohydrate, Fat and Protein, 2005',
        url: 'https://nap.nationalacademies.org/catalog/10490/dietary-reference-intakes-for-energy-carbohydrate-fiber-fat-fatty-acids-cholesterol',
      },
      {
        title: 'Protein targets',
        detail:
          'Morton RW, et al. Br J Sports Med, 2018 — meta-analysis of 49 trials on protein intake and lean mass',
        url: 'https://pubmed.ncbi.nlm.nih.gov/28698222/',
      },
    ],
  },
  {
    heading: 'Weight change & safe pacing',
    blurb:
      'Projected pace uses the ≈7,700 kcal-per-kilogram energy approximation. Pacing warnings, minimum-calorie floors and the healthy-weight limit follow public-health guidance.',
    sources: [
      {
        title: '≈7,700 kcal per kilogram',
        detail: 'Wishnofsky M. Am J Clin Nutr, 1958 — caloric equivalents of gained or lost weight',
        url: 'https://pubmed.ncbi.nlm.nih.gov/13594881/',
      },
      {
        title: 'Safe rate of weight loss',
        detail:
          'NIH / NHLBI — Clinical Guidelines on the Identification, Evaluation, and Treatment of Overweight and Obesity in Adults',
        url: 'https://www.nhlbi.nih.gov/files/docs/guidelines/ob_gdlns.pdf',
      },
      {
        title: 'Healthy weight range (BMI)',
        detail: 'World Health Organization — Obesity and overweight fact sheet',
        url: 'https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight',
      },
    ],
  },
  {
    heading: 'Why tracking helps',
    blurb: 'The studies quoted during onboarding.',
    sources: [
      {
        title: 'Food diaries and weight loss',
        detail: 'Hollis JF, et al. Am J Prev Med, 2008 — Kaiser Permanente study of 1,685 adults',
        url: 'https://pubmed.ncbi.nlm.nih.gov/18617080/',
      },
      {
        title: 'Keeping weight off long-term',
        detail:
          'Wing RR, Phelan S. Am J Clin Nutr, 2005 — National Weight Control Registry findings',
        url: 'https://pubmed.ncbi.nlm.nih.gov/16002825/',
      },
      {
        title: 'People misjudge intake by ~30%',
        detail: 'Lichtman SW, et al. New England Journal of Medicine, 1992',
        url: 'https://pubmed.ncbi.nlm.nih.gov/1454084/',
      },
    ],
  },
  {
    heading: 'Food & nutrition data',
    blurb:
      'Meal nutrition estimates are checked against public food databases. Every logged meal also lists its own sources on the meal screen.',
    sources: [
      {
        title: 'USDA FoodData Central',
        detail: 'U.S. Department of Agriculture — reference nutrition database',
        url: 'https://fdc.nal.usda.gov/',
      },
      {
        title: 'Open Food Facts',
        detail: 'Open database of packaged food products',
        url: 'https://world.openfoodfacts.org/',
      },
    ],
  },
];

function openUrl(url: string) {
  Linking.openURL(url).catch(() => Alert.alert('Could not open link', url));
}

function SourceRow({ source, last }: { source: Source; last?: boolean }) {
  return (
    <Pressable onPress={() => openUrl(source.url)} style={[styles.row, !last && styles.rowBorder]}>
      <View style={styles.rowText}>
        <AppText variant="bodyStrong">{source.title}</AppText>
        <AppText variant="caption" color={colors.inkMuted}>
          {source.detail}
        </AppText>
      </View>
      <ExternalLink size={16} color={colors.infoBlue} strokeWidth={1.5} />
    </Pressable>
  );
}

export default function SourcesScreen() {
  const router = useRouter();

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={26} color={colors.inkMuted} strokeWidth={1.5} />
        </Pressable>
        <AppText variant="overline" color={colors.inkMuted}>
          Science & sources
        </AppText>
        <View style={{ width: 26 }} />
      </View>

      <AppText variant="h1" style={styles.title}>
        Where our numbers come from
      </AppText>
      <AppText variant="body" color={colors.inkMuted} style={styles.lead}>
        Every number YumYummy shows — calorie targets, macros, pacing and projections — is based on
        published research and public guidelines. Tap any source to read it.
      </AppText>

      {SECTIONS.map((section) => (
        <View key={section.heading}>
          <AppText variant="overline" color={colors.inkMuted} style={styles.sectionLabel}>
            {section.heading}
          </AppText>
          <AppText variant="caption" color={colors.inkFaint} style={styles.sectionBlurb}>
            {section.blurb}
          </AppText>
          <Card padded={false}>
            {section.sources.map((source, i) => (
              <SourceRow key={source.url} source={source} last={i === section.sources.length - 1} />
            ))}
          </Card>
        </View>
      ))}

      <Card flat style={styles.disclaimerCard}>
        <AppText variant="bodyStrong">Not medical advice</AppText>
        <AppText variant="small" color={colors.inkMuted}>
          YumYummy provides general nutrition information for healthy adults. It is not medical
          advice, diagnosis or treatment, and it is not a substitute for guidance from a doctor or
          registered dietitian. Always consult a qualified professional before making significant
          changes to your diet — especially if you are pregnant, nursing, under 18, or managing a
          medical condition such as diabetes or an eating disorder.
        </AppText>
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({
  topBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: space.sm,
  },
  title: { marginTop: space.base },
  lead: { marginTop: space.xs },
  sectionLabel: { marginTop: space.lg },
  sectionBlurb: { marginTop: space.xs, marginBottom: space.sm },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    paddingHorizontal: space.base,
    paddingVertical: space.md,
  },
  rowBorder: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.hairline },
  rowText: { flex: 1, gap: 2 },
  disclaimerCard: {
    marginTop: space.lg,
    marginBottom: space.base,
    gap: space.sm,
    backgroundColor: colors.surfaceAlt,
  },
});
