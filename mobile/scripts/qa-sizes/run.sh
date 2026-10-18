#!/usr/bin/env bash
# Screenshot every V3 screen on several iPhone sizes, no tapping (QA builds only).
#
#   MOCKS=1 scripts/qa-sim-build.sh <any-udid>        # build the mock QA app first
#   scripts/qa-sizes/run.sh <out-dir> label=udid ...  # e.g. se=A1B1… max=5660…
#
# For each simulator: fresh install, QA overrides with `auto_tour: true` (see
# src/components/qa/QaAutoTour.tsx), then a screenshot whenever the app reports
# the next step. Sheets with every screen side by side: sheets.py.
set -euo pipefail
cd "$(dirname "$0")/../.."
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
OUT="${1:?out dir}"; shift
APP=ios/build/dd/Build/Products/Release-iphonesimulator/YumYummy.app
OVR='{"auto_tour":true,"mock_purchase":true,"onboarding":{"att":"welcome"},"paywall":{"render":"native"},"offer":{"render":"native"}}'
DRAFT='{"goal_type":"lose","gender":"female","age":32,"height_cm":165,"weight_kg":72,"activity_level":"light","target_weight_kg":66,"deficit_pct":null,"source":"instagram","tracked_before":true,"barrier":"too_long","pain_points":["too_long"],"units":"metric","pace_kg_week":0.5,"target_date":"2027-01-16","target_weeks":13,"target_calories":1430,"target_protein_g":115,"target_fat_g":43,"target_carbs_g":148}'
for pair in "$@"; do
  L="${pair%%=*}"; U="${pair#*=}"; D="$OUT/$L"; rm -rf "$D"; mkdir -p "$D"
  xcrun simctl boot "$U" >/dev/null 2>&1 || true; xcrun simctl bootstatus "$U" -b >/dev/null
  xcrun simctl uninstall "$U" ai.yumyummy.app >/dev/null 2>&1 || true
  xcrun simctl keychain "$U" reset >/dev/null 2>&1 || true
  xcrun simctl install "$U" "$APP"
  xcrun simctl status_bar "$U" override --time "9:41" --batteryState charged --batteryLevel 100 >/dev/null 2>&1 || true
  C=$(xcrun simctl get_app_container "$U" ai.yumyummy.app data)
  M="$C/Library/Application Support/ai.yumyummy.app/RCTAsyncLocalStorage_V1/manifest.json"
  mkdir -p "$(dirname "$M")"
  python3 -c 'import json,sys; json.dump({"@yy_qa_overrides": sys.argv[1], "@yy_intro_draft": sys.argv[2]}, open(sys.argv[3], "w"))' "$OVR" "$DRAFT" "$M"
  xcrun simctl launch "$U" ai.yumyummy.app >/dev/null
  last=""; start=$(date +%s)
  while true; do
    cur=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("@yy_qa_autotour",""))' "$M" 2>/dev/null || true)
    if [ -n "$cur" ] && [ "$cur" != "$last" ]; then
      last=$cur
      name=$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); print("%02d_%s" % (d["i"], d["name"]) if d["i"] >= 0 else "done")' "$cur")
      [ "$name" = "done" ] && break
      sleep 2.2
      xcrun simctl io "$U" screenshot --type=png "$D/$name.png" >/dev/null 2>&1
    fi
    [ $(( $(date +%s) - start )) -gt 480 ] && { echo "$L: timeout"; break; }
    sleep 0.3
  done
  echo "$L: $(ls "$D" | wc -l | tr -d ' ') screenshots"
done
python3 scripts/qa-sizes/sheets.py "$OUT" $(for p in "$@"; do printf '%s ' "${p%%=*}"; done)
