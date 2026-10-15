# Backend cutover to the merged tip — 2026-10-07

Production now serves **`f62fc7200725`**, the merged candidate, from the worktree
`/home/ubuntu/projects/globalstrat-plus-candidate-f62f`. It previously served
`f0cf7be47264`, which was two repairs behind the commit the ten-round browser
pass certified.

The frontend was deployed afterwards, in the same session — see
*The frontend* below. Both halves now come from the same tree.

## What changed on the host

| | |
|---|---|
| `globalstrat-backend.service.d/competition-candidate.conf` | `WorkingDirectory` → the `f62f` worktree |
| `globalstrat-narratives.service.d/competition-candidate.conf` | same |
| `globalstrat-deadline-scheduler.service.d/competition-candidate.conf` | same |
| `globalstrat-backend.service.d/release-candidate.conf` | `Environment=GIT_REVISION=f62f…` |
| `globalstrat-narratives.service.d/release-candidate.conf` | same |
| **`/etc/globalstrat-plus.env` line 7** | **`GIT_REVISION=f0cf…` → `f62f…`** |

The previous drop-ins are saved for a one-command revert, and the env file was
copied to `/etc/globalstrat-plus.env.bak-pre-f62f` (root, 0600) before the edit.
The only difference between backup and current file is that one line.

## The trap, written down because it cost a wrong verdict

**`EnvironmentFile=` is applied after `Environment=`, so the env file wins.**
`release-candidate.conf` sets `Environment=GIT_REVISION=…` in a drop-in, and
`systemctl show -p Environment` duly reported the new revision — but the main
unit also carries `EnvironmentFile=-/etc/globalstrat-plus.env`, which systemd
applies last. The drop-in was therefore **inert**: the services restarted running
`f62f` code while advertising `f0cf`.

For about eight minutes production was a deployment whose code and whose claimed
identity disagreed. `check_release_identity` exists precisely to refuse that, and
it would have — but nothing asked it. What closed the question was reading
`/proc/<MainPID>/environ` rather than trusting the unit file.

**So: the revision pin lives in `/etc/globalstrat-plus.env`.** The drop-in is kept
in sync so that neither file contradicts the other, but it is not the thing that
takes effect. A future cutover that edits only the drop-in will silently do
nothing.

A second, smaller trap: `systemctl show -p MainPID` is the way to find these
processes. `pgrep -f gunicorn…` matches the shell running the pgrep, and returned
my own pid — which is how the first verification came back with the main repo's
working directory and an empty revision.

## Nothing was contaminated in the mismatch window

A resolution computed while code and revision disagreed would have written a
false `code_revision` into a manifest, and `ResolutionManifest` is a determinism
boundary. It did not happen:

* `ResolutionManifest` rows created between 05:28 and 05:40 UTC: **0**.
  Production holds 15 manifests, the most recent from 2026-08-28.
* The deadline scheduler fired every minute through the window and reported
  *no rounds due to close* each time.

## Verification after the fix

* `/etc/globalstrat-plus.env` → `GIT_REVISION=f62fc7200725…`
* both live processes: `cwd` in the `f62f` worktree, `GIT_REVISION=f62f…`
* `check_release_identity` → **Release identity verified: f62fc7200725, clean tree**
* `migrate --check` → no unapplied migrations (through `0092`)
* `install_audit_guards --check` → **all append-only guards installed and enabled**
* `verify_audit_chain --json` → **ok**, 1,179 entries, 0 problems, 0 unsealed,
  anchored head equals recomputed head equals current head
* a DB-backed request through the running code: `POST /api/auth/login/` → **401**
  with `login_invalid`, in 0.56 s
* `globalstrat-backend`, `globalstrat-narratives`, deadline timer: all **active**

Artifacts: `post-cutover-check_release_identity.txt`,
`post-cutover-install_audit_guards-check.txt`,
`post-cutover-verify_audit_chain.json`, `post-cutover-live-processes.txt`.

## Why `f62f` and not the branch tip

The branch tip is `caa96c24`. The single commit between it and `f62f` touches
only `handoff_readiness_v2/` and `docs/` — no backend or frontend file. `f62f` is
also the tree the merged-candidate gate was run against, so it is the commit with
evidence behind it.

## The frontend

Built from the main checkout at `447b4569`, whose `frontend/` tree is **identical
to `f62f`** (`git diff f62fc720..HEAD -- frontend/` is empty), and deployed with
`frontend/deploy-frontend.sh --skip-build` so the artifact that shipped is the one
that was verified.

| | |
|---|---|
| Was on the ECS | `main.81b42bcc.js` — the pre-repair bundle from `a0631e5d` |
| Now on the ECS | **`main.615bbd73.js`** + `main.429abf4d.css`, 37 files |
| Rollback | `/var/www/globalstrat-backup-20261007-060022` holds `main.81b42bcc.js` |

Verified before shipping, against the built bundle rather than the source:

* all **48** `trade_finance` Chinese strings are present in the bundle, found in
  their `\uXXXX`-escaped form — a literal search returns 0, which is a property of
  webpack output and not of the catalogue;
* a random sample of 40 Chinese catalogue strings: **40/40** present;
* `en.json` 2,540 keys, `zh-CN.json` 2,534. The six that differ are i18next
  `_one` plural forms (`sa_active_sessions_one`, `of_teams_one`, …). Chinese has no
  singular/plural split, so `_other` alone is correct and these are not gaps.

Verified after shipping:

* origin, bypassing Cloudflare: `index.html` references `main.615bbd73.js`
* public `https://globalstrat.camdani.com/`: same two hashes, and the bundle
  itself returns **200, 2,879,964 bytes**
* the deploy gate ran: `aide-checks` full, and the model-routing guard
  (21 tests, OK)

**Two things the script could not finish, done by hand.** SSH to that host resets
mid-session intermittently. The deploy record did not get written by the script,
and the verification step died on a broken pipe. The record was appended by hand
and reads

    2026-10-07T06:00:35Z rev=447b4569 … bundle=main.615bbd73.js note=record-written-by-hand-ssh-reset

It went in three times before the log was deduplicated: the attempts that
reported *SSH FAILED* had in fact succeeded server-side and then lost the
connection before returning. `/var/www/globalstrat-deploys.log` now holds two
lines, this deploy and the 2026-10-05 one.

**No Cloudflare purge was needed or made.** No `CF_TOKEN` is present on this host,
and none was required: the HTML is served `cf-cache-status: DYNAMIC` and already
carried the new hashes, and the bundle filenames are content-hashed.

A note for anyone testing the public URL: `curl` with its default user agent gets
**200 with a zero-byte body** from Cloudflare. Pass a browser user agent or the
site looks broken when it is not.

## What is still owed

**Gate 4** — the isolated rehearsal heat on this deployment with its own
instructor account. Unstarted, and now the next thing.

**A browser pass on the deployed pair.** The repaired screens were driven in the
bilingual re-drive against a local stack; they have not been driven against this
deployment. That is part of Gate 4 rather than separate from it.

## Revert

*Updated 2026-10-16.* The saved `dropins-before/` copies are gone (they were not
on disk by 2026-10-16, most likely lost from a temporary directory at the
2026-10-10 reboot), and the `globalstrat-plus-candidate-f0cf` worktree was
removed in a cleanup of leftover worktrees. Both are recreatable; `f0cf7be47264`
is on `origin/crv2-release-integration`. The revert is now:

    W=/home/ubuntu/projects/globalstrat-plus-candidate-f0cf
    git -C /home/ubuntu/projects/globalstrat+ worktree add --detach "$W" f0cf7be47264
    for u in globalstrat-backend globalstrat-narratives globalstrat-deadline-scheduler; do
      printf '[Service]\nWorkingDirectory=%s/backend\n' "$W" |
        sudo tee /etc/systemd/system/$u.service.d/competition-candidate.conf >/dev/null
    done
    for u in globalstrat-backend globalstrat-narratives; do
      printf '[Service]\nEnvironment=GIT_REVISION=f0cf7be47264f41c51400c41b113f0237328b0b5\n' |
        sudo tee /etc/systemd/system/$u.service.d/release-candidate.conf >/dev/null
    done
    sudo cp /etc/globalstrat-plus.env.bak-pre-f62f /etc/globalstrat-plus.env
    sudo systemctl daemon-reload
    sudo systemctl restart globalstrat-backend globalstrat-narratives globalstrat-deadline-scheduler

As noted above, the env file is what takes effect; the drop-in only keeps the
two in agreement. Verify with
`/proc/<MainPID>/environ`, not `systemctl show`.

That returns the deployment to `f0cf7be47264`, which is the state the
2026-10-06 Gate 2 pass certified.
