# YumYummy — Mobile app (Expo / React Native)

The native iOS-first app for YumYummy, built on the **Phase 1** account-scoped API
(`/auth/*`, `/app/*`). It shares one profile, diary, saved meals and subscription with
the Telegram bot once the two are linked.

> This is the **Phase 2 skeleton**: the full design system + all core flows, wired to the
> real API with a built-in mock fallback so it runs with or without a backend.

## Requirements

- Node 18+ (tested on Node 22)
- The **Expo Go** app on your iPhone (App Store), or Xcode for the iOS simulator

## Quick start

```bash
cd mobile
npm install
npx expo start
```

Then either:

- **iPhone:** open **Expo Go** and scan the QR code in the terminal, or
- **Simulator:** press `i` in the terminal (requires Xcode).

By default there is **no `.env`**, so the app runs on **mock data** — you can click through
every screen (sign-in → onboarding → today → capture → week → menu → advisor → paywall →
profile) without a server.

### Pointing at the real backend

```bash
cp .env.example .env
# edit .env and set EXPO_PUBLIC_API_BASE_URL=https://<your-phase1-api>
npx expo start -c   # -c clears the cache so the new env is picked up
```

When an API URL is set, the app calls the real endpoints; read calls fall back to mock data
if the server is unreachable, so the UI never breaks during development.

## Useful scripts

- `npm run start` — start Metro / Expo
- `npm run ios` — start and open the iOS simulator
- `npx tsc --noEmit` — type-check (passes clean)
- `npm run lint` — lint

## Project structure

```
src/
  api/         typed client, endpoints, mock store, photo upload
  components/  design system (Button, Card, Ring, MacroBar, badges, WheelPicker, TabBar…)
  state/       AuthProvider, onboarding draft
  theme/       tokens (colors/space/radius), typography, font loader
  utils/       calorie plan (Mifflin–St Jeor), formatters
  app/         expo-router routes
    (auth)/sign-in
    (onboarding)/goal · profile · plan · first-log
    (tabs)/index(Today) · menu · week · profile   + center "+" capture button
    capture · advisor · paywall · meal/[id]
```

## What's wired vs. left as TODO

**Wired to the API:** email magic-link sign-in, `GET/PATCH /me`, `GET /today`, meals
create/delete, recent + saved meals, `POST /agent/run` (text & photo), `GET /billing/status`,
`POST /billing/trial/start`, photo presign upload, Telegram link redeem.

**Intentionally scaffolded (clearly marked `TODO` in code):**

- **Adapty** paywall/SDK — `src/app/paywall.tsx` is remote-config-shaped; swap the static
  config for the Adapty payload and wire the StoreKit purchase.
- **Apple / Google native sign-in** — buttons + flow exist; plug real credentials
  (`expo-apple-authentication` / Google) in `src/state/auth.tsx` (needs a dev build).
- **Voice capture** — mic button present; needs audio record + server transcription (dev build).
- **Account deletion endpoint** — Profile has the Apple-required entry point; add a backend
  `DELETE /app/me`.
- A couple of small backend follow-ups are noted inline (saved-meal `user_id`, meal `PATCH`).
