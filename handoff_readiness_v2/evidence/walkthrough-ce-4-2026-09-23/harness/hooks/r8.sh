#!/usr/bin/env bash
# Round 8. Nova Circuit (team 4) is deliberately left with the round it
# played and no attempt to make it affordable -- `hooks/skip-blocker-r8` --
# so that two things can be seen:
#
#   * what the Decision Summary SAYS to a team that is over-committed
#     (W-CE3-13, W-CE2-09, W-CE-18b), read off the real screen; and
#   * what the DEADLINE does with a draft the lock refused, which is
#     integrator decision 14: the close should apply the lock's own
#     affordability rule rather than executing the draft anyway.
set -u
cd "$(dirname "$0")/.."
python3 probe_summary_wording.py en 4 8    > runtime/wording-t4-r8.log 2>&1
echo "summary wording en exit $?"
python3 probe_summary_wording.py zh-CN 3 8 > runtime/wording-t3-r8.log 2>&1
echo "summary wording zh exit $?"
