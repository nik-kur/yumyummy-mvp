/**
 * V3 onboarding design tokens — the exact values the canvas uses
 * (`design/build_screens_v3.py`), so screens can be checked against the
 * artboards 1:1. Mostly equal to `theme/tokens.ts`; the V3 extras (paper-2
 * track fill, chart grey, ok/warn tints, sticker shadow) live only here.
 */
import type { ViewStyle } from 'react-native';

import { fonts } from '@/theme/typography';

export const C = {
  ink: '#19150F',
  muted: '#6B6258',
  faint: '#938A7C',
  paper: '#F7F1E6',
  surface: '#FFFDF9',
  hair: '#E7DFD1',
  hair2: '#D8CCB9',
  terra: '#B85A3A',
  terraText: '#9A4628',
  terraSoft: '#EFDFD1',
  info: '#1F5C99',
  infoSoft: '#E7EFF8',
  ok: '#2E6B4E',
  okSoft: '#E3F0E8',
  warn: '#8A5A14',
  warnSoft: '#F5E9D3',
  paper2: '#EFE7DA',
  grey: '#B5AA98',
  protein: '#5A6A3A',
  fat: '#8A5A14',
  carbs: '#2C6CA8',
  white: '#FFFFFF',
} as const;

export const F = {
  serif: fonts.serifSemibold,
  sans: fonts.sans,
  sansMedium: fonts.sansMedium,
  sansSemibold: fonts.sansSemibold,
  mono: fonts.mono,
} as const;

/** `0 10px 30px rgba(42,28,14,.10), 0 2px 8px rgba(42,28,14,.06)` — one iOS shadow. */
export const SHADOW: ViewStyle = {
  shadowColor: '#2A1C0E',
  shadowOpacity: 0.12,
  shadowRadius: 14,
  shadowOffset: { width: 0, height: 6 },
};

/** Screen padding of every quiz artboard: 52 top (incl. status bar), 24 sides, 34 bottom. */
export const PAD = { side: 24, topBelowStatus: 5, bottom: 34 } as const;
