# GSP-CRV2-08 — checkpoint before the walkthrough

**Not a completion report.** Steps 1 and 2 of the agreed sequence are done;
steps 3–6 all consume the fixture described here. If the fixture or the two
scope decisions in it are wrong, the walkthrough, the repairs, the repeats and
the data dictionary are all built on the wrong thing, so this is submitted
before that work rather than after it.

Four rulings are requested at the end. Everything else is reported for the
record.

## Step 1 — the six disputes and their supported paths

Committed at `ed18651`, full detail in
`evidence/post-close-disputes/DISPUTE_PATH_INVENTORY.md`. Read from the code
before any walkthrough, so the walkthrough tests claims rather than confirming
impressions.

| # | Claim | Supported path |
|---|---|---|
| 1 | Submitted before the deadline | `GET /api/games/{id}/instructor/teams/{id}/decisions/?round={n}` → `audit_events[]`; instructor dashboard → team overview → view decisions (`AuditEvidenceTable.js`) |
| 2 | The recorded decision differs | same response: last accepted `payload` and `payload_sha256` before lock, against the stored snapshot |
| 3 | Another team saw our decisions | prevention: `TeamScopeGuardMiddleware` 403. evidence: `manage.py who_accessed` over `SensitiveReadEvent` |
| 4 | The round was rerun after final | `manage.py replay_round --export-only`, operator events, recovery-audit JSONL |
| 5 | The operator changed something | **suspected gap** — `OperatorAuditEvent` has no product API or UI; only the read-only Django admin reads it |
| 6 | Prove the calculation | `manage.py replay_round` against an isolated database |

Two items are recorded as **suspected**, to be settled by the walkthrough:

- **Dispute 5 may have no operator-facing path.** No route in `core/urls.py`
  returns `OperatorAuditEvent`. Instructors are `core.User` rows with a role,
  not `auth_user` staff accounts, so whether they can reach the Django admin at
  all is an open question the walkthrough will answer.
- **The runbook may understate dispute 3.** Its procedure says to classify a
  rival-read claim as "not answerable" if logs do not retain actor and team.
  `SensitiveReadEvent` retains both and `who_accessed` queries it. If that
  works, the runbook text is stale rather than the product incapable.

## Step 2 — the reusable completed game

`evidence/post-close-disputes/completed-game.json`, built by
`harness/build_completed_game.py`.

Every student save, every lock and every lifecycle action is driven through the
supported HTTP endpoints. An audit trail written by the seeder would prove
nothing about what the product records, which is the entire claim this handoff
rests on.

**Contents, verified by the seeder itself before it writes the file:**

- game status `completed`, three active teams, rounds 1–3 processed
- one team-round classified `defaulted_missing` — a team that never submitted
- three team-rounds saved twice with differing payload hashes, so dispute 2 has
  two versions to compare
- one save refused with 403 after the deadline was moved into the past
- operator `set_deadline`, `close`, `process` and `advance` actions per round

The seeder refuses to write the file if the game is not completed, if no
team-round is `defaulted_missing`, or if no submission was saved twice with
differing hashes. An earlier run produced a "completed game" in which every lock
had been refused and every later stage would have measured defaults; that is the
failure this check exists to stop.

## Two scope decisions requiring a ruling

**(a) The fixture scenario is shortened to three rounds.** A game reaches status
`completed` only by advancing past its scenario's final round
(`advance_round.py:310`), and the stock scenario has ten. Rather than play ten
rounds or set the status by hand, the fixture's scenario is set to three rounds
so the real completion transition fires. The alternative readings are a
ten-round playthrough, or a game left `active` with three processed rounds.

**(b) Non-budget decision rows are written directly, not through the API.** The
budget saves go through the decision endpoints because they are the evidence the
disputes are answered from — the audit rows, their payload hashes, their server
timestamps. The rest of a valid submission (product portfolio, marketing mix per
active product-market pair, strategy decision, mandatory communications) is
written with the ORM so the lock endpoint has something complete to judge. The
lock itself is always the product's own decision.

## Two incidents worth recording

**A pre-existing server on port 8002 nearly corrupted the evidence.** The
walkthrough stack was first configured on fixed ports 8002/8003. Port 8002
already carries a gunicorn serving the real `globalstrat_plus` database. My
backend failed to bind, died, and my requests fell through to that server. A
login failure exposed it. Had a fixture username collided with a live one, the
walkthrough would have read production while reporting on the fixture. The stack
now claims free ports at run time and refuses to start unless a fixture identity
authenticates through the app origin. Nothing belonging to the running service
was stopped or altered.

**The manifest backstop fired unprompted.** An early fixture reused one product
name every round, which stalled a round on the `team_product` natural key —
V2-029's second variant arriving through the ORM, where the new write-path
validation cannot reach. Unplanned, but it is independent evidence that the
backstop still holds, matching what
`test_the_manifest_still_refuses_rows_inserted_outside_the_api` asserts.

## Environment for step 3

Chromium and `puppeteer-core` are available, so the walkthrough can be a real
browser session with console and network capture rather than API calls
described as one. `puppeteer-core` is installed in a scratch directory; the
project's `package.json` is untouched. The frontend production build compiles,
and is served on one origin with `/api` proxied to the backend, so no CORS
configuration exists that would not exist in deployment.

## Rulings requested

1. **Fixture accepted?** Three teams, three rounds, completed, with the contents
   listed above.
2. **Scope decision (a)** — shortening the fixture scenario to three rounds so
   the real completion transition fires. Accept, or require a different route to
   a completed game?
3. **Scope decision (b)** — non-budget decision rows written with the ORM while
   every save, lock and lifecycle action goes through the API. Accept, or
   require the full submission through the API?
4. **Does the Django admin count as a supported operator path?** This decides
   whether dispute 5 is answerable-but-awkward or a finding, and whether dispute
   3's evidence path is acceptable as a management command. I will test and
   report either way, but the classification is yours.

No repair has been made and no walkthrough has been run. Nothing in the product
has been changed by this handoff so far; the only committed changes are the
inventory, the harness and the fixture.
