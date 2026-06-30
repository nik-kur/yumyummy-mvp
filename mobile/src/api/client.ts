import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'yumyummy.jwt';

/**
 * Base URL of the Phase 1 FastAPI backend. Set via `EXPO_PUBLIC_API_BASE_URL`
 * in `.env`. When empty, the app runs entirely on local mock data so every
 * screen is clickable without a server (see `USE_MOCKS`).
 */
export const API_BASE_URL = (process.env.EXPO_PUBLIC_API_BASE_URL ?? '').replace(/\/+$/, '');

/** Mocks are on when no API URL is configured, or when forced via env. */
export const USE_MOCKS =
  API_BASE_URL === '' || process.env.EXPO_PUBLIC_USE_MOCKS === '1';

let memToken: string | null = null;
let tokenLoaded = false;

export async function getToken(): Promise<string | null> {
  if (tokenLoaded) return memToken;
  try {
    memToken = (await SecureStore.getItemAsync(TOKEN_KEY)) ?? null;
  } catch {
    memToken = null;
  }
  tokenLoaded = true;
  return memToken;
}

export async function setToken(token: string | null): Promise<void> {
  memToken = token;
  tokenLoaded = true;
  try {
    if (token) await SecureStore.setItemAsync(TOKEN_KEY, token);
    else await SecureStore.deleteItemAsync(TOKEN_KEY);
  } catch {
    // SecureStore may be unavailable in some sandboxes; keep the in-memory copy.
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

type Query = Record<string, string | number | boolean | undefined>;

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE' | 'PUT';
  body?: unknown;
  auth?: boolean;
  query?: Query;
  /**
   * Abort the request after this many ms. Defaults to 30s. The agent run passes
   * a much larger value because its source-checked workflow (esp. photos) can
   * legitimately take 1–2 minutes; without a bound a dropped connection would
   * otherwise hang the caller forever.
   */
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 30_000;

function buildQuery(query?: Query): string {
  if (!query) return '';
  const parts = Object.entries(query)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join('&')}` : '';
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, auth = true, query, timeoutMs = DEFAULT_TIMEOUT_MS } = options;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = await getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}${buildQuery(query)}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (e) {
    const aborted = e instanceof Error && e.name === 'AbortError';
    throw new ApiError(0, aborted ? 'Request timed out' : e instanceof Error ? e.message : 'Network request failed');
  } finally {
    clearTimeout(timer);
  }

  const rawText = await res.text();
  let data: unknown = null;
  if (rawText) {
    try {
      data = JSON.parse(rawText);
    } catch {
      data = rawText;
    }
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    if (data && typeof data === 'object') {
      const obj = data as Record<string, unknown>;
      if (typeof obj.detail === 'string') detail = obj.detail;
      else if (typeof obj.message === 'string') detail = obj.message;
    } else if (typeof data === 'string' && data) {
      detail = data;
    }
    throw new ApiError(res.status, detail);
  }

  return data as T;
}
