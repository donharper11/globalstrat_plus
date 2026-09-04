# V2-048 — credential rotation runbook

Prepared at `29c636d`. **Rotation has not been performed.** Everything that can
be done without root is done; the remaining step is one command.

---

## 1. The blast radius is wider than the finding recorded

The register described a credential committed in this repository. The
credential is also **one shared PostgreSQL role used by three applications
across two repositories**. Confirmed by digest comparison, never by printing:

| Consumer | Where its copy lives | How it runs | Verified |
|---|---|---|---|
| **globalstrat+** | `/etc/globalstrat-plus.env` (root 0600) | `globalstrat-backend.service` | read from the running process environment, `/proc/<pid>/environ` |
| **globalstrat v1** | was a **literal in `~/projects/globalstrat/backend/globalstrat/settings.py:99`** | `check_round_deadlines` cron, every minute | fixed — now `~/.globalstrat-secrets.env` (0600) |
| **BECSR** | `~/projects/BECSR/.becsr-secrets.env` (0600) | `becsr-backend.service` + a 5-minute cron | read from the file |

All three digests match: `ce87835d94b0`. Rotating without all three stops the
other two.

`~/projects/globalstrat` is not a git repository, so its literal was never in
any commit — and was never going to be found by scanning this one.

## 2. The failure mode is silent and delayed

Measured on a disposable role, not assumed:

```
live session before rotation: 1
rotated.
LIVE SESSION AFTER ROTATION: still works -> 1
NEW connection with old password: refused
```

`ALTER ROLE ... PASSWORD` **does not disconnect existing sessions.** A service
that is not restarted keeps serving normally and fails at its next reconnect —
a worker recycle, a connection timeout, or the next cron tick. A rotation can
therefore look successful for hours and then break mid-round.

Every consumer is restarted explicitly. Nothing is left to "pick it up".

## 3. Validated end to end on a disposable role

`gsp_rot_drill` / `gsp_rot_drill_db`, created and destroyed; **16 of 16 steps**,
including rollback and teardown verification. Create, connect, Django boot,
`ALTER ROLE`, old-refused, new-accepted, Django refuses stale, Django boots new,
rollback, rollback-verified, rotated-value-now-dead, drop, and role-is-gone.

Two false starts are recorded rather than tidied away, because both produced
green that meant nothing: the first drill reported four `OK`s from steps whose
setup had already failed (exit codes taken from the wrong command), and a
PostgreSQL 16 rule — `must be able to SET ROLE` — blocked database creation for
reasons unrelated to rotation.

The config rewrite was validated separately against copies of all three files:
only the target key changes, the key set is preserved, and every other secret in
BECSR's file stays byte-identical.

## 4. The remaining step

```sh
sudo bash ops/rotate-db-credential.sh
```

Root is required for two things and nothing else: `/etc/globalstrat-plus.env` is
`root:root 0600`, and the services are systemd-managed. `sudo -l` shows full
sudo for `ubuntu` but **password-required**; the only `NOPASSWD` entry is
start/stop of `becsr-backend`.

The script generates the replacement itself, so the secret never passes through
a transcript. It never prints the value — only 12-character digest prefixes, so
two values can be compared without either being disclosed.

Order, with the reason for it: back up all three configs → `ALTER ROLE` →
write all three configs → restart both services → verify. The window in which
the configs are stale is milliseconds, and services survive it on existing
connections.

**Verification, all of which must pass:** the new credential authenticates; the
old one is **refused**; both services are `active`; and the v1 deadline cron
authenticates as `ubuntu`.

**Rollback is automatic** on any failed step: the role password is restored, all
three configs are restored from their `.pre-<stamp>` copies, and both services
are restarted. The script then exits non-zero and says so.

## 5. Afterwards

- Delete the `*.pre-<stamp>` backups once satisfied.
- The value remains in **14 commits** of this repository's history, behind a
  GitHub remote. **Rotation is what makes that history harmless.** Rewriting it
  is a separate decision with collaboration cost, and step 6 of the recorded
  repair order says to leave history unchanged unless a later decision requires
  otherwise.
- Still outstanding and needing the database host: access-log review, and
  whether the role needs `CREATEROLE`/`CREATEDB` at all. It is not a superuser,
  but `CREATEROLE` is a privilege-escalation path.

## 6. Unrelated finding, noticed while inventorying

`globalstrat-backup-monitor.service` has been **failed since 2026-09-03**:

```
Backup monitor failed: an artifact is not mode 0600.
```

**107 of 131** files in `backend/competition_backups/` are mode `0644` —
competition database dumps readable by any local account. The monitor is
correct to refuse; it has simply been failing unattended, so the integrity and
capacity checks it performs have not run for a day. Not fixed here: changing
backup permissions is an operational action outside this handoff, and the
monitor is the thing that will confirm the fix.
