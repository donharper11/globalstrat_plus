# Host reboot, 2026-10-06 22:02:45 UTC — what came back by itself

Nothing here was driven. `ai-react` installed
`linux-image-5.15.0-194-generic` at 06:38 and was running in it at 22:02:45,
having been on 5.15.0-191 since 2026-10-05. **Who or what restarted the host
is not established here** — `unattended-upgrades` is configured *not* to
reboot (`Automatic-Reboot` is commented out, so false) and no
`/var/run/reboot-required` is present now — so the cause is recorded as
unknown rather than guessed. What IS established is the only part this gate
needs: **nothing had to be done by hand afterwards.** It answers a Gate 3
question no drill had yet asked of the competition deployment on its own
host — does the pinned candidate come back without a human? — and it explains
the loss of an earlier walkthrough stack.

## What came back, and when

| 22:02:45 | boot |
| 22:03:05 | `globalstrat-backend.service`, `globalstrat-narratives.service` and the deadline scheduler all started by systemd |
| 22:03:08 | gunicorn listening on `0.0.0.0:8002`, 32 sync workers |
| 22:03:11 | narrative worker `ai-react:927:99a57623` started; deadline scheduler's first run: *no rounds due to close* |
| every minute since | the scheduler runs and reports *no rounds due to close* |

* Both long-running services came back **in the pinned candidate worktree** —
  `/home/ubuntu/projects/globalstrat-plus-candidate-f0cf/backend` read from
  `/proc/<pid>/cwd` — so the systemd drop-ins that redirected them survived the
  reboot (`process-worktrees.txt`).
* **Zero errors, tracebacks, refusals or failures** in either service journal
  or in the scheduler's, from boot to the time of capture.
* The deadline timer is persistent and caught up on boot rather than waiting
  for the next minute boundary.

## What it cost, stated plainly

The previous session's **disposable walkthrough stack and its PostgreSQL
container were not supervised and did not come back.** That stack was mid-round
5 of a ten-round browser pass; rounds 1–4 are on record and round 5's play was
lost. That is the correct outcome for a disposable stack — it is deliberately
not a service — and the ten-round pass was restarted from a fresh database
rather than resumed.

## Still owed to this reboot, and why it is not here

`manage.py verify_audit_chain --json` and `install_audit_guards --check`
against the production database. Both are read-only and both passed earlier the
same day, before the reboot. They need `/etc/globalstrat-plus.env`, which is
`root:root 0600`, so they are the owner's to run — and the VM `sudo`
credential is itself pending rotation (`RECOVERY_CHECKPOINT_2026-10-06.md`).
A reboot does not rewrite sealed rows, and nothing in the journals suggests it
did; this is the confirmation, not the suspicion.

Production was not changed, restarted or reconfigured to produce any of this.
Every file here is a read of state the host arrived at on its own.
