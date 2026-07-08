/**
 * Meal-editing bottom sheets (25(1), pack 2).
 *
 * UX pattern follows Alma's edit sheet (portion stepper on top, direct macro
 * fields below) and BitePal's per-ingredient rows. Three sheets:
 *
 * - `MealEditSheet`  — whole meal: portion ×-stepper + direct kcal/P/F/C fields.
 * - `ItemEditSheet`  — one breakdown component: grams stepper (macros rescale
 *                      proportionally) + direct fields + remove.
 * - `SavedMealEditSheet` — saved meal: name, per-component rows (tap to edit,
 *                      minus to remove) or direct totals when no breakdown.
 *
 * Sheets are pure UI: they return the edited values via `onSave` and the
 * caller does the optimistic update + API call.
 */
import { useEffect, useRef, useState, type ReactNode } from 'react';
import {
  Animated,
  Easing,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
  useWindowDimensions,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Minus, Plus, Trash2, X } from 'lucide-react-native';

import { AppText } from './AppText';
import { Button } from './Button';
import type { MealItem } from '@/api/types';
import { useKeyboardHeight } from '@/utils/keyboard';
import { colors, radius, shadow, space } from '@/theme/tokens';
import { fonts } from '@/theme/typography';

// ---- helpers ---------------------------------------------------------------

/** '12,5' / '' / junk -> non-negative number (rounded). */
function toNum(s: string): number {
  const n = Math.round(Number(s.replace(',', '.')));
  return Number.isFinite(n) && n > 0 ? n : 0;
}

function fromNum(n: number | null | undefined): string {
  return n || n === 0 ? String(Math.round(n)) : '';
}

/** Scale a breakdown item's grams + macros by k (used for portion edits). */
export function scaleItem(it: MealItem, k: number): MealItem {
  const s = (v: number | null | undefined) => (v == null ? v : Math.round(v * k));
  return {
    ...it,
    grams: s(it.grams),
    calories_kcal: s(it.calories_kcal),
    protein_g: s(it.protein_g),
    fat_g: s(it.fat_g),
    carbs_g: s(it.carbs_g),
  };
}

export function sumItems(items: MealItem[]) {
  return {
    calories: Math.round(items.reduce((a, i) => a + (i.calories_kcal ?? 0), 0)),
    protein: Math.round(items.reduce((a, i) => a + (i.protein_g ?? 0), 0)),
    fat: Math.round(items.reduce((a, i) => a + (i.fat_g ?? 0), 0)),
    carbs: Math.round(items.reduce((a, i) => a + (i.carbs_g ?? 0), 0)),
  };
}

export interface MacroTotals {
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
}

// ---- generic sheet shell ----------------------------------------------------
//
// Structure (fixes the build-28 issues: sheet floating above the bottom and
// "Save" hidden behind a scroll):
//  - The card is glued to the screen bottom. The keyboard lifts the CONTENT
//    via paddingBottom (deterministic `useKeyboardOverlap`, no measuring, no
//    KeyboardAvoidingView — that's what misbehaved inside Modal).
//  - Header and footer (Save/Delete) are pinned OUTSIDE the scroll area, so
//    the primary action is always on screen. The middle only scrolls in the
//    rare case content genuinely doesn't fit (small phone + keyboard).

function SheetShell({
  onClose,
  title,
  footer,
  scrollable = false,
  children,
}: {
  onClose: () => void;
  title: string;
  footer: ReactNode;
  /** Only the saved-meal list (many components) scrolls; edit sheets fit on screen. */
  scrollable?: boolean;
  children: ReactNode;
}) {
  const insets = useSafeAreaInsets();
  const winH = useWindowDimensions().height;
  const kb = useKeyboardHeight();

  const anim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(anim, {
      toValue: 1,
      duration: 240,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start();
  }, [anim]);

  const body = scrollable ? (
    <ScrollView
      style={styles.sheetScroll}
      contentContainerStyle={styles.sheetScrollContent}
      keyboardShouldPersistTaps="handled"
      showsVerticalScrollIndicator={false}
      bounces={false}
    >
      {children}
    </ScrollView>
  ) : (
    <View style={styles.sheetBody}>{children}</View>
  );

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
        <Animated.View
          style={[
            styles.sheet,
            scrollable && { maxHeight: winH - insets.top - space.lg - kb },
            {
              paddingBottom: kb > 0 ? kb : insets.bottom,
              opacity: anim,
              transform: [
                { translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [28, 0] }) },
              ],
            },
          ]}
        >
          <View style={styles.grabber} />
          <View style={styles.sheetHeader}>
            <AppText variant="h2" numberOfLines={1} style={styles.sheetTitle}>
              {title}
            </AppText>
            <Pressable onPress={onClose} hitSlop={10} style={styles.sheetClose}>
              <X size={22} color={colors.inkMuted} strokeWidth={1.5} />
            </Pressable>
          </View>
          {body}
          <View style={styles.sheetFooter}>{footer}</View>
        </Animated.View>
      </View>
    </Modal>
  );
}

// ---- small building blocks --------------------------------------------------

function Stepper({
  display,
  onMinus,
  onPlus,
  minusDisabled,
  plusDisabled,
}: {
  display: string;
  onMinus: () => void;
  onPlus: () => void;
  minusDisabled?: boolean;
  plusDisabled?: boolean;
}) {
  return (
    <View style={styles.stepper}>
      <Pressable
        onPress={onMinus}
        disabled={minusDisabled}
        hitSlop={6}
        style={[styles.stepBtn, minusDisabled && styles.stepBtnDisabled]}
      >
        <Minus size={20} color={minusDisabled ? colors.inkFaint : colors.ink} strokeWidth={2} />
      </Pressable>
      <AppText variant="title" center style={styles.stepValue}>
        {display}
      </AppText>
      <Pressable
        onPress={onPlus}
        disabled={plusDisabled}
        hitSlop={6}
        style={[styles.stepBtn, plusDisabled && styles.stepBtnDisabled]}
      >
        <Plus size={20} color={plusDisabled ? colors.inkFaint : colors.ink} strokeWidth={2} />
      </Pressable>
    </View>
  );
}

/** One labeled numeric box (label on top, value + unit inside). */
function MacroCell({
  label,
  unit,
  value,
  onChangeText,
  tint,
}: {
  label: string;
  unit: string;
  value: string;
  onChangeText: (t: string) => void;
  tint: string;
}) {
  return (
    <View style={styles.cell}>
      <AppText variant="overline" color={tint} numberOfLines={1}>
        {label}
      </AppText>
      <View style={styles.cellInputRow}>
        <TextInput
          style={styles.cellInput}
          value={value}
          onChangeText={onChangeText}
          keyboardType="number-pad"
          placeholder="0"
          placeholderTextColor={colors.inkFaint}
          maxLength={5}
          selectTextOnFocus
        />
        <AppText variant="caption" color={colors.inkFaint}>
          {unit}
        </AppText>
      </View>
    </View>
  );
}

/** Compact grid: calories on its own line, P/F/C side by side. Two rows total,
 * so the whole sheet fits on screen without scrolling. */
function MacroFields({
  cal,
  prot,
  fat,
  carbs,
  onCal,
  onProt,
  onFat,
  onCarbs,
}: {
  cal: string;
  prot: string;
  fat: string;
  carbs: string;
  onCal: (t: string) => void;
  onProt: (t: string) => void;
  onFat: (t: string) => void;
  onCarbs: (t: string) => void;
}) {
  return (
    <View style={styles.fields}>
      <MacroCell label="Calories" unit="kcal" value={cal} onChangeText={onCal} tint={colors.terracottaText} />
      <View style={styles.fieldsRow}>
        <MacroCell label="Protein" unit="g" value={prot} onChangeText={onProt} tint={colors.protein} />
        <MacroCell label="Fat" unit="g" value={fat} onChangeText={onFat} tint={colors.fat} />
        <MacroCell label="Carbs" unit="g" value={carbs} onChangeText={onCarbs} tint={colors.carbs} />
      </View>
    </View>
  );
}

// ---- whole-meal edit sheet ---------------------------------------------------

const PORTION_STEP = 0.25;
const PORTION_MIN = 0.25;
const PORTION_MAX = 4;

function MealEditInner({
  title,
  initial,
  hasItems,
  onClose,
  onSave,
}: {
  title: string;
  initial: MacroTotals;
  hasItems: boolean;
  onClose: () => void;
  onSave: (portion: number, totals: MacroTotals) => void;
}) {
  const [portion, setPortion] = useState(1);
  const [cal, setCal] = useState(fromNum(initial.calories));
  const [prot, setProt] = useState(fromNum(initial.protein));
  const [fat, setFat] = useState(fromNum(initial.fat));
  const [carbs, setCarbs] = useState(fromNum(initial.carbs));

  const applyPortion = (p: number) => {
    setPortion(p);
    setCal(fromNum(initial.calories * p));
    setProt(fromNum(initial.protein * p));
    setFat(fromNum(initial.fat * p));
    setCarbs(fromNum(initial.carbs * p));
  };

  return (
    <SheetShell
      onClose={onClose}
      title={title}
      footer={
        <Button
          label="Save changes"
          onPress={() =>
            onSave(portion, {
              calories: toNum(cal),
              protein: toNum(prot),
              fat: toNum(fat),
              carbs: toNum(carbs),
            })
          }
        />
      }
    >
      <View style={styles.body}>
        <View style={styles.sectionRow}>
          <View style={styles.sectionText}>
            <AppText variant="bodyStrong">Portion</AppText>
            <AppText variant="caption" color={colors.inkMuted}>
              Ate half? Set ×0.5{hasItems ? ' — components rescale too' : ''}.
            </AppText>
          </View>
          <Stepper
            display={`×${portion}`}
            onMinus={() => applyPortion(Math.max(PORTION_MIN, +(portion - PORTION_STEP).toFixed(2)))}
            onPlus={() => applyPortion(Math.min(PORTION_MAX, +(portion + PORTION_STEP).toFixed(2)))}
            minusDisabled={portion <= PORTION_MIN}
            plusDisabled={portion >= PORTION_MAX}
          />
        </View>

        <MacroFields
          cal={cal}
          prot={prot}
          fat={fat}
          carbs={carbs}
          onCal={setCal}
          onProt={setProt}
          onFat={setFat}
          onCarbs={setCarbs}
        />
      </View>
    </SheetShell>
  );
}

export function MealEditSheet({
  visible,
  title,
  initial,
  hasItems,
  onClose,
  onSave,
}: {
  visible: boolean;
  title: string;
  initial: MacroTotals;
  hasItems: boolean;
  onClose: () => void;
  onSave: (portion: number, totals: MacroTotals) => void;
}) {
  // Mount per open so state re-seeds from `initial`.
  if (!visible) return null;
  return (
    <MealEditInner
      title={title}
      initial={initial}
      hasItems={hasItems}
      onClose={onClose}
      onSave={onSave}
    />
  );
}

// ---- single component (breakdown item) edit sheet ----------------------------

const GRAMS_STEP = 10;

function ItemEditInner({
  item,
  onClose,
  onSave,
  onRemove,
}: {
  item: MealItem;
  onClose: () => void;
  onSave: (next: MealItem) => void;
  onRemove: () => void;
}) {
  const baseGrams = item.grams && item.grams > 0 ? item.grams : null;
  const [grams, setGrams] = useState(fromNum(item.grams));
  const [cal, setCal] = useState(fromNum(item.calories_kcal));
  const [prot, setProt] = useState(fromNum(item.protein_g));
  const [fat, setFat] = useState(fromNum(item.fat_g));
  const [carbs, setCarbs] = useState(fromNum(item.carbs_g));

  // Grams drive the macros proportionally (only when we know the base weight).
  const applyGrams = (g: number) => {
    setGrams(g ? String(g) : '');
    if (baseGrams) {
      const k = g / baseGrams;
      setCal(fromNum((item.calories_kcal ?? 0) * k));
      setProt(fromNum((item.protein_g ?? 0) * k));
      setFat(fromNum((item.fat_g ?? 0) * k));
      setCarbs(fromNum((item.carbs_g ?? 0) * k));
    }
  };

  return (
    <SheetShell
      onClose={onClose}
      title={item.name ?? 'Component'}
      footer={
        <View style={styles.footerCol}>
          <Button
            label="Save changes"
            onPress={() =>
              onSave({
                ...item,
                grams: toNum(grams) || item.grams,
                calories_kcal: toNum(cal),
                protein_g: toNum(prot),
                fat_g: toNum(fat),
                carbs_g: toNum(carbs),
              })
            }
          />
          <Pressable onPress={onRemove} style={styles.removeBtn}>
            <Trash2 size={18} color={colors.error} strokeWidth={1.5} />
            <AppText variant="bodyStrong" color={colors.error}>
              Remove this component
            </AppText>
          </Pressable>
        </View>
      }
    >
      <View style={styles.body}>
        <View style={styles.sectionRow}>
          <View style={styles.sectionText}>
            <AppText variant="bodyStrong">Weight</AppText>
            <AppText variant="caption" color={colors.inkMuted}>
              {baseGrams
                ? 'Macros rescale with the grams.'
                : 'No weight on record — edit the numbers below.'}
            </AppText>
          </View>
          <View style={styles.gramsWrap}>
            <Pressable
              onPress={() => applyGrams(Math.max(0, toNum(grams) - GRAMS_STEP))}
              disabled={toNum(grams) <= 0}
              hitSlop={6}
              style={[styles.stepBtn, toNum(grams) <= 0 && styles.stepBtnDisabled]}
            >
              <Minus size={20} color={toNum(grams) <= 0 ? colors.inkFaint : colors.ink} strokeWidth={2} />
            </Pressable>
            <View style={styles.gramsInputWrap}>
              <TextInput
                style={styles.gramsInput}
                value={grams}
                onChangeText={(t) => applyGrams(toNum(t))}
                keyboardType="number-pad"
                placeholder="0"
                placeholderTextColor={colors.inkFaint}
                maxLength={5}
                selectTextOnFocus
              />
              <AppText variant="caption" color={colors.inkFaint}>
                g
              </AppText>
            </View>
            <Pressable
              onPress={() => applyGrams(toNum(grams) + GRAMS_STEP)}
              hitSlop={6}
              style={styles.stepBtn}
            >
              <Plus size={20} color={colors.ink} strokeWidth={2} />
            </Pressable>
          </View>
        </View>

        <MacroFields
          cal={cal}
          prot={prot}
          fat={fat}
          carbs={carbs}
          onCal={setCal}
          onProt={setProt}
          onFat={setFat}
          onCarbs={setCarbs}
        />
      </View>
    </SheetShell>
  );
}

export function ItemEditSheet({
  visible,
  item,
  onClose,
  onSave,
  onRemove,
}: {
  visible: boolean;
  item: MealItem | null;
  onClose: () => void;
  onSave: (next: MealItem) => void;
  onRemove: () => void;
}) {
  if (!visible || !item) return null;
  return <ItemEditInner item={item} onClose={onClose} onSave={onSave} onRemove={onRemove} />;
}

// ---- saved meal edit sheet ----------------------------------------------------

function SavedMealEditInner({
  name,
  totals,
  items,
  onClose,
  onSave,
  onDelete,
  onEditItem,
  onRemoveItem,
}: {
  name: string;
  totals: MacroTotals;
  items: MealItem[];
  onClose: () => void;
  onSave: (name: string, totals: MacroTotals | null) => void;
  onDelete: () => void;
  onEditItem: (index: number) => void;
  onRemoveItem: (index: number) => void;
}) {
  const [draftName, setDraftName] = useState(name);
  const hasItems = items.length > 0;
  const [cal, setCal] = useState(fromNum(totals.calories));
  const [prot, setProt] = useState(fromNum(totals.protein));
  const [fat, setFat] = useState(fromNum(totals.fat));
  const [carbs, setCarbs] = useState(fromNum(totals.carbs));

  return (
    <SheetShell
      onClose={onClose}
      title="Edit saved meal"
      scrollable
      footer={
        <View style={styles.footerCol}>
          <Button
            label="Save changes"
            onPress={() =>
              onSave(
                draftName.trim() || name,
                hasItems
                  ? null
                  : { calories: toNum(cal), protein: toNum(prot), fat: toNum(fat), carbs: toNum(carbs) },
              )
            }
          />
          <Pressable onPress={onDelete} style={styles.removeBtn}>
            <Trash2 size={18} color={colors.error} strokeWidth={1.5} />
            <AppText variant="bodyStrong" color={colors.error}>
              Remove from My Menu
            </AppText>
          </Pressable>
        </View>
      }
    >
      <View style={styles.body}>
        <View style={styles.nameField}>
          <AppText variant="overline" color={colors.inkMuted}>
            Name
          </AppText>
          <TextInput
            style={styles.nameInput}
            value={draftName}
            onChangeText={setDraftName}
            placeholder="Meal name"
            placeholderTextColor={colors.inkFaint}
            maxLength={80}
          />
        </View>

        {hasItems ? (
          <View style={styles.itemList}>
            <AppText variant="overline" color={colors.inkMuted}>
              Components — tap to edit
            </AppText>
            {items.map((it, i) => (
              <View key={`${it.name}-${i}`} style={styles.itemRow}>
                <Pressable style={styles.itemRowMain} onPress={() => onEditItem(i)}>
                  <AppText variant="bodyStrong" numberOfLines={1} style={styles.itemRowName}>
                    {it.name}
                  </AppText>
                  <AppText variant="caption" color={colors.inkMuted}>
                    {[
                      it.grams ? `${Math.round(it.grams)} g` : null,
                      it.calories_kcal != null ? `${Math.round(it.calories_kcal)} kcal` : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </AppText>
                </Pressable>
                <Pressable onPress={() => onRemoveItem(i)} hitSlop={8} style={styles.itemRemove}>
                  <Minus size={16} color={colors.error} strokeWidth={2.5} />
                </Pressable>
              </View>
            ))}
            <AppText variant="caption" color={colors.inkFaint}>
              Totals update automatically from the components.
            </AppText>
          </View>
        ) : (
          <MacroFields
            cal={cal}
            prot={prot}
            fat={fat}
            carbs={carbs}
            onCal={setCal}
            onProt={setProt}
            onFat={setFat}
            onCarbs={setCarbs}
          />
        )}
      </View>
    </SheetShell>
  );
}

export function SavedMealEditSheet({
  visible,
  name,
  totals,
  items,
  onClose,
  onSave,
  onDelete,
  onEditItem,
  onRemoveItem,
}: {
  visible: boolean;
  name: string;
  totals: MacroTotals;
  items: MealItem[];
  onClose: () => void;
  onSave: (name: string, totals: MacroTotals | null) => void;
  onDelete: () => void;
  onEditItem: (index: number) => void;
  onRemoveItem: (index: number) => void;
}) {
  if (!visible) return null;
  return (
    <SavedMealEditInner
      name={name}
      totals={totals}
      items={items}
      onClose={onClose}
      onSave={onSave}
      onDelete={onDelete}
      onEditItem={onEditItem}
      onRemoveItem={onRemoveItem}
    />
  );
}

// ---- styles -------------------------------------------------------------------

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: colors.overlay,
    justifyContent: 'flex-end',
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    paddingHorizontal: space.lg,
    paddingTop: space.sm,
    width: '100%',
    ...shadow.float,
  },
  grabber: {
    alignSelf: 'center',
    width: 36,
    height: 4,
    borderRadius: radius.pill,
    backgroundColor: colors.hairlineStrong,
    marginBottom: space.sm,
  },
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.md,
    marginBottom: space.md,
  },
  sheetTitle: { flex: 1 },
  sheetClose: {
    width: 32,
    height: 32,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceAlt,
    alignItems: 'center',
    justifyContent: 'center',
  },
  // Scroll only for saved-meal lists; compact edit sheets use sheetBody instead.
  sheetScroll: { flexGrow: 0, flexShrink: 1, maxHeight: 280 },
  sheetScrollContent: { paddingBottom: space.xs },
  sheetBody: { gap: space.sm },
  sheetFooter: { paddingTop: space.sm },
  footerCol: { gap: space.xs },
  body: { gap: space.sm },

  sectionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.md,
  },
  sectionText: { flex: 1, gap: 2 },

  stepper: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
  },
  stepBtn: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.hairline,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepBtnDisabled: { opacity: 0.4 },
  stepValue: { minWidth: 52, fontVariant: ['tabular-nums'] },

  gramsWrap: { flexDirection: 'row', alignItems: 'center', gap: space.sm },
  gramsInputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    height: 40,
    minWidth: 84,
  },
  gramsInput: {
    flex: 1,
    fontFamily: fonts.serifSemibold,
    fontSize: 18,
    color: colors.ink,
    fontVariant: ['tabular-nums'],
    padding: 0,
    textAlign: 'right',
  },

  fields: { gap: space.sm },
  fieldsRow: { flexDirection: 'row', gap: space.sm },
  cell: {
    flex: 1,
    gap: 6,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
  },
  cellInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
  },
  cellInput: {
    flexShrink: 1,
    minWidth: 24,
    fontFamily: fonts.serifSemibold,
    fontSize: 20,
    color: colors.ink,
    fontVariant: ['tabular-nums'],
    padding: 0,
  },

  nameField: { gap: space.xs },
  nameInput: {
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.md,
    paddingHorizontal: space.base,
    height: 48,
    fontFamily: fonts.sansMedium,
    fontSize: 16,
    color: colors.ink,
  },

  itemList: { gap: space.sm },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.md,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.md,
    paddingHorizontal: space.base,
    paddingVertical: space.md,
  },
  itemRowMain: { flex: 1, gap: 2 },
  itemRowName: { flexShrink: 1 },
  itemRemove: {
    width: 28,
    height: 28,
    borderRadius: radius.pill,
    backgroundColor: colors.errorSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },

  removeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: space.sm,
    paddingVertical: space.sm,
  },
});
