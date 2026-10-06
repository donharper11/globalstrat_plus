#!/usr/bin/env bash
# Rounds <from>..<to> of walkthrough 4, back to back.
#
#   run_game.sh <from> <to>
#
# The console language and the way each round is resolved are chosen per
# round below, so the record carries every path and both languages. The
# instructor's SERVER language is zh-CN throughout (set once through the
# console's own switch, before round 1 was processed): the console's
# interface language is a browser choice and does not restate it, so every
# round's AI Coach alerts are written in the same language.
set -u
H="$(cd "$(dirname "$0")" && pwd)"
cd "$H"
FROM="$1"; TO="$2"
for n in $(seq "$FROM" "$TO"); do
  case "$n" in
    2) LANG=zh-CN; WAY=console; PROF=probe ;;
    3) LANG=en;    WAY=console; PROF=plain ;;
    4) LANG=zh-CN; WAY=force;   PROF=plain ;;
    5) LANG=zh-CN; WAY=console; PROF=probe ;;
    6) LANG=en;    WAY=console; PROF=plain ;;
    7) LANG=zh-CN; WAY=lifecycle; PROF=plain ;;
    8) LANG=zh-CN; WAY=console; PROF=plain ;;
    9) LANG=en;    WAY=console; PROF=plain ;;
    *) LANG=zh-CN; WAY=console; PROF=plain ;;
  esac
  ./run_round.sh "$n" "$WAY" "$LANG" "$PROF"
done
echo "rounds $FROM..$TO done"
