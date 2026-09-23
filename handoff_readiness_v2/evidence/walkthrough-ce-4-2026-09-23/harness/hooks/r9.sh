#!/usr/bin/env bash
# Round 9. W-CE3-15 needs a firm with a HIGH performance index and no sales,
# because R32 ranks a commercially inactive firm below every firm that
# competed and that is the only way a high score can appear below a low one.
# Round 6's attempt -- producing nothing -- was not enough: stock built in an
# earlier round still sold. Photon Labs, top of the table all game, now takes
# its products off sale as well, which is what a blank price means on the
# Marketing page.
set -u
cd "$(dirname "$0")/.."
python3 drive_overproduction.py en 2 9 0 blank-price
