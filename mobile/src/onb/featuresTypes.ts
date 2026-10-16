/** Shapes of the data extracted from the Features artboards (`scripts/v3_extract.py`). */
import type { SvgSpecData } from '@/components/onb/SvgSpec';

export interface FeatureRow {
  icon: string;
  title: string;
  sub: string;
}

export interface FeaturesArtboard {
  title: string;
  also: FeatureRow[];
  hero?: FeatureRow[];
  chartLabel?: string;
  chart?: SvgSpecData;
  claim?: string;
  source?: string | null;
}
