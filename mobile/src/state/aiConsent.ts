/**
 * AI data-processing consent (App Review Guidelines 5.1.1(i) / 5.1.2(i)).
 *
 * Apple requires explicit user permission BEFORE personal data (meal text,
 * voice audio, food photos) is sent to third-party AI providers. We gate the
 * capture and advisor screens on this one-time consent.
 *
 * The flag is stored locally (SecureStore) — deliberately per-device: after a
 * reinstall the user is simply asked again, which is the safe direction.
 */
import { useCallback, useEffect, useState } from 'react';
import * as SecureStore from 'expo-secure-store';

import { track } from '@/analytics/posthog';

const STORAGE_KEY = 'yy.ai_consent.v1';

/**
 * Single source of truth for "who receives the data" copy shown in the consent
 * sheet. Keep in sync with the Sub-processors section of
 * https://yumyummy.ai/privacy.html when providers change.
 */
export const AI_PROVIDERS_LABEL = 'Google (Gemini), Perplexity and OpenAI';

let cached: boolean | null = null;

export async function hasAIConsent(): Promise<boolean> {
  if (cached !== null) return cached;
  try {
    cached = (await SecureStore.getItemAsync(STORAGE_KEY)) !== null;
  } catch {
    cached = false;
  }
  return cached;
}

export async function grantAIConsent(): Promise<void> {
  cached = true;
  track('ai_consent_granted');
  try {
    await SecureStore.setItemAsync(STORAGE_KEY, new Date().toISOString());
  } catch {
    // Best-effort: the in-memory flag still unblocks this session.
  }
}

interface AIConsentState {
  /** null while loading from storage. */
  granted: boolean | null;
  grant: () => Promise<void>;
}

export function useAIConsent(): AIConsentState {
  const [granted, setGranted] = useState<boolean | null>(cached);

  useEffect(() => {
    if (granted !== null) return;
    let active = true;
    void hasAIConsent().then((v) => {
      if (active) setGranted(v);
    });
    return () => {
      active = false;
    };
  }, [granted]);

  const grant = useCallback(async () => {
    await grantAIConsent();
    setGranted(true);
  }, []);

  return { granted, grant };
}
