import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import * as AppleAuthentication from 'expo-apple-authentication';

import { getToken, setToken, USE_MOCKS } from '@/api/client';
import * as api from '@/api/endpoints';
import type { AccountProfile } from '@/api/types';
import {
  identifyAdapty,
  logoutAdapty,
  getAdaptyProfileId,
  setAdaptyIntegrationIdentifier,
} from '@/billing/adapty';
import { identify as phIdentify, reset as phReset, track } from '@/analytics/posthog';
import { setUser as sentrySetUser, clearUser as sentryClearUser } from '@/analytics/sentry';
import { setAttributionCustomerId } from '@/analytics/attribution';

type AuthStatus = 'loading' | 'signedOut' | 'signedIn';

type Provider = 'apple' | 'google';

interface AuthContextValue {
  status: AuthStatus;
  profile: AccountProfile | null;
  requestEmailCode: (email: string) => Promise<string | null>;
  signInWithEmail: (email: string, code: string) => Promise<void>;
  signInWithDemoEmail: () => Promise<void>;
  /** False when the customer dismissed the provider's sheet without signing in. */
  signInWithProvider: (provider: Provider) => Promise<boolean>;
  signInFromTelegram: (code: string) => Promise<void>;
  linkTelegram: (code: string) => Promise<void>;
  refreshProfile: () => Promise<void>;
  applyProfile: (profile: AccountProfile) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [profile, setProfile] = useState<AccountProfile | null>(null);

  // `method` is set only on a genuine sign-in (Apple/Google/email/…), not on
  // boot session-restore, so `signin_success` fires exactly once per login.
  const loadProfile = useCallback(async (method?: string) => {
    const me = await api.getMe();
    setProfile(me);
    setStatus('signedIn');
    setAttributionCustomerId(me.account_id);
    // identify() links the anonymous onboarding distinct_id to account_id, so
    // pre-login funnel events (paywall_shown, onboarding_*) stitch to the user.
    phIdentify(String(me.account_id), { goal: me.goal_type });
    sentrySetUser(String(me.account_id));
    if (method) track('signin_success', { method });

    // People buy before signing in, so the purchase sits on an anonymous Adapty
    // profile and its webhook reached us with no customer_user_id. Read that
    // profile id first, then identify (awaited — a racing sync would resolve
    // against the pre-merge profile and find nothing), then reconcile.
    void (async () => {
      const adaptyProfileId = await getAdaptyProfileId();
      await identifyAdapty(me.account_id);
      await setAdaptyIntegrationIdentifier(
        'posthog_distinct_user_id',
        String(me.account_id),
      );
      try {
        const billing = await api.syncBilling(adaptyProfileId);
        setProfile((prev) => (prev ? { ...prev, billing } : prev));
      } catch {
        // entitlement stays as the backend last reported it
      }
    })();
  }, []);

  // Boot: if a token is stored, resolve the account.
  useEffect(() => {
    let active = true;
    (async () => {
      const token = await getToken();
      if (!active) return;
      if (!token) {
        setStatus('signedOut');
        return;
      }
      try {
        await loadProfile();
      } catch {
        await setToken(null);
        if (active) setStatus('signedOut');
      }
    })();
    return () => {
      active = false;
    };
  }, [loadProfile]);

  const requestEmailCode = useCallback(async (email: string) => {
    const res = await api.requestEmailCode(email);
    return res.debug_code ?? null;
  }, []);

  const signInWithEmail = useCallback(
    async (email: string, code: string) => {
      const res = await api.verifyEmailCode(email, code);
      await setToken(res.access_token);
      await loadProfile('email');
    },
    [loadProfile],
  );

  // One-tap entry into the live app using a stable demo email. The backend
  // returns the login code in the response while AUTH_EMAIL_DEBUG_RETURN_CODE
  // is on, so this works in Expo Go without a native build.
  const signInWithDemoEmail = useCallback(async () => {
    const email = 'demo@yumyummy.ai';
    const res = await api.requestEmailCode(email);
    const code = res.debug_code;
    if (!code) {
      throw new Error('Demo sign-in is unavailable right now — try email instead.');
    }
    const token = await api.verifyEmailCode(email, code);
    await setToken(token.access_token);
    await loadProfile('demo');
  }, [loadProfile]);

  /**
   * Resolves `false` when the customer dismissed Apple's sheet, `true` once an
   * account is actually signed in. Callers MUST branch on it: a cancel used to
   * resolve like a success, which let people through the save-plan gate with no
   * account at all and stranded their purchase on an anonymous Adapty profile.
   */
  const signInWithApple = useCallback(async (): Promise<boolean> => {
    // Native Sign in with Apple. Only available in a dev/TestFlight build
    // (the capability is compiled in) — not in Expo Go.
    const available = await AppleAuthentication.isAvailableAsync().catch(() => false);
    if (!available) {
      throw new Error('Sign in with Apple isn’t available on this device — use email instead.');
    }
    let identityToken: string | null;
    let fullName: string | null = null;
    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });
      identityToken = credential.identityToken;
      // Populated on the first authorisation only; every later sign-in returns
      // null, so this value has to reach the backend now or never.
      fullName = [credential.fullName?.givenName, credential.fullName?.familyName]
        .filter(Boolean)
        .join(' ')
        .trim() || null;
    } catch (e) {
      // The user cancelling the native sheet shouldn't surface as an error.
      if (e && typeof e === 'object' && (e as { code?: string }).code === 'ERR_REQUEST_CANCELED') {
        return false;
      }
      throw e;
    }
    if (!identityToken) throw new Error('Apple did not return an identity token. Please try again.');
    const res = await api.signInApple(identityToken, fullName);
    await setToken(res.access_token);
    await loadProfile('apple');
    return true;
  }, [loadProfile]);

  const signInWithProvider = useCallback(
    async (provider: Provider): Promise<boolean> => {
      if (provider === 'apple') {
        if (USE_MOCKS) {
          const res = await api.signInApple('apple-placeholder-identity-token');
          await setToken(res.access_token);
          await loadProfile('apple');
          return true;
        }
        return signInWithApple();
      }

      // Google: native sign-in (@react-native-google-signin) lands in a later
      // build. Against the real API, steer the user to email for now.
      if (USE_MOCKS) {
        const res = await api.signInGoogle('google-placeholder-identity-token');
        await setToken(res.access_token);
        await loadProfile('google');
        return true;
      }
      throw new Error('Google sign-in arrives in the next build — use Apple or email for now.');
    },
    [loadProfile, signInWithApple],
  );

  const signInFromTelegram = useCallback(
    async (code: string) => {
      // Mock: a bot link code logs you straight in and links Telegram.
      // TODO(real-auth): the backend's redeem endpoint requires an existing
      // signed-in account (JWT). For production, either add a dedicated
      // "sign in with Telegram link code" endpoint, or have users sign in with
      // Apple/Google/email first and then link Telegram from Profile.
      if (USE_MOCKS) {
        await setToken('telegram.session.token');
        await api.redeemTelegramLink(code);
        await loadProfile('telegram');
        return;
      }
      const token = await getToken();
      if (!token) {
        throw new Error(
          'Sign in with Apple, Google, or email first, then link Telegram in Profile.',
        );
      }
      await api.redeemTelegramLink(code);
      await loadProfile('telegram');
    },
    [loadProfile],
  );

  const linkTelegram = useCallback(
    async (code: string) => {
      await api.redeemTelegramLink(code);
      await loadProfile();
    },
    [loadProfile],
  );

  const refreshProfile = useCallback(async () => {
    const me = await api.getMe();
    setProfile(me);
  }, []);

  const applyProfile = useCallback((next: AccountProfile) => {
    setProfile(next);
  }, []);

  const signOut = useCallback(async () => {
    await setToken(null);
    setProfile(null);
    setStatus('signedOut');
    void logoutAdapty();
    phReset();
    sentryClearUser();
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      profile,
      requestEmailCode,
      signInWithEmail,
      signInWithDemoEmail,
      signInWithProvider,
      signInFromTelegram,
      linkTelegram,
      refreshProfile,
      applyProfile,
      signOut,
    }),
    [status, profile, requestEmailCode, signInWithEmail, signInWithDemoEmail, signInWithProvider, signInFromTelegram, linkTelegram, refreshProfile, applyProfile, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>');
  return ctx;
}
