#!/usr/bin/env bash
# GSP-CRV2-05 evidence run.
#
# Runs the three acceptance commands in order on the pinned runtime, from a
# genuinely empty node_modules, and records the exit code of each. Earlier runs
# in this handoff piped through `tail`, which reports the exit status of `tail`
# — a failed build looked like a passing one until the output was read.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$REPO/frontend/globalstrat-frontend"
OUT="$REPO/handoff_readiness_v2/evidence/frontend-toolchain"
mkdir -p "$OUT"

cd "$APP" || exit 1
export PATH="$HOME/.nvm/versions/node/$(cat .nvmrc | sed 's/^/v/')/bin:$PATH"
export CI=true

status=0
record() {  # record <name> <command...>
  local name="$1"; shift
  local log="$OUT/$name.log"
  echo "\$ $*" > "$log"
  local start; start=$(date +%s)
  "$@" >> "$log" 2>&1
  local code=$?
  local secs=$(( $(date +%s) - start ))
  echo "--> exit ${code} after ${secs}s" >> "$log"
  printf '  %-22s exit %-3s %ss\n' "$name" "$code" "$secs"
  echo "${name} ${code} ${secs}" >> "$OUT/summary.txt"
  [ "$code" -ne 0 ] && status=1
  return 0
}

: > "$OUT/summary.txt"
{
  echo "generated_at   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "revision       $(git -C "$REPO" rev-parse HEAD)"
  echo "tree_clean     $([ -z "$(git -C "$REPO" status --porcelain --untracked-files=no)" ] && echo yes || echo NO)"
  echo "nvmrc          $(cat .nvmrc)"
  echo "node           $(node --version)"
  echo "npm            $(npm --version)"
  echo "system_node    $(/usr/bin/node --version 2>/dev/null || echo none)"
  echo "lockfiles      $(ls package-lock.json yarn.lock pnpm-lock.yaml 2>/dev/null | tr '\n' ' ')"
} > "$OUT/runtime.txt"
cat "$OUT/runtime.txt"
echo

rm -rf node_modules build
record clean-install npm ci --no-audit --no-fund
record jest          npm test -- --watchAll=false
record build         npm run build

# `npm ci` must not rewrite the lockfile; if it did, the lock and the manifest
# disagreed before the run started.
record lockfile-unchanged git -C "$REPO" diff --exit-code -- \
  frontend/globalstrat-frontend/package-lock.json

{
  echo "react-router-dom $(node -p "require('./node_modules/react-router-dom/package.json').version")"
  echo "build artefacts  $(find build -type f | wc -l) files, $(du -sh build | cut -f1)"
  echo "main bundle      $(ls build/static/js/main.*.js 2>/dev/null | head -1)"
} > "$OUT/artefacts.txt"
cat "$OUT/artefacts.txt"

( cd "$OUT" && sha256sum ./*.log ./*.txt > SHA256SUMS )
echo
echo "overall: $([ $status -eq 0 ] && echo PASS || echo FAIL)"
exit $status
