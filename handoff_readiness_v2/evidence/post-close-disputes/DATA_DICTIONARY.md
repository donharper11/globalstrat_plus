# End-run report — data dictionary

What a post-competition report could be built from, read from the code at
`8136fad`. **No reporting feature was built and none is proposed here**; this
names the sources, what survives, who may read them, and — the part worth
reading — what is not captured at all.

Retention below is what the code does, not a policy. Only two things expire:
sessions and backup dumps. Everything else is kept until someone deletes the
database, because nothing deletes it.

## Results and standings

| What | Source | Retention | Visible to | Notes |
|---|---|---|---|---|
| Per-team, per-round financials | `RoundResultFinancials` (`round_result_financials`) → `GET /api/games/{id}/teams/{tid}/results/round/{n}/` | indefinite | own team; instructor for any team in a game they own | the numbers a final standing rests on |
| Performance index | `RoundResultPerformanceIndex` → same endpoint | indefinite | as above | |
| Leaderboard, one round and across rounds | `GET /api/games/{id}/leaderboard/round/{n}/`, `.../leaderboard/history/` | indefinite | any authenticated member of the game | already ordered; a report needs no new ranking |
| Product and market outcomes | `RoundResultProductMarket`, `RoundResultMarketRevenue` | indefinite | instructor; team for its own rows | |
| Narrative prose | `Round.narrative_*`, `NarrativeJob` | indefinite | as the round results | hashed separately from the competitive envelope; never an input to scoring |

## Decisions and their evidence

| What | Source | Retention | Visible to | Notes |
|---|---|---|---|---|
| Submitted decisions | `DecisionSubmission` + per-type rows → `GET /api/games/{id}/instructor/teams/{tid}/decisions/?round={n}` | indefinite | own team; owning instructor | the snapshot, not the history |
| Every accepted save | `DecisionAuditEvent` (`competition_decision_audit_event`) → `audit_events[]` on the same response | indefinite, append-only, trigger-protected, chained | owning instructor | actor, server timestamp, endpoint, request id, payload, payload SHA-256 |
| How a submission reached its state | `submission_origin` on the same response, derived from the audit log | derived | owning instructor | distinguishes `student_locked`, `deadline_locked`, `defaulted_missing`, `draft`, `no_submission` |

## Operator and integrity trail

| What | Source | Retention | Visible to | Notes |
|---|---|---|---|---|
| Operator lifecycle actions and refusals | `OperatorAuditEvent` → `GET /api/games/{id}/instructor/operator-events/`, Operator Log tab | indefinite, append-only, chained | owning instructor | before/after, conflict, written reason, request id; a race is one committed and one rejected row |
| Reads of decisions or audit payloads | `SensitiveReadEvent` → `manage.py who_accessed` | indefinite, append-only, chained | operator via CLI | actor, team read, route, outcome including `denied`, request id |
| Refused cross-cohort attempts | `AuthorizationRefusalEvent` → `manage.py who_attempted` | indefinite, append-only, chained | operator via CLI | actor, game attempted, method, route, endpoint, timestamp, outcome, reason, request id; filter by game, request id, actor, method, route or time range; `--json` for an incident file |
| Resolution manifests | `ResolutionManifest` → `manage.py replay_round --export-only` | indefinite | operator via CLI | input/output hashes, seed, code revision, source tree digest |
| Chain seals | `AuditChainEntry` → `manage.py verify_audit_chain` | indefinite | operator via CLI | covers the decision, operator, sensitive-read and authorization-refusal ledgers, plus completed resolution manifests, and its own entries |
| Pre-resolution dumps | filesystem under `COMPETITION_BACKUP_DIR` | **30 days** (`COMPETITION_BACKUP_RETENTION_DAYS`), pruned only when someone runs `manage_competition_backups --delete-expired` | operator with filesystem access | the only competition evidence with an expiry |

## Participation

| What | Source | Retention | Visible to | Notes |
|---|---|---|---|---|
| Roster and team membership | `Enrollment`, `TeamMember`, `Team` | indefinite | owning instructor | |
| Who was signed in | `UserSession` → `GET /api/games/{id}/instructor/session-readiness/` | **idle after 15 minutes**; rows kept | owning instructor | readiness is a point-in-time answer, not a history |

## What is not captured

These are gaps in the record, not proposals. A report that wants them will find
nothing to read.

1. **Time spent on a decision.** Only accepted saves are recorded. There is no
   draft-edit history, no keystroke or dwell time, no record of a value typed
   and replaced before saving. "Which team deliberated longest" is unanswerable.
2. **Who on a team did what.** `DecisionAuditEvent` records the acting user, so
   individual contribution *is* recoverable per save — but nothing records who
   read a briefing, who was present, or who agreed. Team-internal attribution
   beyond the save actor does not exist.
3. **No browser view of refused cross-cohort attempts.** The rows are
   retrievable — `manage.py who_attempted`, by game, request id, actor, method,
   route or time range (V2-036) — but only from the command line. An instructor
   holding a 403's request id needs an operator to run the query. This entry
   previously called the absence of any reader a "deliberate boundary of that
   repair"; that was wrong, and the audit rejected it: naming a gap is not a
   disposition, and V2-030 had already settled that an audit row the operator
   cannot retrieve does not answer its incident.
4. **Session history.** `UserSession` answers who is signed in now. There is no
   retained connect/disconnect timeline, so "was this team offline during round
   3" cannot be answered after the fact.
5. **Narrative provenance.** Prose is stored, and the model and prompt that
   produced it are not, beyond the job row. A report cannot say which model
   version wrote a briefing.
6. **Client-side errors.** Nothing collects browser console or network failures.
   The CRV2-08 walkthrough captured them only because a driver was attached.
7. **Reads of results.** `SensitiveReadEvent` covers decisions and audit
   payloads by design. Ordinary result and leaderboard reads are not recorded,
   so "who saw the standings first" is unanswerable.

## Two cautions for whoever builds the report

**Round 0 is not a played round.** `setup_test_game` leaves a processed round 0
carrying starter state. Counting processed rounds without excluding it
overstates the competition by one, and its financial rows belong to teams that
may since have been withdrawn.

**A team's row count is not its participation.** Closing a round creates an
empty submission for every team that did not submit, so every team has a row
for every round. `submission_origin` is what separates a team that played from
one that was defaulted at close — the distinction a final report most needs and
the one the raw `status` field hides.
