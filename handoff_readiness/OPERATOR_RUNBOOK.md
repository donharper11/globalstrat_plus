# Competition operator runbook

This runbook applies to the Phase 2 hardened build. The original Phase 1
findings are retained in `PHASE1_FINDINGS_REGISTER.md`; their current
dispositions and verification are recorded in `FIX_LOG.md`.

## Before the event

- Use only the supported public GlobalStrat URL. Port 8081 is the code-server
  service and is not a competition endpoint.
- Deploy the approved, tagged build and verify that `GIT_REVISION` is populated
  in a newly generated resolution manifest.
- Confirm the approved `BACKUP_RETENTION_POLICY.md`, available storage, monitoring, the
  bilingual announcement channel, maintenance-mode access, and two named
  recovery approvers.
- Complete the launch gates in `LAUNCH_CHECKLIST.md`. Do not treat the automated
  rehearsal as a substitute for the volunteer dry run.

### Admission window — how the cohort signs in

Password verification is deliberately expensive (PBKDF2 at the framework's
default work factor). That cost is per sign-in and is CPU-bound, so a whole
cohort signing in at the same instant is a compute burst that no amount of
extra web workers relieves. Measured on the reference host, 8 cores: 96
simultaneous sign-ins took 26 seconds for the cohort with a median wait of 21
seconds; 288 took 64 seconds with a median wait of 40 seconds and a worst case
of 63.

**The work factor is not to be lowered.** Admission is staged instead.

1. **Open sign-in ten minutes before the first round opens.** Announce the
   admission window explicitly ("sign in any time in the next ten minutes"),
   not a single start time. Spread arrival is the control.

   Ten minutes is the **required** window on the reference 8-core host. Five
   minutes was measured and passed, but by 0.8 ms of p95 margin against a
   2000 ms bar — a lower bound, not a procedure. A slower host, a larger
   cohort or an unlucky arrival cluster consumes that margin entirely.
   **Slower hosts must establish a longer window during preflight**, by
   running the admission profile on the deployment host rather than assuming
   this one's numbers.
2. **Do not gate sign-in behind a countdown, a shared link opened on cue, or
   an instructor "go" message.** Anything that makes 96 people click at the
   same second recreates the burst the window exists to avoid.
3. **A session's token lasts 8 hours** (`JWT_ACCESS_TOKEN_LIFETIME_HOURS`).
   Once admitted, a student does not sign in again for the rest of the
   competition. There is no refresh endpoint and none is needed within that
   span. A competition intended to run longer than 8 hours must plan a
   re-admission window in the same staged way.
4. **Confirm the cohort is in before opening round 1 — using session
   readiness, not the roster.** Open
   `/api/games/{game_id}/instructor/session-readiness/` (or the console view
   that consumes it). It reports two different things and they must not be
   confused:

   - **Roster** — `expected_participants`: who is enrolled. This is
     unchanged by anyone signing in and answers "who is in this class".
   - **Sessions** — `authenticated`, `missing`, `stale`, `duplicate_sessions`:
     who is actually signed in and working now.

   **Open the round when `ready` is true.** It is true only when every
   expected participant holds exactly one usable session. `blocking_reasons`
   names what is outstanding.

   - `missing` — never signed in, or signed in on another cohort. Chase them.
   - `stale` — signed in and then idled out or logged out. They must sign in
     again; their earlier session does not count.
   - `duplicate_sessions` — one person with two browsers or devices. Have them
     close one. Duplicates deliberately block `ready` rather than being
     absorbed, because two sessions for one person could otherwise make a
     cohort look complete while someone is still locked out.

   Do **not** read the dashboard's member list as a sign-in count. It
   enumerates enrolled members and will show the full class whether or not
   anybody has authenticated.
5. **Several sections starting at once.** 288 simultaneous password checks is
   an unsupported arrival shape, not supported capacity. Stagger the sections'
   admission windows — for example three sections at five-minute offsets —
   rather than admitting them together.
6. **If sign-in is slow anyway**, it is a queue and it drains. Tell students to
   wait rather than to reload: a reload abandons a password check that is
   already running and starts another, which lengthens the queue for everyone.

Longer-term alternatives, if simultaneous admission ever becomes a hard
requirement: random high-entropy competition access tokens issued in advance,
or authentication scaled separately from the application. Neither is a reason
to weaken PBKDF2.

### Hard deploy-freeze rule

Do not deploy any code inside the competition window. Recovery rejects a dump
whose manifest revision differs from the running build, so a deploy makes every
earlier round backup unavailable to the normal recovery path. If an emergency
deploy is unavoidable: pause the event, obtain two-operator approval, deploy,
take a fresh backup immediately, restore that backup on an isolated stack, and
do not open the next round until the restore is verified. The guarded
`--allow-code-revision-mismatch` option is break-glass only: it requires an
explicit schema/code compatibility review, maintenance mode, two approvals, and
a retained written reason.

## Before each round

Confirm the game and round, server UTC time, published deadline, roster and
submission counts. Announce the deadline in both languages and verify monitoring
from a second device. Confirm the supported team-removal/deactivation procedure
before play begins; do not improvise by deleting database rows.

The instructor lock is enforced by student write paths. Deadline close and all
identified student write families share the same database coordination boundary;
requests that were waiting when close committed re-read the closed state and are
rejected uniformly. The final rehearsal evidence is in `LOAD_TEST_RESULTS.md`.

## Close and resolve a round

1. Verify the intended game and round and record the operator reason.
2. Close the round once. Missing submissions are materialised uniformly and
   recorded as `missing_submission_defaulted` audit events.
3. Verify the locked count and investigate any discrepancy before processing.
4. Process once. Resolution creates and verifies a pre-mutation database dump,
   then records the seed, canonical input and output hashes, code revision slot,
   backup path and completion time in the resolution manifest.
5. Verify results and the operator audit record before publishing.

Two simultaneous resolution attempts cannot both run: the rehearsal recorded
one completion and one already-processed rejection. This is a guardrail, not a
reason to issue duplicate process requests deliberately.

## Team disputes a decision or result

Freeze further lifecycle actions for the affected round. Record the game, team,
round, user, reported time, request ID and screenshots. Preserve application,
access and database logs and the pre-resolution snapshot.

Compare the append-only submission audit payload/hash, actor, timestamp, endpoint
and request ID with the resolution input manifest, stored seed and output
manifest. Do not overwrite a disputed submission. If a correction is authorized,
use the logged correction workflow with a substantive reason and retain the
written ruling.

## Submission appears lost

### Dispute-response procedures (operator UI only)

1. **“We submitted before the deadline.”** Open Instructor → Team Overview →
   View decisions, select the disputed round, and read the audit-evidence table.
   Compare its server timestamp and action with the round deadline and
   `submission_origin`. Copy the request ID and payload hash into the incident.
2. **“The recorded decision differs.”** In the same table, copy the last
   accepted payload before lock and compare its SHA-256 and fields with the
   stored snapshot. Do not rely on a browser screenshot alone.
3. **“Another team saw our decisions.”** Preserve the request ID and gateway
   access log. The decision ledger proves writes, not reads; search team-scoped
   reads by actor. If logs do not retain actor/team, classify this as not
   answerable and escalate—absence of a write is not proof of absence of a read.
4. **“The round was rerun after final.”** Compare manifest timestamps/hash with
   operator events and recovery-audit JSONL. Require one original process or an
   explicitly approved recovery trail.
5. **“The operator changed something.”** Review operator events in timestamp
   order; compare before/after, actor, reason and request ID.
6. **“Prove the calculation.”** Use `manage.py replay_round` — see *Prove a
   round by replaying it* below. A matching competitive hash proves the
   published outputs and the state carried into the next round; it does not
   cover narrative wording, which is hashed and reported separately.

Do not reconstruct it from memory. Check gateway and application logs for the
request ID and response, then inspect the append-only decision audit ledger. If
the server acknowledged an accepted version before the deadline, use that exact
version through the logged correction workflow. If no accepted version exists,
apply the published missing-submission rule uniformly.

## Two operators act at once

Every lifecycle action — close, reopen, deadline, process, advance, event
injection, correction unlock, team withdrawal — serialises on one boundary per
game and re-reads the round after acquiring it. Concurrent actions cannot
interleave; one wins and the other is told.

Read the status code as an instruction:

- **409 Conflict** — refresh and look again. Another operator, or the deadline
  scheduler, already did this or moved the round past it. The response body
  carries `guidance` saying so. Nothing you retype will change it; if the round
  now needs a different action, take that one.
- **400 Bad Request** — do something else first, or fix the request. "Close the
  round first", "that team is not locked", "a reason is required".
- **200** — it happened. The response carries a `request_id`; that is the
  operator audit row for what you just did.

Every attempt is recorded, including refusals. To see a race after the fact,
read the operator audit events for the round: a race shows as exactly one row
with `outcome='committed'` and one with `outcome='rejected'`, the rejected one
carrying an empty `after` and the conflict that caused it. Two committed rows
for the same action on the same round is a defect — escalate it.

An override (`force=true`, a correction unlock, a team withdrawal) is refused
without a written reason of at least ten characters, and the reason is stored
on the audit row. Do not work around this; the reason is the record of why the
override was correct.

## Prove a round by replaying it

Use this when a team disputes a result, or as a routine post-round check. It
never touches the live database: every step below runs against an isolated
database whose `DB_NAME` points at a disposable copy.

1. **Export the recorded manifest first, from the live stack.** Do this before
   any restore, because the restore overwrites the row that holds it.

   ```bash
   python3 manage.py replay_round --game-id <id> --round <n> --export-only \
     --evidence-dir <evidence>/<incident>/recorded
   ```

2. **Replay against the isolated database.** `--restore` drops and rebuilds the
   target schema from the pre-resolution backup, so confirm `DB_NAME` is the
   disposable one before running it.

   ```bash
   DB_NAME=<disposable> COMPETITION_RECOVERY_ENABLED=true \
   python3 manage.py replay_round --game-id <id> --round <n> \
     --restore --confirm REPLAY-GAME-<id>-ROUND-<n> \
     --expected-manifest <evidence>/<incident>/recorded/expected-manifest.json \
     --evidence-dir <evidence>/<incident>/replay --wait-narrative 150
   ```

3. **Read the exit code.**
   - `0` — the input verified and the competitive hash matched. The round is
     reproduced exactly. A differing narrative hash is reported but is not a
     mismatch: Phase-2 prose is outside the competitive envelope by design.
   - `2` — **the input did not verify and the engine was not run.** The restored
     state is not what resolution was given. The console names the differing
     sections and rows; the full diff is in `input-verification.json`. Treat
     this as a tampering or restore-integrity incident, not a scoring defect.
   - `3` — the input verified but the competitive hash differs. This is a
     genuine reproducibility failure. Preserve `replay-report.json`, stop
     further lifecycle actions on the round, and escalate.

4. **Retain** the evidence directory with the incident record: it holds the
   recorded manifest, the input verification, the per-section diffs, both hash
   sets, and the environment fingerprint of the machine that replayed.

Add `--verify-only` to check a restored database without running the engine.
Old rounds resolved under manifest schema version 1 are refused rather than
silently compared — their envelope is narrower and their hashes are not
comparable.

## Resolution fails or a scoring defect is confirmed

Stop application workers, schedulers and other database writers and keep the
application in maintenance mode. Preserve logs and database state. Follow
`RECOVERY_RUNBOOK.md`; first execute its guarded dry run, then perform the
approved restore/re-run with two-operator sign-off.

The recovery control validates the manifest, dump path and SHA-256 and requires
maintenance enablement, an instructor/admin identity, a substantive reason and
an exact confirmation token. Do not substitute manual SQL or an unrecorded
process retry.

### A round refuses to resolve: duplicate product name

This is the one resolution failure with no operator-facing control, so it is
the one exception to the "do not substitute manual SQL" rule above. Apply it
only for this symptom, and record it exactly as any other recovery.

**Symptom.** Resolving the round fails immediately and repeatedly with
`SnapshotError: Natural key ... is not unique`, naming either
`decision_product_create` or `team_product`. The round stays `open`, no
results are written, and retrying produces the identical error. A student
caused this with a decision the API accepted normally: two new products given
the same name, or one new product reusing the name of a product the team
already owns. Nothing warned them and nothing warned you.

**What is and is not at risk.** Nothing is corrupted. When the collision is on
`team_product` the failure comes from `complete_manifest`, which runs inside
the same transaction as Phase 1, so the whole resolution rolls back and no
duplicate is ever stored. The round is stalled, not damaged, and no team's
decisions are lost.

**Find it.** Substitute the round's `id` (not its round number):

```sql
-- Two creates sharing a name inside one submission
SELECT d.id, s.team_id, d.product_name, count(*) OVER (PARTITION BY d.submission_id, d.product_name) AS copies
  FROM decision_product_create d
  JOIN decision_submission s ON s.id = d.submission_id
 WHERE s.round_id = :round_id
 ORDER BY copies DESC, d.id;

-- A create reusing the name of a product the team already owns
SELECT d.id, s.team_id, d.product_name
  FROM decision_product_create d
  JOIN decision_submission s ON s.id = d.submission_id
  JOIN team_product p ON p.team_id = s.team_id AND p.name = d.product_name
 WHERE s.round_id = :round_id;
```

**Clear it.** Delete the surplus decision row by `id` — the second of the two
copies, or the create that collides with an existing product. Tell the team
what was removed and why, before results are published. Then resolve the round
again; it proceeds normally.

**Do not** rename rows in `team_product` to work around it. The team's own
product names are their record of what they built, and renaming one changes a
result the team can see.

## Platform unreachable at deadline

Record monitoring timestamps and outage scope. Announce a competition-wide
pause through the predeclared channel. Do not accept decisions by ad-hoc email or
chat. When service is stable, extend the deadline equally for all teams by at
least the outage duration plus the published recovery buffer, record actor and
reason, and announce the new UTC and local deadline in both languages.

## Evidence to retain

Retain and dispose of all competition evidence according to
`BACKUP_RETENTION_POLICY.md`, including its dispute-hold rule. Restrict recovery
artifacts because a full database dump can contain credentials and participant
data.
