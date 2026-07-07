import type { MealAssessment } from '@/api/types';

/**
 * Human sentence for the "How we got this" card, rendered from the additive
 * machine-readable `assessment` the 25(1)+ server returns. Older meals (no
 * assessment stored) fall back to the generic copy at the call site.
 */
export function assessmentText(a: MealAssessment): string {
  const domain = a.domain ? ` (${a.domain})` : '';
  const parts: string[] = [];

  switch (a.method) {
    case 'label':
      parts.push('Read straight off the nutrition label in your photo — exact numbers.');
      break;
    case 'off':
      parts.push('Found by barcode in the OpenFoodFacts product database.');
      break;
    case 'official':
      parts.push(`Verified on the brand’s official site${domain}.`);
      break;
    case 'web':
      parts.push(
        a.domain
          ? `Checked against a live page${domain}.`
          : 'Checked against live pages — see the per-item links.',
      );
      break;
    case 'usda':
      parts.push('Matched to the USDA FoodData Central database.');
      break;
    case 'usda_components':
      parts.push('Broke the dish into components and matched each to USDA FoodData Central.');
      break;
    case 'photo': {
      const v = a.verified_items ?? 0;
      const t = a.total_items ?? 0;
      parts.push(
        t > 0 && v > 0
          ? `Identified from your photo; ${v} of ${t} component${t === 1 ? '' : 's'} verified against sources.`
          : 'Identified from your photo and checked against sources.',
      );
      break;
    }
    default:
      parts.push('AI estimate — no verifiable source was found for this one.');
      break;
  }

  if (a.portion_estimated && a.method !== 'photo' && a.method !== 'estimate') {
    parts.push('Portion size was estimated.');
  }
  return parts.join(' ');
}
