# GSP-CRV2-07 authentication readiness — REWORK 2

## Decision

**FAIL / REWORK**

Revision audited: `d252eb2`

The session-readiness contract and the bounded three-user walkthrough are otherwise suitable, but the new endpoint exposes cohort authentication state across instructor boundaries.

## Blocking defect: instructor role is treated as game authorization

`InstructorSessionReadinessView` declares `permission_classes = [IsInstructor]`, fetches any supplied `game_id`, and immediately returns `readiness(game, cohort)`. It does not call the existing `instructor_can_access_game(request, game)` ownership check used by other instructor endpoints.

The response contains participant identifiers/names, team membership, and whether sessions are active, missing, stale, logged out, or duplicated. An instructor for one course can therefore enumerate this information for another instructor's game by changing the URL game ID.

The focused endpoint test reinforces the defect: `test_the_endpoint_returns_the_same_contract` creates an instructor with no ownership/course relationship to the game and expects HTTP 200.

## Required correction

1. After resolving the game, enforce `instructor_can_access_game(request, game)` before calling `readiness()`.
2. Preserve the established unowned-course/pilot behavior already encoded by that helper; do not invent a second ownership rule.
3. Replace the permissive endpoint fixture with explicit authorization cases:
   - the instructor who owns/can access the game receives 200 and the readiness contract;
   - an instructor associated only with another owned course/game receives 403;
   - a student remains 403;
   - if the existing helper deliberately permits an unowned pilot course, pin that behavior in one focused test.
4. Confirm a refused foreign-game request does not disclose the readiness body.

## Proportionate verification budget

Run only:

- the focused session-readiness test module;
- the existing focused tests for `instructor_can_access_game`, if they are separate and directly affected;
- route/read-inventory static check if the correction changes either inventory;
- `git diff --check` and the existing evidence checksum verification.

Do **not** rerun the 96-user authentication drive, field/margin load profiles, concurrency/determinism matrices, recovery drills, deploy/restore walkthrough, or full backend suite. The existing seven-stage walkthrough measures session semantics and need not be regenerated unless its instructor fixture cannot be made legitimately authorized without changing the recorded scenario.

## Resubmission

Return the repair revision, changed files, focused test results, ownership cases proven, clean-tree status, and checksum result. Keep CRV2-07 marked incomplete: the five failure injections and deploy/restore walkthrough remain outstanding.
