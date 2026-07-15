import { View, Pressable, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { ChevronLeft } from 'lucide-react-native';

import { Screen } from '@/components/Screen';
import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Chip } from '@/components/Chip';
import { SegmentedControl } from '@/components/SegmentedControl';
import { WheelPicker } from '@/components/WheelPicker';
import { useOnboarding } from '@/state/onboarding';
import { ACTIVITY_LABELS, type ActivityLevel, type Gender } from '@/utils/calories';
import { colors, space } from '@/theme/tokens';

function range(start: number, end: number): number[] {
  return Array.from({ length: end - start + 1 }, (_, i) => start + i);
}

const AGES = range(14, 90);
const HEIGHTS = range(130, 220);
const WEIGHTS = range(40, 160);
const ACTIVITIES = Object.keys(ACTIVITY_LABELS) as ActivityLevel[];

export default function ProfileScreen() {
  const router = useRouter();
  const { gender, age, height_cm, weight_kg, activity_level, set } = useOnboarding();

  const ready = gender !== null && activity_level !== null;

  return (
    <Screen scroll grow edges={['top', 'bottom', 'left', 'right']}>
      <View style={styles.topBar}>
        <Pressable onPress={() => router.back()} hitSlop={10}>
          <ChevronLeft size={26} color={colors.inkMuted} strokeWidth={1.5} />
        </Pressable>
      </View>
      <View style={styles.header}>
        <AppText variant="overline" color={colors.inkMuted}>
          Step 2 of 3
        </AppText>
        <AppText variant="h1" style={styles.title}>
          A few details
        </AppText>
        <AppText variant="body" color={colors.inkMuted}>
          Used only to estimate your energy needs.
        </AppText>
      </View>

      <View style={styles.block}>
        <AppText variant="overline" color={colors.inkMuted}>
          Sex
        </AppText>
        <SegmentedControl<Gender>
          options={[
            { label: 'Male', value: 'male' },
            { label: 'Female', value: 'female' },
          ]}
          value={gender}
          onChange={(v) => set({ gender: v })}
        />
      </View>

      <View style={styles.wheelsRow}>
        <View style={styles.wheelCol}>
          <AppText variant="overline" color={colors.inkMuted} center>
            Age
          </AppText>
          <WheelPicker values={AGES} value={age} onChange={(v) => set({ age: v })} />
        </View>
        <View style={styles.wheelCol}>
          <AppText variant="overline" color={colors.inkMuted} center>
            Height · cm
          </AppText>
          <WheelPicker values={HEIGHTS} value={height_cm} onChange={(v) => set({ height_cm: v })} />
        </View>
        <View style={styles.wheelCol}>
          <AppText variant="overline" color={colors.inkMuted} center>
            Weight · kg
          </AppText>
          <WheelPicker values={WEIGHTS} value={weight_kg} onChange={(v) => set({ weight_kg: v })} />
        </View>
      </View>

      <View style={styles.block}>
        <AppText variant="overline" color={colors.inkMuted}>
          Activity level
        </AppText>
        <View style={styles.chips}>
          {ACTIVITIES.map((a) => (
            <Chip
              key={a}
              label={ACTIVITY_LABELS[a]}
              selected={activity_level === a}
              onPress={() => set({ activity_level: a })}
            />
          ))}
        </View>
      </View>

      <Button
        label="Continue"
        disabled={!ready}
        onPress={() => router.push('/(onboarding)/plan')}
        style={styles.cta}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  topBar: { marginTop: space.sm, marginLeft: -space.xs, alignSelf: 'flex-start' },
  header: { marginTop: space.md, marginBottom: space.lg, gap: space.xs },
  title: { marginTop: space.xs },
  block: { gap: space.sm, marginBottom: space.xl },
  wheelsRow: { flexDirection: 'row', gap: space.sm, marginBottom: space.xl },
  wheelCol: { flex: 1, gap: space.sm },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: space.sm },
  cta: { marginTop: 'auto', paddingTop: space.lg },
});
