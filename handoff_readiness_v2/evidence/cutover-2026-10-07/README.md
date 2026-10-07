# Backend cutover to the merged tip — 2026-10-07

Production now serves **`f62fc7200725`**, the merged candidate, from the worktree
`/home/ubuntu/projects/globalstrat-plus-candidate-f62f`. It previously served
`f0cf7be47264`, which was two repairs behind the commit the ten-round browser
pass certified.

This is the backend only. **The frontend was not deployed in this action** — see
*What is still owed* below.

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

## What is still owed

**The frontend.** The repairs changed `FinancialReportsPage.js`, `FinancePage.js`,
`CorporateStrategyPage.js`, `ReasoningAnalysisTab.js` and both locale catalogues.
Students are served a build from `/var/www/globalstrat/build` on the Alibaba ECS
(`47.86.57.36`), which still carries the pre-repair bundle. Until that is rebuilt
and deployed, **a Chinese student still meets the English strings V2-145 to
V2-148 repaired** — the serving half landed, the rendering half did not. The `f62f`
worktree has no `node_modules` and no `build`, so this is an install, a build and
`frontend/deploy-frontend.sh`, whose `aide-checks` gate refuses a deploy if the
checks do not run.

**Gate 2 for this revision.** The read-only half is above and clean. **Gate 4**
is unstarted: the isolated rehearsal heat on this deployment with its own
instructor account.

## Revert

    sudo cp $S/dropins-before/*.conf back into the two .service.d directories
    sudo cp /etc/globalstrat-plus.env.bak-pre-f62f /etc/globalstrat-plus.env
    sudo systemctl daemon-reload
    sudo systemctl restart globalstrat-backend globalstrat-narratives

That returns the deployment to `f0cf7be47264`, which is the state the
2026-10-06 Gate 2 pass certified.
