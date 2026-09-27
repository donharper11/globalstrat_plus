#!/usr/bin/env bash
# Round 4: after the scale player's deliberate round-3 overproduction, inspect
# and exercise every financing lever from the real student UI. The driver
# resets each probe before the normal blocker/correction pass runs.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 probe_de_ceiling.py en 2 4
