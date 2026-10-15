#!/bin/zsh
# DISABLED 2026-10-05: placement pw_main now carries a live A/B test for "All users". The CLI's
# `placements update --audiences` rewrites the WHOLE audience list and knows no A/B-test entries,
# so running this would silently drop the test. Change the "Nikita tester" audience in the
# dashboard instead: Placements -> Paywall main (flow) -> audience "Nikita tester" -> edit flow.
echo "qa_switch.sh is disabled while the pw_main A/B test is live — edit the tester audience in the Adapty dashboard." >&2
exit 1
