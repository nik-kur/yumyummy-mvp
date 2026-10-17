/**
 * React context for the intro onboarding draft.
 *
 * Wraps AsyncStorage persistence: on mount loads from disk, every `set` call
 * saves to disk. This lets the user resume onboarding after an app kill.
 */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  type IntroDraft,
  DEFAULT_DRAFT,
  loadDraft,
  saveDraft,
  clearDraft,
  onDraftReplaced,
} from './introDraft';

interface IntroContextValue extends IntroDraft {
  set: (patch: Partial<IntroDraft>) => void;
  clear: () => void;
  ready: boolean;
}

const IntroContext = createContext<IntroContextValue | null>(null);

export function IntroProvider({ children }: { children: React.ReactNode }) {
  const [draft, setDraft] = useState<IntroDraft>(DEFAULT_DRAFT);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const load = () =>
      loadDraft().then((d) => {
        setDraft(d);
        setReady(true);
      });
    void load();
    return onDraftReplaced(() => void load());
  }, []);

  const set = useCallback((patch: Partial<IntroDraft>) => {
    setDraft((prev) => {
      const next = { ...prev, ...patch };
      void saveDraft(next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    setDraft(DEFAULT_DRAFT);
    void clearDraft();
  }, []);

  const value = useMemo<IntroContextValue>(
    () => ({ ...draft, set, clear, ready }),
    [draft, set, clear, ready],
  );

  // Screens never see the defaults while the stored answers load (a few ms):
  // screens that freeze values on mount (goal check, loader) would keep them.
  return <IntroContext.Provider value={value}>{ready ? children : null}</IntroContext.Provider>;
}

export function useIntro(): IntroContextValue {
  const ctx = useContext(IntroContext);
  if (!ctx) throw new Error('useIntro must be used within <IntroProvider>');
  return ctx;
}
