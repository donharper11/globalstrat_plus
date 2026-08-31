# GSP-CRV2-08 — second checkpoint: a new finding needs a ruling

Steps 1–5 of the agreed sequence are done. This is submitted now, before the
data dictionary and evidence archive, because the walkthrough turned up a
disclosure finding wider than CRV2-08's remit and the scope decision is yours.

Revisions: fixture and walkthrough `8554db3`, repairs `45eb83c`, repeat
`ebf40fc`.

## Where CRV2-08 stands

**All six disputes settled.** Five answerable through supported paths, one was
a finding and is repaired.

| # | Dispute | Verdict | Supported path |
|---|---|---|---|
| 1 | Submitted before the deadline | answerable | instructor evidence table: saves with server timestamps, actors, request ids against the round deadline |
| 2 | Recorded decision differs | answerable | same response: per-save payload and SHA-256, so the version in force at lock is identifiable |
| 3 | Rival saw our decisions | answerable | `who_accessed` returns actor, target team, route, outcome, request id — refusals included |
| 4 | Rerun after final | answerable | `replay_round --export-only`: manifest hashes and timestamps |
| 5 | Operator changed something | **was a finding, repaired (V2-030)** | new Operator Log tab and `GET /api/games/{id}/instructor/operator-events/` |
| 6 | Prove the calculation | answerable | replay reproduced round 1 exactly, competitive hash `108c4f0a…`, exit 0 |

**Browser walkthrough**, real Chromium, both roles, one session: students reach
an early and the final report after completion; a rival's raw result URL and
raw decision URL are both refused with 403 in both directions; the instructor
evidence table renders with every required column; the defaulted team-round
reports *why* it is empty (`defaulted_missing`, "Never submitted — defaulted at
close"); copy controls work; the bilingual switch changes the interface. The
pagination boundary is **not reachable** with this fixture — six audit rows
against a page size of eight — and is recorded as not-reachable rather than
claimed.

**Two failures found and repaired, then repeated:**

- **V2-030** — dispute 5 had no operator-facing path. Read-only,
  ownership-scoped endpoint and Operator Log tab added; returns actor,
  timestamp, action, outcome, round, before/after, conflict, reason, request
  id; refusals shown beside successes; writes refused with 405; registered in
  the sensitive-read inventory as an audit-category read. 7 focused tests, plus
  13 disclosure-gate tests still passing.
- **V2-031** — `LanguageSwitcher` used `REACT_APP_API_URL || ''` where
  `api/client.js` uses `|| '/api'`, so the default build PUT to
  `/user/preferences/` and 404ed into a silent catch: the language changed on
  screen and was never stored. Proven in the browser (404 as shipped, 200 under
  `/api`), fixed, re-proven at 200.

Repeat run after repair: 7 of 7 pass, no console errors, no network failures.

## The new finding: V2-032

**Ten instructor GET endpoints answer 200 to an instructor with no connection
to the game.** Evidence: `evidence/post-close-disputes/instructor-ownership-scan.json`.

The probe is a fully unrelated instructor — `crv208_outsider`, owner of a
different course, no link to game 1 — asking for game 1:

```
LEAK 200  /api/games/1/instructor/teams/1/decisions/     <- raw decision payloads,
                                                            payload hashes, actors,
                                                            request ids
LEAK 200  /api/games/1/instructor/dashboard/
LEAK 200  /api/games/1/instructor/briefings/
LEAK 200  /api/games/1/instructor/team-config/
LEAK 200  /api/games/1/instructor/alerts/  (+ /summary/)
LEAK 200  /api/games/1/instructor/research-queries/
LEAK 200  /api/games/1/instructor/event-templates/
LEAK 200  /api/games/1/instructor/sc-panel/
LEAK 200  /api/games/1/instructor/sc-event-catalog/

ok   403  /api/games/1/instructor/operator-events/    (V2-030, this handoff)
ok   403  /api/games/1/instructor/session-readiness/  (V2-007 rework, CRV2-07)
ok   403  /api/games/1/round-control/
```

Only the three endpoints carrying an explicit `instructor_can_access_game`
check refuse. The rest declare `IsInstructor`, which checks the role and
nothing else, so any instructor account reads any cohort by changing the game
id in the URL.

The first one is the same endpoint CRV2-08 certifies as the answer to disputes
1 and 2. Its response is the dispute evidence: submitted payloads, their
SHA-256, the actor and the request id.

**How it was found.** My new endpoint refused the fixture's own instructor,
because the fixture's course belonged to `setup_test_game`'s instructor row
rather than to the fixture instructor. Chasing that 403 showed the neighbouring
endpoints answering 200 to the same non-owner.

**Not proven, and I want to be exact about it.** Only GET was exercised. The
write endpoints — `close`, `process`, `advance`, `reopen`, `deadline`,
`inject-event`, `participation` — answer 405 to GET, so they are **untested,
not safe**. Testing them means issuing lifecycle writes against a cohort as a
non-owner, which mutates state; on a disposable clone that is cheap, but it is
a scope decision rather than mine to take.

This is the third instance of the same class: V2-007's rework and CRV2-07's
authorization FAIL were both `IsInstructor` without an ownership check. That
suggests the rule needs a default rather than another per-endpoint repair.

## Rulings requested

1. **Scope of the V2-032 repair.** Fix all ten inside CRV2-08, or register it
   and hand it to a dedicated handoff? My recommendation is to fix
   `instructor/teams/{id}/decisions/` here, because CRV2-08 certifies it as the
   dispute evidence path and shipping that certification over an open
   cross-cohort read would be wrong, and to hand the remaining nine to their
   own handoff with the write endpoints.
2. **Write endpoints.** Should I exercise lifecycle writes as a non-owner
   against a disposable clone to establish whether the exposure is read-only?
3. **A default instead of repeated repairs.** Worth requiring ownership at the
   permission layer — an `IsGameInstructor` permission class, or a guard
   middleware like `TeamScopeGuardMiddleware` does for students — so a new
   instructor endpoint is scoped unless it opts out with a stated reason?

## What remains in CRV2-08 regardless

Step 6: the data dictionary and the concise evidence archive. Neither depends
on the ruling. Step 7 stays with CRV2-09.

Nothing else is running. I have not started step 6.
