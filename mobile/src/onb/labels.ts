/** Answer labels as the V3 screens word them. */
import type { ActivityLevel } from '@/utils/calories';

export const ACTIVITY_LABELS_V3: Record<ActivityLevel, string> = {
  sedentary: 'Mostly sitting',
  light: 'Lightly active',
  moderate: 'Active',
  active: 'Very active',
  very_active: 'Very active',
};
