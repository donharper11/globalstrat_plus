#!/usr/bin/env bash
# Round 6. Photon Labs -- the firm at the top of the table all game -- produces
# nothing. It keeps its performance index and loses its sales, which is the
# one state R32 ranks below every firm that competed. That is the only way to
# put a HIGH score below a LOW one on the leaderboard, which is what W-CE3-15
# is about: the standings contradicting the numbers printed beside them, with
# nothing on the screen to explain it.
set -u
cd "$(dirname "$0")/.."
python3 drive_overproduction.py en 2 6 0

# The round-5 unlocks, verified a round late: round 5's hook file was created
# after that round's play had already passed the hook point. The unlocks stay
# open from round 5 onward, so the third platform generation (W-CE3-14) and
# the customs classification are checked here instead, and the record says so.
python3 verify_round5_unlocks.py en 1 6 > runtime/r5-unlocks-t1-en.log 2>&1
echo "unlocks t1 en exit $?"
python3 verify_round5_unlocks.py zh-CN 3 6 > runtime/r5-unlocks-t3-zh.log 2>&1
echo "unlocks t3 zh exit $?"
