#!/usr/bin/env bash
# Local QA build for the iOS Simulator (Release JS bundle, arm64 only).
#
# QA flags and the public SDK keys are passed through the environment of this
# one build only — never via a .env file, which `eas update` would also pick up
# and ship QA mode (AppsFlyer off, QA menu) to every user.
#
# Usage: scripts/qa-sim-build.sh <simulator-udid>
set -euo pipefail
cd "$(dirname "$0")/.."

UDID="${1:?simulator udid}"
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
export LANG=en_US.UTF-8
export SENTRY_DISABLE_AUTO_UPLOAD=true

# Public keys from the EAS preview profile, plus the QA switch.
eval "$(python3 - <<'EOF'
import json, shlex
env = json.load(open('eas.json'))['build']['preview']['env']
for k in ('EXPO_PUBLIC_API_BASE_URL', 'EXPO_PUBLIC_ADAPTY_IOS_SDK_KEY', 'EXPO_PUBLIC_POSTHOG_API_KEY',
          'EXPO_PUBLIC_POSTHOG_HOST', 'EXPO_PUBLIC_SENTRY_DSN'):
    print(f'export {k}={shlex.quote(env[k])}')
EOF
)"
export EXPO_PUBLIC_QA_BUILD=1
# MOCKS=1: the app talks to the in-app mock API (sign-in without an Apple ID,
# a fresh diary), so the after-purchase screens and the tour can be walked in
# the simulator. Never for a build that leaves this Mac.
if [ "${MOCKS:-0}" = "1" ]; then export EXPO_PUBLIC_USE_MOCKS=1; else unset EXPO_PUBLIC_USE_MOCKS; fi
# Metro caches transforms across builds and does not key them on env vars:
# start from a clean cache, and wipe it again afterwards so a later production
# bundle on this Mac (`eas update`, `expo export`) cannot reuse QA transforms.
export EXTRA_PACKAGER_ARGS="--reset-cache"
trap 'rm -rf "${TMPDIR:-/tmp}"/metro-* "${TMPDIR:-/tmp}"/haste-map-* 2>/dev/null || true' EXIT
# AppsFlyer stays unset: a QA build must never report installs or purchases.
export EXPO_PUBLIC_APPSFLYER_DEV_KEY=

cd ios
xcodebuild -workspace YumYummy.xcworkspace -scheme YumYummy -configuration Release \
  -sdk iphonesimulator -destination "id=${UDID}" \
  ONLY_ACTIVE_ARCH=YES ARCHS=arm64 \
  -derivedDataPath build/dd build
echo "APP: $(pwd)/build/dd/Build/Products/Release-iphonesimulator/YumYummy.app"
