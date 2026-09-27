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
