#!/usr/bin/env bash
# Switch what Nikita's tester phone sees: rewrite the remote config of one `_qa`
# flow in Adapty and publish it. Live placements and A/B tests are not touched.
# See docs/knowledge/adapty-control-registry.md, "Тестовый телефон", for keys.
#
#   scripts/adapty_tester_switch.sh <onb_main_qa|onb_content_qa|pw_main_qa|pw_after_cancel_qa> '<json>'
#   scripts/adapty_tester_switch.sh pw_main_qa '{"render":"native","variant":"p1_photo","price_emphasis":"billed","show_rating":true}'
#
# Needs the Adapty CLI logged in (`npx adapty@0.9.5 auth login`); set ADAPTY to
# an installed binary to skip npx.
set -uo pipefail
APP=356b7d68-ddae-41f8-8d3a-2bac9ce1cfa2
ADAPTY=${ADAPTY:-"npx --yes adapty@0.9.5"}

case "${1:-}" in
  onb_main_qa) ID=a8b40dfc-c3a7-478f-81d3-2053f930df99 ;;
  onb_content_qa) ID=cf4ada7f-4303-4fdc-97b1-a5f9fffe0dd9 ;;
  pw_main_qa) ID=88072cc9-7ca9-47df-9d26-992d170f44f8 ;;
  pw_after_cancel_qa) ID=29900e97-e90f-4775-a474-64c95fdcd11b ;;
  *) echo "usage: $0 <onb_main_qa|onb_content_qa|pw_main_qa|pw_after_cancel_qa> '<json>'" >&2; exit 2 ;;
esac
NAME=$1
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

RC=$(python3 -c 'import json,sys; print(json.dumps([{"locale": "en", "data": json.dumps(json.loads(sys.argv[1]), separators=(",", ":"))}]))' "${2:?remote config JSON}") || exit 1

# One retry loop for Adapty's occasional "fetch failed".
run() {
  local out="$1"; shift
  for _ in 1 2 3 4; do
    $ADAPTY "$@" --app $APP --json > "$out" 2>&1
    grep -q '"NetworkError"' "$out" || return 0
    sleep 3
  done
  echo "Adapty kept failing: $*" >&2; return 1
}

# The CLI wants the builder config with every write: send the current one back unchanged.
run "$TMP/cur.json" flows config get "$ID" || exit 1
python3 -c 'import json,sys; json.dump(json.load(open(sys.argv[1]))["config"], open(sys.argv[2], "w"))' "$TMP/cur.json" "$TMP/cfg.json" || exit 1
run "$TMP/upd.json" flows config update "$ID" --config-file "$TMP/cfg.json" --remote-configs "$RC" || exit 1
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(1 if isinstance(d, dict) and d.get("error") else 0)' "$TMP/upd.json" || { head -c 600 "$TMP/upd.json"; exit 1; }
run "$TMP/pub.json" flows publish "$ID" --yes || exit 1

for _ in $(seq 1 40); do
  st=$($ADAPTY flows get "$ID" --app $APP --json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status"))' 2>/dev/null)
  case "$st" in published|publication_failed) break ;; esac
  sleep 5
done
echo "$NAME: $st"
