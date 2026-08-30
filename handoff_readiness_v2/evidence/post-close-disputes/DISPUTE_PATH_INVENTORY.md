# GSP-CRV2-08 step 1 — the six disputes and their supported paths

Read from the code at `ba42484`, before any walkthrough. Each row names the
exact supported path a walkthrough must exercise. Two entries are marked
**suspected gap**: they are claims to be tested in the walkthrough, not
findings. Nothing here is asserted as a defect yet.

## Retrieval surfaces

| Purpose | Supported path |
|---|---|
| Round result, one team, one round | `GET /api/games/{game_id}/teams/{team_id}/results/round/{round_number}/` |
| Leaderboard across rounds | `GET /api/games/{game_id}/leaderboard/history/` |
| Financial report history | `GET /api/games/{game_id}/teams/{team_id}/financial-reports/history/` |
| Event history | `GET /api/games/{game_id}/teams/{team_id}/events/history/` |
| Instructor decisions + audit evidence | `GET /api/games/{game_id}/instructor/teams/{team_id}/decisions/?round={n}` |
| Round lifecycle state, deadline, server time | `GET /api/games/{game_id}/round-control/` |

The instructor decisions response carries `audit_events[]` with `action`,
`actor`, `server_timestamp`, `endpoint`, `request_id`, `payload_sha256` and
`payload`, plus `submission_origin`, `locked_at` and `locked_by`
(`results_api.py:1034`). The browser surface is
`components/instructor/AuditEvidenceTable.js`, reached from the instructor
dashboard's team overview.

## Disclosure boundary

`TeamScopeGuardMiddleware` (`middleware.py:210`) refuses any student request
carrying a `team_id` they are not a member of, with 403 and
`{'detail': 'You do not have access to this team.'}`. `TEAM_SCOPE_EXEMPT_PREFIXES`
is empty, so no `/api/` route with a `team_id` is exempt. Instructors and admins
pass through. This matters because most read views inherit DRF's default
`IsAuthenticated` and do not scope by team themselves — `RoundResultsView`
declares no `permission_classes` at all, so the middleware is the only thing
standing between a student and a rival team's results. The walkthrough must
attack it directly rather than trust it.

`SensitiveReadLogMiddleware` (`middleware.py:279`) records every GET of a
team's raw decisions or an audit payload into `SensitiveReadEvent`: actor id
and username, game, team and round read, route, endpoint, status, outcome
(`allowed` / `denied` / `error`) and request id. Route matching comes from
`core.services.read_inventory`, not a hand-kept path list. No response content
is stored.

## The six disputes

| # | Claim | Supported path | Evidence returned |
|---|---|---|---|
| 1 | "We submitted before the deadline" | Instructor → team overview → view decisions, or `GET .../instructor/teams/{id}/decisions/?round={n}` | `audit_events[].server_timestamp` and `action` against the round deadline; `submission_origin`; `request_id`; `payload_sha256` |
| 2 | "The recorded decision differs" | Same response | last accepted `payload` before lock and its `payload_sha256`, against the stored snapshot in the same response |
| 3 | "Another team saw our decisions" | Prevention: the 403 above. Evidence: `python3 manage.py who_accessed` over `SensitiveReadEvent`; Django admin read-only view | actor, team read, route, outcome, request id |
| 4 | "The round was rerun after final" | `python3 manage.py replay_round --game-id {id} --round {n} --export-only`; operator events; recovery-audit JSONL from `recover_competition_round` | manifest timestamps and hashes against the operator trail |
| 5 | "The operator changed something" | **Suspected gap** — `OperatorAuditEvent` has no product API or UI. Only `core/admin.py:811` (read-only Django admin) reads it | before/after, actor, reason, request id — reachable only through Django admin |
| 6 | "Prove the calculation" | `python3 manage.py replay_round` against an isolated database | matching competitive hash; narrative hashed and reported separately |

## Two things to test rather than assume

**Suspected gap A — dispute 5 has no operator-facing path.** No route in
`core/urls.py` returns `OperatorAuditEvent`, and `round_control.py` does not
read it despite what a quick grep of `read_inventory.py`'s comment suggests
(that comment describes the write side, through the `operator_action` context
manager). The only reader is the Django admin, registered `AppendOnlyAdmin`.
Whether that counts as a supported path depends on whether an instructor can
log into Django admin at all — instructors are `core.User` rows with a role,
not `auth_user` staff accounts. The walkthrough will attempt it as an
instructor and record what happens.

**Suspected gap B — the runbook understates dispute 3.** Procedure 3 says to
classify a rival-read claim as "not answerable" if logs do not retain
actor/team. `SensitiveReadEvent` does retain both, and `who_accessed` queries
it. If the walkthrough confirms the command answers the claim, the runbook text
is out of date rather than the product being incapable, and the correction
belongs in the runbook.

## Not in scope for this handoff

The integrated backend/frontend regression suite (CRV2-09), load, concurrency,
determinism and provider drills.
