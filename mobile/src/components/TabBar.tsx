import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { House, Bookmark, BarChart3, User, Plus, type LucideIcon } from 'lucide-react-native';
import * as Haptics from 'expo-haptics';

import { AppText } from './AppText';
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

  const activeName = routes[activeIndex]?.name;

  const go = (name: TabName) => {
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
    router.push('/capture');
  };

  return (
    <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, space.sm) }]}>
      <Tab name="index" />
      <Tab name="menu" />
      <View style={styles.fabSlot}>
        <Pressable style={styles.fab} onPress={openCapture} hitSlop={8}>
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
