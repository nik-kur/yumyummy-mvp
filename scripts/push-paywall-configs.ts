#!/usr/bin/env npx tsx
/**
 * Push paywall remote configs to Adapty via the Server API.
 *
 * Usage:
 *   ADAPTY_SERVER_API_KEY=secret_live_... npx tsx scripts/push-paywall-configs.ts
 *
 * Adapty has TWO paywall entities (see `npx adapty@latest paywalls list`):
 *   - "Main Paywall"        (main placement / hard gate)
 *   - "Onboarding Paywall"  (onboarding placement)
 *
 * The A/B/B2/C layouts are NOT separate Adapty paywalls — the renderer picks a
 * layout from the `variant` field inside the remote-config JSON. So each Adapty
 * paywall gets ONE config file pushed as its `en` remote config. A/B testing is
 * layered later in the Adapty dashboard (audiences / A-B tests).
 *
 * The remote config `data` must be a serialized JSON string. See:
 *   https://adapty.io/docs/ss-update-paywall
 *   PUT /api/v2/server-side-api/paywalls/{paywall_id}/
 */
import { readFileSync } from 'fs';
import { join } from 'path';

const API_KEY = process.env.ADAPTY_SERVER_API_KEY;
if (!API_KEY) {
  console.error('Set ADAPTY_SERVER_API_KEY env var (secret_live_...)');
  process.exit(1);
}

const BASE = 'https://api.adapty.io/api/v2/server-side-api';
const CONFIG_DIR = join(__dirname, '..', 'config', 'paywalls');

// Map Adapty paywall title -> local config file to push as its remote config.
const TITLE_TO_CONFIG: Record<string, string> = {
  'Main Paywall': 'a.json',
  'Onboarding Paywall': 'a.json',
};

interface AdaptyPaywall {
  title: string;
  paywall_id: string;
}

async function listPaywalls(): Promise<AdaptyPaywall[]> {
  const resp = await fetch(`${BASE}/paywalls/`, {
    headers: { Authorization: `Api-Key ${API_KEY}` },
  });
  if (!resp.ok) {
    throw new Error(`list paywalls failed: ${resp.status} ${await resp.text()}`);
  }
  const json = (await resp.json()) as { data: AdaptyPaywall[] };
  return json.data;
}

async function pushConfig(paywall: AdaptyPaywall, file: string): Promise<void> {
  const configStr = readFileSync(join(CONFIG_DIR, file), 'utf-8');
  JSON.parse(configStr); // validate before sending

  const resp = await fetch(`${BASE}/paywalls/${paywall.paywall_id}/`, {
    method: 'PUT',
    headers: {
      Authorization: `Api-Key ${API_KEY}`,
      'Content-Type': 'application/json',
    },
    // `data` is the serialized config JSON string the app parses at runtime.
    body: JSON.stringify({
      remote_configs: [{ locale: 'en', data: configStr }],
    }),
  });

  if (!resp.ok) {
    console.error(`FAIL ${paywall.title}: ${resp.status} ${await resp.text()}`);
  } else {
    console.log(`OK   ${paywall.title} <- ${file}`);
  }
}

async function main() {
  const paywalls = await listPaywalls();
  for (const pw of paywalls) {
    const file = TITLE_TO_CONFIG[pw.title];
    if (!file) {
      console.warn(`SKIP ${pw.title}: no config mapping`);
      continue;
    }
    await pushConfig(pw, file);
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
