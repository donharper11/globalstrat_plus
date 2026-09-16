# GSP-CRV2-08 — rulings on the fixture checkpoint

**Issued 2026-08-31 by the product owner**, answering the four rulings requested
at the end of `GSP-CRV2-08_FIXTURE_CHECKPOINT.md`. Steps 3–6 were blocked on
these. They are unblocked.

## 1. Fixture — accepted

Three teams, three processed rounds, completed status, with repeated saves, a
missing-submission default, a deadline refusal and operator actions. That set is
sufficient. Proceed on it; do not enlarge it.

## 2. Three-round scenario — accepted

Shortening the disposable fixture scenario to three rounds is valid **because it
exercises the real completion transition**. That is the whole reason it is
accepted, and it is also the constraint: do not hand-set completion status, and
do not run ten rounds to reach a transition three will reach.

## 3. ORM scaffolding — accepted, with the boundary stated

Non-budget decision rows may be created through the ORM to make the fixture
playable.

**The boundary: evidence for a dispute must come from supported API or UI
actions.** An ORM-written row cannot be presented as proof of audit capture —
it never traversed the write path whose capture is the thing being proved. Where
a dispute answer depends on a row's audit trail, that row is created through the
product, not the ORM. Scaffolding makes the game playable; it does not make the
argument.

## 4. Django admin — does not count

The Django admin is **not** a supported operator surface. It requires a separate
staff identity that competition instructors do not have and will not be issued.

Consequences, in order:

1. **Dispute 5 is a finding.** If the only way to answer "the operator changed
   something" was the admin, then it could not be answered, and the checkpoint's
   suspected gap A is confirmed rather than dismissed.
2. Add an **ownership-scoped, read-only instructor API/UI path** for
   `OperatorAuditEvent`.
3. Verify the failed path with focused automated tests.
4. **Repeat only dispute 5.** Do not replay the five disputes that passed and do
   not rebuild the completed game.

The same test applies to dispute 3's evidence path: a management command is not
an instructor surface either. If `who_accessed` is the only route, say so as a
finding rather than as an answer, and let the owner decide whether it needs a
product path too.

### Status against ruling 4 at `45eb83c`

Most of this was anticipated correctly before the ruling landed, and that work
stands:

| Requirement | State at `45eb83c` |
|---|---|
| Dispute 5 raised as a finding | Done — **V2-030**, described in the commit message |
| Ownership-scoped | Done — `instructor_can_access_game`, 403 otherwise |
| Read-only | Done — `GET` only, no write of any kind |
| Instructor API **and** UI | Done — `GET /api/games/{id}/instructor/operator-events/` and an Operator Log tab |
| Focused tests | Done — `core/tests/test_operator_events_view.py`, 7 tests |
| Registered as a sensitive read | Done — reading operator evidence is itself recorded |

Returning refusals beside committed actions is the right call and worth keeping:
a race is one committed row and one rejected row, and an endpoint returning only
successes hides the half being asked about.

**What ruling 4 still leaves outstanding:**

- **V2-030 and V2-031 are not in `V2_FINDINGS_REGISTER.md`.** They exist only in
  a commit message. The standing rule is that findings are logged before they
  are repaired; these were repaired first. Register both, with reproduction and
  the closure entry, before the completion report.
- **Dispute 5 has not been repeated.** `DISPUTE_PATH_INVENTORY.md:58` still
  reads "suspected gap A — dispute 5 has no operator-facing path." Re-run that
  one dispute through the new path and record the answer.

V2-031 (the `LanguageSwitcher` URL defaulting to `''` instead of `'/api'`, so a
language preference 404ed into a silent catch and never persisted) is also handed
forward to **GSP-CRV2-12**, which sweeps player-facing language and now takes
CRV2-08's completion report as an input rather than rediscovering its strings.

## Note on what happens after this handoff

`RULES_AND_CALIBRATION_ASSESSMENT.md` and handoffs **GSP-CRV2-10 through 13**
were authored while this handoff was in flight. They are gated on CRV2-08
clearing its audit — they mutate the candidate this handoff is generating
evidence against, and a runtime change after evidence starts invalidates that
evidence.

One item is owed **to** this handoff rather than by it. GSP-CRV2-10 introduces a
price band whose deadline behaviour auto-adjusts an out-of-band price, so the
stored price will legitimately differ from what a team typed. That is a new
instance of **dispute 2 — "our decision was recorded differently from what we
entered"** — and it arrives after this handoff has frozen its dispute inventory.
CRV2-10 owes this handoff's owner a written delta and one re-verification of
that case. It does not invalidate anything proved here.
