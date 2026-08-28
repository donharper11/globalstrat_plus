#!/usr/bin/env bash
# Does the built bundle actually run in a browser?
#
# Jest exercises the source in jsdom. That leaves the artefact users are served
# verified only by the fact that it compiled, and a bundle can compile and still
# fail to boot. This serves `build/` and asks a real headless chromium to render
# `/login`, then checks the DOM it returns.
#
# Deliberately a shell one-liner around chromium rather than a browser-driver
# script. The chromium here is a snap: it refuses a `--user-data-dir` outside
# its own confinement, and it hangs rather than failing under several ordinary
# flag combinations. No automation library is installed, and adding one to this
# project's dependency tree is not what V2-009 is about. GSP-CRV2-08 owns
# browser proof and should stand up a real driver.
#
# Scope: no backend runs, so this covers the bundle booting, React mounting and
# the router resolving a route. It does not cover the student journey or the
# instructor audit-evidence screen.
set -u
APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/../frontend/globalstrat-frontend" && pwd)"
OUT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/evidence/frontend-toolchain"
PORT="${PORT:-8734}"
CHROME=/snap/bin/chromium

[ -f "$APP/build/index.html" ] || { echo "No build at $APP/build" >&2; exit 2; }
mkdir -p "$OUT"

( cd "$APP/build" && python3 -m http.server "$PORT" >/dev/null 2>&1 & echo $! > /tmp/gsp-render-check.pid )
sleep 2
dom=$(timeout 90 "$CHROME" --headless --no-sandbox --disable-gpu \
        --virtual-time-budget=15000 --dump-dom \
        "http://127.0.0.1:$PORT/index.html" 2>/dev/null)
kill "$(cat /tmp/gsp-render-check.pid)" 2>/dev/null
rm -f /tmp/gsp-render-check.pid

bytes=${#dom}
mounted=$(printf '%s' "$dom" | grep -c 'id="root"')
login=$(printf '%s' "$dom" | grep -c 'id="username"')
antd=$(printf '%s' "$dom" | grep -c 'ant-')

{
  echo "Built-bundle render check"
  echo "========================="
  echo
  echo "chromium   $CHROME ($("$CHROME" --version 2>/dev/null | tail -1))"
  echo "served     $APP/build"
  echo "url        http://127.0.0.1:$PORT/index.html"
  echo "dom bytes  $bytes"
  echo
  echo "  root element present         $([ "$mounted" -gt 0 ] && echo ok || echo BAD)"
  echo "  antd rendered into the DOM   $([ "$antd" -gt 0 ] && echo ok || echo BAD)"
  echo "  login screen at the default route $([ "$login" -gt 0 ] && echo ok || echo BAD)"
  echo
  echo "Scope: no backend, so API calls fail by design and are not checked."
  echo "The student journey and the instructor audit-evidence screen need a"
  echo "seeded backend; they are GSP-CRV2-08's browser proof, not this."
  echo
  if [ "$bytes" -gt 10000 ] && [ "$mounted" -gt 0 ] && [ "$antd" -gt 0 ] && [ "$login" -gt 0 ]; then
    echo "overall: PASS"
  else
    echo "overall: FAIL"
  fi
} > "$OUT/bundle-render-check.txt"
cat "$OUT/bundle-render-check.txt"
grep -q "overall: PASS" "$OUT/bundle-render-check.txt"
