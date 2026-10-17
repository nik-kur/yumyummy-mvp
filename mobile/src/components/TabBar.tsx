import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { House, Bookmark, BarChart3, User, Plus, type LucideIcon } from 'lucide-react-native';
import * as Haptics from 'expo-haptics';

import { AppText } from './AppText';
import { useTourTarget } from './tour/TourOverlay';
import { track } from '@/analytics/posthog';
import { getOnboardingConfig } from '@/config/onboardingConfig';
import { useAuth } from '@/state/auth';
import { usePendingMeals } from '@/state/pendingMeals';
import { colors, radius, shadow, space } from '@/theme/tokens';

type TabName = 'index' | 'menu' | 'week' | 'profile';

const ICONS: Record<TabName, LucideIcon> = {
  index: House,
  menu: Bookmark,
  week: BarChart3,
  profile: User,
};
const LABELS: Record<TabName, string> = {
  index: 'Today',
  menu: 'My Menu',
  week: 'Week',
  profile: 'Profile',
};

interface TabBarProps {
  routes: { key: string; name: string }[];
  activeIndex: number;
  onNavigate: (name: string) => void;
}

/** Custom editorial tab bar: Today / My Menu / center "+" / Week / Profile. */
export function TabBar({ routes, activeIndex, onNavigate }: TabBarProps) {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const tourBarRef = useTourTarget('tabbar');
  const tourPlusRef = useTourTarget('plus');

  const activeName = routes[activeIndex]?.name;

  // Preview mode (21): the free log opens capture; anything past it opens
  // Last offer, as does Profile (there is no account to manage yet).
  const { status, profile } = useAuth();
  const { pending } = usePendingMeals();
  const preview = status === 'preview';
  // A log still in flight already holds the free log.
  const freeLogLeft =
    Boolean(profile?.preview_free_log_available) && getOnboardingConfig().free_first_log && pending.length === 0;
  const openLastOffer = (from: string) => {
    track('preview_gate', { from });
    router.push('/paywall?last_offer=1');
  };

  const go = (name: TabName) => {
    if (preview && name === 'profile') {
      openLastOffer('profile');
      return;
    }
    if (routes.some((r) => r.name === name)) onNavigate(name);
  };

  const Tab = ({ name }: { name: TabName }) => {
    const active = activeName === name;
    const color = active ? colors.ink : colors.inkFaint;
    const Icon = ICONS[name];
    return (
      <Pressable style={styles.tab} onPress={() => go(name)} hitSlop={8}>
        <Icon size={24} color={color} strokeWidth={1.5} />
        <AppText variant="eyebrow" color={color} style={styles.label}>
          {LABELS[name]}
        </AppText>
      </Pressable>
    );
  };

  const openCapture = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
    if (preview && !freeLogLeft) {
      openLastOffer('plus');
      return;
    }
    router.push('/capture');
  };

  return (
    <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, space.sm) }]} ref={tourBarRef} collapsable={false}>
      <Tab name="index" />
      <Tab name="menu" />
      <View style={styles.fabSlot}>
        <Pressable style={styles.fab} onPress={openCapture} hitSlop={8} ref={tourPlusRef}>
          <Plus size={28} color={colors.bg} strokeWidth={2} />
        </Pressable>
      </View>
      <Tab name="week" />
      <Tab name="profile" />
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
    paddingTop: space.sm,
    paddingHorizontal: space.sm,
  },
  tab: { flex: 1, alignItems: 'center', gap: 3, paddingVertical: 4 },
  label: { letterSpacing: 0.6 },
  fabSlot: { width: 72, alignItems: 'center', justifyContent: 'center' },
  fab: {
    width: 58,
    height: 58,
    borderRadius: radius.pill,
    backgroundColor: colors.ink,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: -28,
    borderWidth: 4,
    borderColor: colors.bg,
    ...shadow.float,
  },
});
