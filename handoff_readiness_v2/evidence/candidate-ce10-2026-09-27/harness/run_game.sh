#!/usr/bin/env bash
# Resolve rounds 1-9 using only normal console close/process/advance controls.
set -euo pipefail
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
for round in $(seq 1 9); do
  lang=en
  case "$round" in 2|4|5|7|8) lang=zh-CN ;; esac
  ./run_round.sh "$round" "$lang"
done
