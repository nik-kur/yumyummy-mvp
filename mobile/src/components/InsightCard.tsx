/**
 * InsightCard — shows a daily insight from the backend on the Today screen.
 *
 * Appears between the journey card and the advisor card once the user has
 * logged at least one day of data (the backend returns a motivational
 * fallback otherwise).
 */
import { View, StyleSheet } from 'react-native';
import { Sparkle, TrendingUp, AlertTriangle, Award } from 'lucide-react-native';

import { AppText } from './AppText';
import { Card } from './Card';
import { colors, space } from '@/theme/tokens';

const ICONS: Record<string, typeof Sparkle> = {
  sparkle: Sparkle,
  trending_up: TrendingUp,
  alert: AlertTriangle,
  award: Award,
};

interface InsightCardProps {
  insight: {
    id?: string;
    icon?: string;
    title?: string;
    body?: string;
  };
}

export function InsightCard({ insight }: InsightCardProps) {
  const IconComp = ICONS[insight.icon ?? ''] ?? Sparkle;

  return (
    <Card style={s.card}>
      <View style={s.iconWrap}>
        <IconComp size={18} color={colors.protein} strokeWidth={1.5} />
      </View>
      <View style={s.text}>
        {insight.title ? (
          <AppText variant="bodyStrong">{insight.title}</AppText>
        ) : null}
        {insight.body ? (
          <AppText variant="caption" color={colors.inkMuted}>{insight.body}</AppText>
        ) : null}
      </View>
    </Card>
  );
}

const s = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: space.md,
    borderColor: colors.oliveSoft,
    borderWidth: 1,
  },
  iconWrap: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.oliveSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  text: { flex: 1, gap: 4 },
});
