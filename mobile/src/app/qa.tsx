/**
 * QA menu — QA builds only (see `config/buildFlags.ts`). Forces any
 * remote-config key on this device without touching Adapty, shows which arm
 * Adapty assigned, and resets the onboarding to run it again.
 *
 * In a production build the route exists but redirects home at once.
 */
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Redirect, useRouter } from 'expo-router';
import { X } from 'lucide-react-native';

import { AppText } from '@/components/AppText';
import { Button } from '@/components/Button';
import { Chip } from '@/components/Chip';
import { Screen } from '@/components/Screen';
import { IS_QA_BUILD } from '@/config/buildFlags';
import { OFFER_VARIANTS, PAYWALL_VARIANTS } from '@/config/defaults';
import {
  clearOnboardingAssignment,
  getLateFetch,
  resolveOnboardingAssignment,
  useOnboardingConfig,
} from '@/config/onboardingConfig';
import { loadQaOverrides, qaOverrides, saveQaOverrides, type QaOverrides } from '@/config/qa';
import { QA_PRESETS, QA_SCENARIOS, QA_SCREENS } from '@/config/qaPresets';
import { resetTour } from '@/state/tour';
import { isTesterMarked } from '@/config/testerMark';
import { buildPlan } from '@/onb/buildPlan';
import { clearDraft, loadDraft, notifyDraftReplaced, saveDraft } from '@/state/introDraft';
import { clearPendingPurchase } from '@/state/pendingPurchase';
import { colors, radius, space } from '@/theme/tokens';

type Opt = string | boolean;

/** A row of chips; the first chip ("Adapty") clears the override. */
function Choice<T extends Opt>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T | undefined;
  options: readonly T[];
  onChange: (v: T | undefined) => void;
}) {
  return (
    <View style={s.row}>
      <AppText variant="caption" color={colors.inkMuted}>{label}</AppText>
      <View style={s.chips}>
        <Chip label="Adapty" selected={value === undefined} onPress={() => onChange(undefined)} />
        {options.map((o) => (
          <Chip key={String(o)} label={String(o)} selected={value === o} onPress={() => onChange(o)} />
        ))}
      </View>
    </View>
  );
}

const ON_OFF = [true, false] as const;

export default function QaScreen() {
  const router = useRouter();
  const { config, meta } = useOnboardingConfig();
  const [o, setO] = useState<QaOverrides>(qaOverrides());
  const [tester, setTester] = useState(false);

  const [draftLine, setDraftLine] = useState('');
  useEffect(() => {
    void loadDraft().then((d) =>
      setDraftLine(
        `draft: ${d.goal_type ?? '—'} · ${d.weight_kg} → ${d.target_weight_kg ?? '—'} kg · ${d.height_cm} cm · tracked ${String(d.tracked_before)} · ${d.target_calories ?? '—'} kcal`,
      ),
    );
    void isTesterMarked().then(setTester);
    // A cold start straight into /qa has not loaded the stored overrides yet.
    void loadQaOverrides().then(setO);
  }, []);

  const [preset, setPreset] = useState(QA_PRESETS[0].key);

  if (!IS_QA_BUILD) return <Redirect href="/" />;

  const update = (next: QaOverrides) => {
    // Drop undefined keys and empty sections at any depth, so "no overrides"
    // really is `{}` and the arm stops reporting `source: qa`.
    const prune = (v: unknown): unknown => {
      if (!v || typeof v !== 'object' || Array.isArray(v)) return v;
      const out: Record<string, unknown> = {};
      for (const [k, child] of Object.entries(v)) {
        const p = prune(child);
        if (p === undefined) continue;
        if (p && typeof p === 'object' && Object.keys(p).length === 0) continue;
        out[k] = p;
      }
      return out;
    };
    const clean = prune(next) as QaOverrides;
    setO(clean);
    void saveQaOverrides(clean);
  };
  const onb = o.onboarding ?? {};
  const setOnb = (patch: NonNullable<QaOverrides['onboarding']>) => update({ ...o, onboarding: { ...onb, ...patch } });
  const setWelcome = (patch: Record<string, unknown>) =>
    setOnb({ welcome: { ...(onb.welcome ?? {}), ...patch } });
  const setSocial = (patch: Record<string, unknown>) =>
    setOnb({ social_proof: { ...(onb.social_proof ?? {}), ...patch } });
  const pw = o.paywall ?? {};
  const offer = o.offer ?? {};

  const jump = async (route: string, extra?: QaOverrides) => {
    const p = QA_PRESETS.find((x) => x.key === preset) ?? QA_PRESETS[0];
    // A scenario replaces the overrides wholesale, so earlier taps cannot leak in.
    if (extra) update(extra);
    // Plan numbers as the loader would have saved them.
    await saveDraft({ ...p.draft, ...buildPlan(p.draft).patch });
    notifyDraftReplaced();
    // Let mounted providers re-read it before screens that freeze on mount open.
    await new Promise((resolve) => setTimeout(resolve, 250));
    if (router.canDismiss()) router.dismissAll();
    // Replacing the intro group remounts its provider, which re-reads the draft.
    router.replace(route as never);
  };

  const restart = async () => {
    await clearDraft();
    await clearPendingPurchase();
    await clearOnboardingAssignment();
    router.replace('/');
  };

  return (
    <Screen edges={['top', 'left', 'right']} padded={false}>
      <View style={s.header}>
        <AppText variant="h2">QA</AppText>
        <Pressable onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} hitSlop={10}>
          <X size={22} color={colors.ink} />
        </Pressable>
      </View>
      <ScrollView contentContainerStyle={s.body}>
        <View style={s.card}>
          <AppText variant="bodyStrong">Onboarding arm</AppText>
          <AppText variant="small">
            source: {meta?.source ?? '—'}
            {meta?.default_reason ? ` (${meta.default_reason})` : ''}
            {meta?.fetch_ms !== undefined ? ` · ${meta.fetch_ms} ms` : ''}
          </AppText>
          <AppText variant="small">
            variation: {meta?.variation_name ?? meta?.variation_id ?? '—'} · test: {meta?.ab_test ?? '—'}
          </AppText>
          {getLateFetch() ? (
            <AppText variant="small">
              Adapty answered late: {getLateFetch()?.outcome} after {getLateFetch()?.ms} ms
            </AppText>
          ) : null}
          <AppText variant="small">tester mark: {tester ? 'on' : 'off'}</AppText>
          <AppText variant="small">{draftLine}</AppText>
          <AppText variant="caption" style={s.mono}>{JSON.stringify(config)}</AppText>
        </View>

        <AppText variant="eyebrow">Jump to a V3 screen</AppText>
        <View style={s.chips}>
          {QA_PRESETS.map((p) => (
            <Chip key={p.key} label={p.label} selected={preset === p.key} onPress={() => setPreset(p.key)} />
          ))}
        </View>
        <View style={s.chips}>
          {QA_SCREENS.map((x) => (
            <Chip key={x.route} label={`→ ${x.label}`} onPress={() => void jump(x.route)} />
          ))}
        </View>
        <View style={s.chips}>
          {QA_SCENARIOS.map((x) => (
            <Chip key={x.label} label={`★ ${x.label}`} onPress={() => void jump(x.route, x.overrides)} />
          ))}
          <Chip label="✕ clear overrides" onPress={() => update({})} />
        </View>

        <AppText variant="eyebrow">onb_main</AppText>
        <Choice label="onboarding" value={onb.onboarding} options={['v3', 'v1'] as const} onChange={(v) => setOnb({ onboarding: v })} />
        <Choice label="welcome.variant" value={onb.welcome?.variant} options={['A', 'B', 'C', 'D'] as const} onChange={(v) => setWelcome({ variant: v })} />
        <Choice label="welcome.render" value={onb.welcome?.render} options={['native', 'flow'] as const} onChange={(v) => setWelcome({ render: v })} />
        <Choice label="features" value={onb.features} options={['screen', 'off'] as const} onChange={(v) => setOnb({ features: v })} />
        <Choice label="social_proof.show" value={onb.social_proof?.show} options={ON_OFF} onChange={(v) => setSocial({ show: v })} />
        <Choice label="social_proof.hero" value={onb.social_proof?.hero} options={['before_after', 'text'] as const} onChange={(v) => setSocial({ hero: v })} />
        <Choice label="social_proof.render" value={onb.social_proof?.render} options={['native', 'flow'] as const} onChange={(v) => setSocial({ render: v })} />
        <Choice label="loader_review" value={onb.loader_review} options={ON_OFF} onChange={(v) => setOnb({ loader_review: v })} />
        <Choice label="plan" value={onb.plan} options={['chart', 'ahead'] as const} onChange={(v) => setOnb({ plan: v })} />
        <Choice label="att" value={onb.att} options={['loader', 'welcome'] as const} onChange={(v) => setOnb({ att: v })} />
        <Choice label="free_first_log" value={onb.free_first_log} options={ON_OFF} onChange={(v) => setOnb({ free_first_log: v })} />
        <Choice label="after_cancel_offer" value={onb.after_cancel_offer} options={ON_OFF} onChange={(v) => setOnb({ after_cancel_offer: v })} />
        <Choice label="tutorial" value={onb.tutorial} options={ON_OFF} onChange={(v) => setOnb({ tutorial: v })} />

        <AppText variant="eyebrow">onb_content</AppText>
        <Choice label="content" value={o.content} options={['demo'] as const} onChange={(v) => update({ ...o, content: v })} />

        <AppText variant="eyebrow">pw_main</AppText>
        <Choice label="render" value={pw.render} options={['native', 'flow', 'legacy'] as const} onChange={(v) => update({ ...o, paywall: { ...pw, render: v } })} />
        <Choice label="variant" value={pw.variant} options={PAYWALL_VARIANTS} onChange={(v) => update({ ...o, paywall: { ...pw, variant: v } })} />
        <Choice label="price_emphasis" value={pw.price_emphasis} options={['billed', 'design', 'weekly'] as const} onChange={(v) => update({ ...o, paywall: { ...pw, price_emphasis: v } })} />
        <Choice label="show_rating" value={pw.show_rating} options={ON_OFF} onChange={(v) => update({ ...o, paywall: { ...pw, show_rating: v } })} />

        <AppText variant="eyebrow">pw_after_cancel</AppText>
        <Choice label="render" value={offer.render} options={['native', 'flow'] as const} onChange={(v) => update({ ...o, offer: { ...offer, render: v } })} />
        <Choice label="variant" value={offer.variant} options={OFFER_VARIANTS} onChange={(v) => update({ ...o, offer: { ...offer, variant: v } })} />
        <Choice
          label="copy.headline"
          value={offer.copy?.headline}
          options={['Try it FREE', '50% OFF'] as const}
          onChange={(v) => update({ ...o, offer: { ...offer, copy: v ? { ...offer.copy, headline: v } : {} } })}
        />

        <AppText variant="eyebrow">Simulation</AppText>
        <Choice label="simulate Adapty timeout" value={o.simulate_timeout} options={[true] as const} onChange={(v) => update({ ...o, simulate_timeout: v })} />
        <Choice label="mock purchase (no StoreKit)" value={o.mock_purchase} options={[true] as const} onChange={(v) => update({ ...o, mock_purchase: v })} />

        <View style={s.actions}>
          <Button label="Restart onboarding" variant="brand" onPress={() => void restart()} />
          <Button
            label="Start the after-purchase tour (signed in)"
            variant="secondary"
            onPress={() =>
              void resetTour(true).then(() => {
                if (router.canDismiss()) router.dismissAll();
                router.replace('/(tabs)');
              })
            }
          />
          <Button
            label="Re-fetch arm from Adapty"
            variant="secondary"
            onPress={() => void clearOnboardingAssignment().then(resolveOnboardingAssignment)}
          />
          <Button label="Clear all overrides" variant="ghost" onPress={() => update({})} />
        </View>
      </ScrollView>
    </Screen>
  );
}

const s = StyleSheet.create({
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: space.lg,
    paddingVertical: space.sm,
  },
  body: { padding: space.lg, gap: space.md, paddingBottom: space.xxxl },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.hairline,
    padding: space.base,
    gap: 4,
  },
  mono: { marginTop: space.xs },
  row: { gap: 6 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  actions: { gap: space.sm, marginTop: space.md },
});
