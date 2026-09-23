#!/usr/bin/env bash
# Round 7. The walkthrough-2 residues that need a team to queue and withdraw
# real commitments are driven here, on Prism Tech (team 6) -- a team that
# submits when it can but is not one of the four whose round is being
# balanced, so a queued plant or acquisition cannot quietly change what a
# playing team could afford.
set -u
cd "$(dirname "$0")/.."
python3 verify_plant_collision.py 6 7            > runtime/plant-collision-t6-r7.log 2>&1
echo "plant collision exit $?"
python3 verify_plant_after_acquisition.py 6 7    > runtime/plant-after-acq-t6-r7.log 2>&1
echo "plant after acquisition exit $?"
python3 verify_withdraw.py en 6 7                > runtime/withdraw-t6-r7.log 2>&1
echo "withdraw exit $?"
python3 verify_marketing_refusal.py zh-CN 3 7    > runtime/mktg-refusal-t3-r7.log 2>&1
echo "marketing refusal exit $?"
