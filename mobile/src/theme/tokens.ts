/**
 * YumYummy design tokens — v2 "Refined Warm Editorial".
 * Canonical source: YumYummy_Design_System_v2.md (§3 color, §5 spacing, §6 radius, §7 elevation).
 *
 * Principles: charcoal leads the UI; terracotta is a ≤10% accent (never the default
 * button fill); two surfaces (warm paper canvas + crisp warm-white cards); macro and
 * semantic colors appear only inside data. Borders over shadows.
 */

export const colors = {
  // surfaces — a real hierarchy, not one flat cream
  bg: '#F7F1E6', // warm paper canvas (app background)
  surface: '#FFFDF9', // crisp warm-white card
  surfaceAlt: '#FBF6EE', // pressed / hover rows, subtle fills

  // ink
  ink: '#19150F',
  inkMuted: '#6B6258',
  inkFaint: '#938A7C',
  hairline: '#E7DFD1',
  hairlineStrong: '#D8CCB9',

  // brand accent — sun-baked clay (use at ≤10% of any screen)
  terracotta: '#B85A3A', // brand-moment CTA fill, calorie-ring arc, source-stamp icon
  terracottaText: '#9A4628', // terracotta AS TEXT on light surfaces (AA)
  terracottaSoft: '#EFDFD1', // tints, hover, focus rings

  // trust / source badge — the signature color
  infoBlue: '#1F5C99',
  infoBlueSoft: '#E7EFF8',

  // status — only in their semantic role
  success: '#2E6B4E',
  successSoft: '#E3F0E8',
  oliveSoft: '#E3E6CE', // light olive tint of `protein` — in-goal chart bars
  warning: '#8A5A14',
  warningSoft: '#FBEFD6',
  error: '#9A2A1F',
  errorSoft: '#FBEAE7',

  // macros — muted, data-only (never UI chrome). Displayed in P → F → C order.
  protein: '#5A6A3A', // olive
  fat: '#8A5A14', // ochre
  carbs: '#2C6CA8', // muted blue

  // accuracy-badge palette — aligned to the semantic system
  exact: '#2E6B4E', // = success
  estimate: '#8A5A14', // = warning
  approx: '#938A7C', // = inkFaint

  // dark mode (Direction B — designed now, ships post-launch)
  darkBg: '#15120F',
  darkSurface: '#1F1B16',
  onDark: '#F3ECE0',
  onDarkMuted: '#A79E90',
  terracottaDark: '#D98B5E', // brightened clay to hold luminance on dark surfaces
  infoDark: '#7FA8D6',

  white: '#FFFFFF',
  overlay: 'rgba(20, 16, 12, 0.45)',
} as const;

/** 8pt spacing scale (4 for micro-adjustments). */
export const space = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 20,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

/** Rounded-sharp, editorial. Down across the board from the MVP (cards 20→16, buttons 14→12). */
export const radius = {
  sm: 8, // tags, small controls
  md: 12, // buttons, inputs
  lg: 16, // cards, panels
  xl: 20, // sheets, modals
  pill: 999, // chips & badges only — never a CTA button
} as const;

/**
 * Elevation: borders over shadows. The default card uses a 1px hairline border and
 * NO shadow — `shadow.float` is reserved for things that truly float (sheets, FAB,
 * dropdowns, toasts). Shadow tint is warm brown, never neutral black.
 */
export const shadow = {
  float: {
    shadowColor: '#2A1C0E',
    shadowOpacity: 0.1,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 10 },
    elevation: 6,
  },
} as const;

export type MacroKey = 'protein' | 'fat' | 'carbs';
