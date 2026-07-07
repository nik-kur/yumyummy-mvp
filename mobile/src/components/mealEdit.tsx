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
import { useState, type ReactNode } from 'react';
import {
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Minus, Plus, Trash2, X } from 'lucide-react-native';

import { AppText } from './AppText';
import { Button } from './Button';
import type { MealItem } from '@/api/types';
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

function Sheet({
  visible,
  onClose,
  title,
  children,
}: {
  visible: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <Pressable style={StyleSheet.absoluteFill} onPress={onClose} />
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <View style={[styles.sheet, { paddingBottom: insets.bottom + space.base }]}>
            <View style={styles.sheetHeader}>
              <AppText variant="h2" numberOfLines={1} style={styles.sheetTitle}>
                {title}
              </AppText>
              <Pressable onPress={onClose} hitSlop={10}>
                <X size={24} color={colors.inkMuted} strokeWidth={1.5} />
              </Pressable>
            </View>
            <ScrollView
              keyboardShouldPersistTaps="handled"
              showsVerticalScrollIndicator={false}
              style={styles.sheetScroll}
            >
              {children}
            </ScrollView>
          </View>
        </KeyboardAvoidingView>
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

function NumRow({
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
  tint?: string;
}) {
  return (
    <View style={styles.numRow}>
      <AppText variant="body" color={tint ?? colors.ink} style={styles.numLabel}>
        {label}
      </AppText>
      <View style={styles.numInputWrap}>
        <TextInput
          style={styles.numInput}
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
      <NumRow label="Calories" unit="kcal" value={cal} onChangeText={onCal} tint={colors.terracottaText} />
      <NumRow label="Protein" unit="g" value={prot} onChangeText={onProt} tint={colors.protein} />
      <NumRow label="Fat" unit="g" value={fat} onChangeText={onFat} tint={colors.fat} />
      <NumRow label="Carbs" unit="g" value={carbs} onChangeText={onCarbs} tint={colors.carbs} />
    </View>
  );
}

// ---- whole-meal edit sheet ---------------------------------------------------

const PORTION_STEP = 0.25;
const PORTION_MIN = 0.25;
const PORTION_MAX = 4;

function MealEditBody({
  initial,
  hasItems,
  onSave,
}: {
  initial: MacroTotals;
  hasItems: boolean;
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
    <View style={styles.body}>
      <View style={styles.sectionRow}>
        <View style={styles.sectionText}>
          <AppText variant="bodyStrong">Portion</AppText>
          <AppText variant="caption" color={colors.inkMuted}>
            Ate half? Set ×0.5 — everything rescales{hasItems ? ', components too' : ''}.
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

      <AppText variant="overline" color={colors.inkMuted} style={styles.fieldsLabel}>
        Or set the numbers directly
      </AppText>
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
    </View>
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
  return (
    <Sheet visible={visible} onClose={onClose} title={title}>
      {/* Remount per open so state re-seeds from `initial`. */}
      {visible ? <MealEditBody initial={initial} hasItems={hasItems} onSave={onSave} /> : null}
    </Sheet>
  );
}

// ---- single component (breakdown item) edit sheet ----------------------------

const GRAMS_STEP = 10;

function ItemEditBody({
  item,
  onSave,
  onRemove,
}: {
  item: MealItem;
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
  return (
    <Sheet visible={visible} onClose={onClose} title={item?.name ?? 'Component'}>
      {visible && item ? <ItemEditBody item={item} onSave={onSave} onRemove={onRemove} /> : null}
    </Sheet>
  );
}

// ---- saved meal edit sheet ----------------------------------------------------

function SavedMealEditBody({
  name,
  totals,
  items,
  onSave,
  onDelete,
  onEditItem,
  onRemoveItem,
}: {
  name: string;
  totals: MacroTotals;
  items: MealItem[];
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
        <>
          <AppText variant="overline" color={colors.inkMuted} style={styles.fieldsLabel}>
            Nutrition
          </AppText>
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
        </>
      )}

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
  return (
    <Sheet visible={visible} onClose={onClose} title="Edit saved meal">
      {visible ? (
        <SavedMealEditBody
          name={name}
          totals={totals}
          items={items}
          onSave={onSave}
          onDelete={onDelete}
          onEditItem={onEditItem}
          onRemoveItem={onRemoveItem}
        />
      ) : null}
    </Sheet>
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
    paddingTop: space.lg,
    maxHeight: '88%',
    ...shadow.float,
  },
  sheetHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.md,
    marginBottom: space.base,
  },
  sheetTitle: { flex: 1 },
  sheetScroll: { flexGrow: 0 },
  body: { gap: space.base, paddingBottom: space.sm },

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

  fieldsLabel: { marginBottom: -space.sm },
  fields: { gap: space.sm },
  numRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: space.md,
  },
  numLabel: { flex: 1 },
  numInputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: space.xs,
    backgroundColor: colors.surfaceAlt,
    borderWidth: 1,
    borderColor: colors.hairline,
    borderRadius: radius.md,
    paddingHorizontal: space.md,
    height: 44,
    width: 128,
  },
  numInput: {
    flex: 1,
    fontFamily: fonts.serifSemibold,
    fontSize: 18,
    color: colors.ink,
    fontVariant: ['tabular-nums'],
    padding: 0,
    textAlign: 'right',
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
