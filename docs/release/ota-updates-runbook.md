# OTA Updates Runbook — EAS Update

From 1.0.2 the app ships with `expo-updates`, so JavaScript-only changes
(paywall copy, layouts, prices, analytics, most bug fixes) reach users without
an App Store review. Anything native still needs a full build and review.

## What can and cannot go out over the air

| Change | OTA? |
| --- | --- |
| Paywall copy, layout, new `PaywallRenderer` variants | yes |
| Screens, navigation, analytics events, business logic | yes |
| Bundled assets (images, fonts) referenced from JS | yes |
| A new native module, or a version bump of one | no — new binary |
| `app.json` native config (permissions, entitlements, plugins) | no — new binary |
| `expo.version` bump | no — it changes the runtime version, see below |

## How targeting works

- **Runtime version** is `expo.version` (`runtimeVersion.policy: "appVersion"` in
  `app.json`). An update is only ever delivered to binaries with the *same*
  runtime version — so an update published while `expo.version` is `1.0.2`
  reaches 1.0.2 installs and can never land on 1.0.1 or on a future 1.0.3.
  This is the safety net: JS that calls into a native module the older binary
  doesn't have simply never reaches it.
- **Channel** is set per EAS build profile in `eas.json`
  (`production` / `preview` / `development`). TestFlight and App Store builds
  come from the `production` profile and therefore listen on the `production`
  channel.
- The app checks for an update on launch and downloads it in the background
  (`fallbackToCacheTimeout: 0`), so launch is never delayed. **The new bundle
  activates on the next launch**, not the current one — expect a one-launch lag
  when verifying.

## Publishing an update

Always dry-run on `preview` first if there is a preview build of the same
runtime version installed; otherwise go straight to production and watch
Sentry.

```bash
cd mobile
npx tsc --noEmit && npx expo lint     # never publish red

# 1. Preview (internal testers on the preview channel)
eas update --branch preview --message "paywall: weekly price on plan cards"

# 2. Production (TestFlight + App Store users on 1.0.2)
eas update --branch production --message "paywall: weekly price on plan cards"
```

Verify what a build will actually receive:

```bash
eas update:list --branch production          # recent updates + their runtime versions
eas channel:view production                  # which branch the channel points at
```

## Rolling back

Republish the last known-good update — it becomes the newest one on the branch
and supersedes the bad bundle on the next launch:

```bash
eas update:republish --branch production --group <update-group-id>
```

`eas update:list --branch production` prints the group ids. There is no way to
recall an update already running on a device before its next launch, so treat
production publishes with the same care as a release.

## After bumping `expo.version`

A version bump changes the runtime version, which orphans the update branch:
freshly built binaries find no update for their runtime version (fine — they
already carry the newest JS), but the first OTA for that version has to be
published after the build. Order of operations for a release:

1. Bump `expo.version` in `app.json`.
2. `eas build --platform ios --profile production` → submit → release.
3. Only then publish OTA updates against the new version.
