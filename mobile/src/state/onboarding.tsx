import React, { createContext, useContext, useMemo, useState } from 'react';
import type { ActivityLevel, Gender, GoalType } from '@/utils/calories';

export interface OnboardingDraft {
  goal_type: GoalType | null;
  gender: Gender | null;
  age: number;
  height_cm: number;
  weight_kg: number;
  activity_level: ActivityLevel | null;
}

interface OnboardingContextValue extends OnboardingDraft {
  set: (patch: Partial<OnboardingDraft>) => void;
}

const DEFAULT_DRAFT: OnboardingDraft = {
  goal_type: null,
  gender: null,
  age: 30,
  height_cm: 175,
  weight_kg: 75,
  activity_level: null,
};

const OnboardingContext = createContext<OnboardingContextValue | null>(null);

export function OnboardingProvider({ children }: { children: React.ReactNode }) {
  const [draft, setDraft] = useState<OnboardingDraft>(DEFAULT_DRAFT);
  const value = useMemo<OnboardingContextValue>(
    () => ({
      ...draft,
      set: (patch) => setDraft((d) => ({ ...d, ...patch })),
    }),
    [draft],
  );
  return <OnboardingContext.Provider value={value}>{children}</OnboardingContext.Provider>;
}

export function useOnboarding(): OnboardingContextValue {
  const ctx = useContext(OnboardingContext);
  if (!ctx) throw new Error('useOnboarding must be used within <OnboardingProvider>');
  return ctx;
}
