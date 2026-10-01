/**
 * Onboarding flow — the quiz (S1 welcome … S10 fix) rendered by Adapty from
 * placement `onb_main`, so its screens can be changed and A/B-tested in the
 * dashboard without a release.
 *
 * The app stays in charge of everything the flow cannot do:
 *   - the answers are mirrored into the intro draft as the user gives them
 *     (`flow_user_input` events → `flowInputToDraftPatch`);
 *   - when the flow says it is done (custom action `quiz_done`, or a "close
 *     flow" action) the native screens take over for the plan math: target &
 *     pace for lose/gain, the loader for everyone else, then plan reveal and
 *     the paywall;
 *   - no flow (offline, nothing published, render error) → the native welcome
 *     → quiz screens, unchanged from 1.0.9.
 *
 * Contract (ids, actions, tags): `billing/flowBridge.ts`.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { useRouter } from 'expo-router';
import { AdaptyFlowView } from 'react-native-adapty';
import type { AdaptyFlow, CreateFlowViewParamsInput } from 'react-native-adapty';

import { requestTrackingConsent } from '@/analytics/attribution';
import { track } from '@/analytics/posthog';
import { addBreadcrumb, captureException } from '@/analytics/sentry';
import { ADAPTY_PLACEMENT_ONBOARDING_FLOW, fetchAdaptyFlow } from '@/billing/adapty';
import {
  FLOW_ACTION_QUIZ_DONE,
  FLOW_ACTION_REQUEST_ATT,
  FLOW_ACTION_SIGN_IN,
  draftIsComplete,
  flowInputToDraftPatch,
  handleFlowPermissionRequest,
  trackFlowAnalytics,
  type FlowImperialScratch,
} from '@/billing/flowBridge';
import { useIntro } from '@/state/introContext';
import { colors } from '@/theme/tokens';

/** Cap the fetch so a slow network shows the native quiz instead of a spinner. */
const ONBOARDING_FLOW_TIMEOUT_MS = 5000;

type FallbackReason = 'no_flow' | 'no_view' | 'render_error' | 'incomplete_draft' | 'disabled';

/**
 * Remote kill switch: a flow on `onb_main` whose remote config carries
 * `{"use_native": true}` hands the onboarding back to the native screens
 * without a release. Lets the dashboard keep a published flow around (for a
 * later A/B test) while production runs the native quiz.
 */
function flowDisabledByRemoteConfig(flow: AdaptyFlow): boolean {
  return flow.remoteConfigs?.some((rc) => rc.data?.use_native === true) ?? false;
}

export default function IntroFlowScreen() {
  const router = useRouter();
  const intro = useIntro();
  const [flow, setFlow] = useState<AdaptyFlow | null>(null);
  const scratch = useRef<FlowImperialScratch>({});
  const doneRef = useRef(false);
  // The completion handler runs from a native callback; read the draft
  // through a ref so it sees the answers given a moment ago.
  const introRef = useRef(intro);
  useEffect(() => {
    introRef.current = intro;
  }, [intro]);

  const context = useMemo(
    () => ({
      placement: ADAPTY_PLACEMENT_ONBOARDING_FLOW,
      variation: flow?.variationId,
      variationName: flow?.variationName,
    }),
    [flow],
  );

  const fallback = useCallback(
    (reason: FallbackReason) => {
      if (doneRef.current) return;
      doneRef.current = true;
      track('onboarding_flow_fallback', { placement: ADAPTY_PLACEMENT_ONBOARDING_FLOW, reason });
      addBreadcrumb('onboarding', 'Flow unavailable → native intro', { reason });
      // A broken flow after some answers: the native quiz starts at the goal
      // and pre-fills from the draft, so nothing typed so far is lost.
      router.replace(reason === 'incomplete_draft' ? '/(intro)/goal' : '/(intro)/welcome');
    },
    [router],
  );

  const finishQuiz = useCallback(
    (source: string) => {
      if (doneRef.current) return;
      const draft = introRef.current;
      if (!draftIsComplete(draft)) {
        // The flow ended without the fields the plan math needs — a dashboard
        // edit dropped an id, most likely. Finish the quiz natively.
        captureException(new Error('onboarding flow finished with incomplete draft'), {
          source,
          goal: draft.goal_type,
          gender: draft.gender,
          activity: draft.activity_level,
        });
        fallback('incomplete_draft');
        return;
      }
      doneRef.current = true;
      track('onboarding_flow_completed', {
        placement: ADAPTY_PLACEMENT_ONBOARDING_FLOW,
        variation_id: flow?.variationId,
        variation_name: flow?.variationName,
        source,
        goal: draft.goal_type,
      });
      addBreadcrumb('onboarding', 'Flow quiz done → native plan screens', { goal: draft.goal_type });
      const needsTarget = draft.goal_type === 'lose' || draft.goal_type === 'gain';
      router.replace(needsTarget ? '/(intro)/target-pace' : '/(intro)/loader');
    },
    [fallback, flow, router],
  );

  useEffect(() => {
    let alive = true;
    void (async () => {
      const fetched = await fetchAdaptyFlow(
        ADAPTY_PLACEMENT_ONBOARDING_FLOW,
        ONBOARDING_FLOW_TIMEOUT_MS,
      );
      if (!alive) return;
      if (!fetched) {
        fallback('no_flow');
        return;
      }
      if (!fetched.hasViewConfiguration) {
        fallback('no_view');
        return;
      }
      if (flowDisabledByRemoteConfig(fetched)) {
        fallback('disabled');
        return;
      }
      setFlow(fetched);
      track('onboarding_flow_shown', {
        placement: ADAPTY_PLACEMENT_ONBOARDING_FLOW,
        variation_id: fetched.variationId,
        variation_name: fetched.variationName,
        ab_test: fetched.placement?.abTestName,
        audience: fetched.placement?.audienceName,
      });
    })();
    return () => {
      alive = false;
    };
  }, [fallback]);

  const params = useMemo<CreateFlowViewParamsInput>(() => ({}), []);

  if (!flow || !intro.ready) {
    return (
      <View style={s.loading}>
        <ActivityIndicator color={colors.terracotta} />
      </View>
    );
  }

  return (
    <View style={s.fill}>
      <AdaptyFlowView
        flow={flow}
        params={params}
        style={s.fill}
        onAnalytics={(name, eventParams) => {
          trackFlowAnalytics(context, name, eventParams);
          if (name === 'flow_user_input') {
            const patch = flowInputToDraftPatch(eventParams, scratch.current);
            if (Object.keys(patch).length > 0) introRef.current.set(patch);
          }
          return false;
        }}
        onCustomAction={(actionId) => {
          switch (actionId) {
            case FLOW_ACTION_QUIZ_DONE:
              finishQuiz('custom_action');
              break;
            case FLOW_ACTION_SIGN_IN:
              track('onboarding_screen_completed', { screen: 'S1_welcome', action: 'sign_in' });
              router.replace('/(auth)/sign-in');
              break;
            case FLOW_ACTION_REQUEST_ATT:
              void requestTrackingConsent().then((granted) =>
                track('att_prompt_answered', { granted, source: 'adapty_flow_action' }),
              );
              break;
            default:
              track('adapty_flow_custom_action', { ...context, action_id: actionId });
          }
          return false;
        }}
        // A "Close flow" action on the last screen means the same as quiz_done.
        onCloseButtonPress={() => {
          finishQuiz('close');
          return false;
        }}
        onRequestPermission={handleFlowPermissionRequest}
        onError={(error) => {
          captureException(error, { placement: ADAPTY_PLACEMENT_ONBOARDING_FLOW });
          fallback('render_error');
          return false;
        }}
      />
    </View>
  );
}

const s = StyleSheet.create({
  fill: { flex: 1, backgroundColor: colors.bg },
  loading: {
    flex: 1,
    backgroundColor: colors.bg,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
