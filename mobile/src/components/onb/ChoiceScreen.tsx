/**
 * Single-choice quiz screen (Goal, Source, Gender, Activity, Tracked before,
 * Barriers): headline, subline, spacer 1, the answer list, spacer 1.4, then
 * Continue — enabled once something is picked.
 */
import type { ReactNode } from 'react';
import { StyleSheet, Text, View, type ImageSourcePropType } from 'react-native';

import { C, F } from '@/onb/theme';

import { OnbButton } from './OnbButton';
import { OnbLayout } from './OnbLayout';
import { OptionCard } from './OptionCard';

export interface Choice<K extends string> {
  key: K;
  label: string;
  sub?: string;
  icon?: ImageSourcePropType;
  iconNode?: ReactNode;
}

interface Props<K extends string> {
  progress: number | null;
  title: string;
  sub?: string;
  options: Choice<K>[];
  value: K | null;
  onChange: (k: K) => void;
  onContinue: () => void;
  gap?: number;
  iconSize?: number;
  pad?: { v: number; h: number; minHeight?: number };
  compact?: boolean;
  bold?: boolean;
  titleMarginTop?: number;
  /** Spacer weights above and below the list. */
  spacers?: [number, number];
}

export function ChoiceScreen<K extends string>({
  progress,
  title,
  sub,
  options,
  value,
  onChange,
  onContinue,
  gap = 12,
  iconSize,
  pad,
  compact,
  bold,
  titleMarginTop = 24,
  spacers = [1, 1.4],
}: Props<K>) {
  return (
    <OnbLayout
      progress={progress}
      title={<Text style={[s.title, { marginTop: titleMarginTop }]}>{title}</Text>}
      sub={sub}
      footer={<OnbButton label="Continue" onPress={onContinue} disabled={value === null} />}
    >
      <View style={{ flex: spacers[0] }} />
      <View style={{ gap }}>
        {options.map((o) => (
          <OptionCard
            key={o.key}
            label={o.label}
            sub={o.sub}
            icon={o.icon}
            iconNode={o.iconNode}
            iconSize={iconSize}
            pad={pad}
            compact={compact}
            bold={bold}
            selected={value === o.key}
            onPress={() => onChange(o.key)}
          />
        ))}
      </View>
      <View style={{ flex: spacers[1] }} />
    </OnbLayout>
  );
}

const s = StyleSheet.create({
  title: { fontFamily: F.serif, fontSize: 32, lineHeight: 38, letterSpacing: -0.32, color: C.ink },
});
