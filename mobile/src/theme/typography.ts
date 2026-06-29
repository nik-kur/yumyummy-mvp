import type { TextStyle } from 'react-native';
import { colors } from './tokens';

/** Font family keys map to the names registered in `useAppFonts`. */
export const fonts = {
  serifRegular: 'Fraunces_400Regular',
  serifSemibold: 'Fraunces_600SemiBold',
  serifBold: 'Fraunces_700Bold',
  sans: 'Inter_400Regular',
  sansMedium: 'Inter_500Medium',
  sansSemibold: 'Inter_600SemiBold',
  mono: 'JetBrainsMono_500Medium',
} as const;

/** Tabular figures so nutrition numbers/columns align (v2 §4.3). */
const tnum: TextStyle = { fontVariant: ['tabular-nums'] };

/**
 * Type presets (v2 §4). Numbers = Fraunces 600 + tabular (the premium signal);
 * headlines = Fraunces 600; body / labels = Inter; eyebrows = JetBrains Mono.
 *
 * `hero` and `overline` are kept as back-compat aliases of `heroNum` and `eyebrow`
 * so existing screens keep working.
 */
export const text = {
  // numbers — the hero, in the editorial serif
  heroNum: { fontFamily: fonts.serifSemibold, fontSize: 60, lineHeight: 60, color: colors.ink, ...tnum },
  hero: { fontFamily: fonts.serifSemibold, fontSize: 56, lineHeight: 58, color: colors.ink, ...tnum },
  macroValue: { fontFamily: fonts.serifSemibold, fontSize: 18, lineHeight: 22, color: colors.ink, ...tnum },

  // headlines — Fraunces 600
  display: { fontFamily: fonts.serifSemibold, fontSize: 36, lineHeight: 40, color: colors.ink, ...tnum },
  h1: { fontFamily: fonts.serifSemibold, fontSize: 28, lineHeight: 32, color: colors.ink, ...tnum },
  h2: { fontFamily: fonts.serifSemibold, fontSize: 22, lineHeight: 28, color: colors.ink, ...tnum },

  // text — Inter
  title: { fontFamily: fonts.sansSemibold, fontSize: 18, lineHeight: 24, color: colors.ink, ...tnum },
  body: { fontFamily: fonts.sans, fontSize: 16, lineHeight: 26, color: colors.ink },
  bodyStrong: { fontFamily: fonts.sansSemibold, fontSize: 16, lineHeight: 26, color: colors.ink },
  small: { fontFamily: fonts.sans, fontSize: 14, lineHeight: 21, color: colors.inkMuted },
  caption: { fontFamily: fonts.sansMedium, fontSize: 12, lineHeight: 16, color: colors.inkMuted, ...tnum },

  // eyebrows / overlines — mono, uppercase
  eyebrow: {
    fontFamily: fonts.mono,
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1.6,
    color: colors.inkMuted,
    textTransform: 'uppercase',
  },
  overline: {
    fontFamily: fonts.mono,
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1.6,
    color: colors.inkMuted,
    textTransform: 'uppercase',
  },
} satisfies Record<string, TextStyle>;

export type TextVariant = keyof typeof text;
