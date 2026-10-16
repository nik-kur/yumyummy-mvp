/**
 * Mascot screen (Reflect, goal check): 208 pt soft-terracotta disc with the
 * animated mascot, a centred Fraunces 32/37 headline with one terracotta
 * accent, an 18/27 subline, then the CTA (and an optional text button).
 */
import type { ReactNode } from 'react';
import { StyleSheet, Text, View, type ImageSourcePropType } from 'react-native';

import { C, F } from '@/onb/theme';

import { OnbButton } from './OnbButton';
import { OnbLayout } from './OnbLayout';
import { Sticker, type StickerMotion } from './Sticker';

interface Props {
  progress: number | null;
  mascot: ImageSourcePropType;
  motion: StickerMotion;
  /** Headline parts: plain text before, the accent, plain text after. */
  before: string;
  accent: string;
  after?: string;
  sub: string;
  cta: string;
  onCta: () => void;
  secondary?: { label: string; onPress: () => void };
  extra?: ReactNode;
}

export function MascotMessage({ progress, mascot, motion, before, accent, after, sub, cta, onCta, secondary, extra }: Props) {
  return (
    <OnbLayout
      progress={progress}
      footer={
        <>
          <OnbButton label={cta} onPress={onCta} />
          {secondary ? <OnbButton label={secondary.label} onPress={secondary.onPress} variant="text" /> : null}
        </>
      }
    >
      <View style={{ flex: 1 }} />
      <View style={s.disc}>
        <Sticker source={mascot} size={196} motion={motion} />
      </View>
      <Text style={s.h1}>
        {before}
        <Text style={s.accent}>{accent}</Text>
        {after ?? ''}
      </Text>
      <Text style={s.sub}>{sub}</Text>
      {extra}
      <View style={{ flex: 1.3 }} />
    </OnbLayout>
  );
}

const s = StyleSheet.create({
  disc: {
    alignSelf: 'center',
    width: 208,
    height: 208,
    borderRadius: 104,
    backgroundColor: C.terraSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  h1: {
    marginTop: 28,
    textAlign: 'center',
    fontFamily: F.serif,
    fontSize: 32,
    lineHeight: 37,
    letterSpacing: -0.32,
    color: C.ink,
  },
  accent: { color: C.terra },
  sub: { marginTop: 12, textAlign: 'center', fontFamily: F.sans, fontSize: 18, lineHeight: 27, color: C.muted },
});
