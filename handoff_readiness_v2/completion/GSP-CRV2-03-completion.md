# GSP-CRV2-03 completion report — durable Phase-2 narrative execution

**Findings closed:** V2-006 (P1), V2-015 (P1), V2-016 (P1)
**Current frozen revision:** `49d6514b9b9723e8d4e6244bb58236a89a3551d6`
**Current source tree digest:** `0c284a835d41f1a6b1ab0e1ea76b8e20cfe1e0032c13a6def75fd3e9f651003b`
**Branch:** `crv2-03-durable-narratives`, on the GSP-CRV2-02 baseline `7272a2f`

> **Superseded in part.** The body below describes the first submission, frozen
> at `ef01237`, and is kept as written. Two of its statements no longer hold:
> V2-016 was left for the rules owner, and the coherence blend was a
> default-off setting. The audit rejected both. See the **rework addendum** at
> the end for the current disposition; where the two disagree, the addendum is
> authoritative.

## What Phase 1 found before any code was written

The protocol's inventory-first rule earned its place here. Cross-referencing
every narrative producer against the *certified manifest envelope* — rather
than reading the narrative code on its own — showed that three of six write
into rows the competitive hash covers, **after** that hash is taken:

| Producer | Writes | Status before |
|---|---|---|
| `coherence_rag` | `RoundResultCoherence.rag_score`, `.blended_score`, `.breakdown` | all fields hashed |
| `sc_event` | `SCEventInstance.resolution_data['narrative']` | field hashed, and shared with the engine's fire/applied flags |
| `coaching` | new `InstructorAlert` rows | row creation hashed |

The hash itself never moved, which is exactly why every GSP-CRV2-01 replay
matched: both the original and the replay hash at Phase-1 commit, before Phase
2 runs. What diverges is **the stored database from the manifest that certified
it** — something no replay compares. Logged as **V2-015** before repair, then
demonstrated by a failing test rather than asserted.

Worse, `blended_score` is read by `core/services/grading.py`. With an LLM
reachable, coherence is `0.6·formula + 0.4·RAG`; without one, the formula score
stands. Two identical competitions grade differently depending on an external
service. Logged as **V2-016**. Rank is unaffected — neither `performance.py`
nor `leaderboard.py` reads coherence — so it is a grading defect, not a ranking
one.

## The deliverable

**Enqueued in the Phase-1 transaction.** Six `NarrativeJob` rows commit with
the numbers. There is no window where a round is resolved and nothing records
that its narratives are owed.

**Claimed as a lease, not a lock.** `SELECT … FOR UPDATE SKIP LOCKED` under a
300 s lease that must exceed the LLM timeout. Several workers run without
coordinating; a worker that dies leaves a lease to expire and the next one
reclaims the job. Nothing has to notice the death — which is the whole of
V2-006.

**Bounded and visible.** Attempts increment; at `max_attempts` the job is
`failed`, terminal and reportable. `retry_narrative_jobs` requeues without
re-running scoring, and the manifest is untouched.

**Idempotent.** Identity is `(round, narrative_type, template_version)` and
every producer writes through `update_or_create` on a natural key, so a retry
overwrites its own rows rather than adding a second briefing.

**The thread is now a convenience.** A single-process deployment still gets
narratives promptly, through the same durable path, but if the thread never
starts the rows are still there.

## Repairs to the isolation defects

* **SC-event prose** moved to its own column, leaving `resolution_data` for the
  `pending`/`applied` flags the engine reads. A data migration moves existing
  text and is reversible.
* **Coaching alerts** gained `InstructorAlert.source`, and the manifest now
  splits engine alerts (hashed) from narrative alerts (not), using a new
  optional per-section filter.
* **The coherence blend** is gated behind `COMPETITION_RAG_AFFECTS_COHERENCE`,
  **off** by default, with the RAG evaluation recorded as instructor commentary
  beside the score instead. Turning it on restores both defects knowingly and
  is a rules decision, not an operational one.
  **— Superseded at `49d6514`:** the audit rejected a default-off switch, the
  write path was removed outright, and setting the flag now stops resolution.
  See the rework addendum.

## Certification

Actual order, from the frozen commit:

| # | Command | Duration | Result |
|---:|---|---:|---|
| 1 | `dump_route_inventory --check` | <5 s | current |
| 2 | `dump_manifest_schema --check` | <5 s | current |
| 3 | `makemigrations --check --dry-run` | <10 s | no changes |
| 4 | restart drill (SIGKILL mid-job) | 67 s | PASSED |
| 5 | provider drill ×3 (unreachable / no key / live model) | 13 + 13 + 60 s | all passed |
| 6 | `manage.py test core` | **199 s** | **387 tests OK** |
| 7 | `MANIFEST.sha256` + `git diff --check` | <5 s | 7 files verify, clean |

Development used focused tests only; no release-scale run was used to explore.

### The first certification attempt failed

Reported because it explains the freeze commits. The run at `463496b` failed
three pre-existing CC-17 tests still asserting the old SC-narrative location,
and tracing their consumers found the supply-chain panel reading
`resolution_data.narrative` too. Per the protocol I stopped before finishing,
fixed the tests, the frontend and a data migration for existing rows, re-froze
at `ef01237`, and certified once from there. An earlier freeze (`ab1bccd`) was
also superseded when the drills exposed the `degraded` gap — a real failed
freeze candidate, which is the exemption the budget allows.

## Preflight checklist

| Question | Answer |
|---|---|
| Did inventory start from authoritative registries? | Yes — the Phase-2 call graph and the certified manifest envelope, not the narrative code alone. It is what found V2-015. |
| Is there an active legacy or alternate entry point? | The daemon thread remains, but it drains through the same durable path and cannot double-run a job. |
| Does a failure/refusal audit survive rollback? | Job rows are the record; a failed job is a committed row, not an in-memory flag. |
| Is each correlation ID generated once? | Not applicable; jobs are identified by `(round, type, version)`. |
| Is background work delayed until the outer transaction commits? | Yes — enqueue is in the transaction, dispatch is on `transaction.on_commit`. |
| Do claimed environment values describe the executing process? | Yes — each drill records the revision and digest it read at run time. |
| Does provenance identify runtime bytes? | Yes — `build_identity()`, recorded in every evidence file. |
| Do README commands run as written? | Yes; the reproduce block was run as written. |
| Do P0/P1/P2 labels match their definitions? | V2-006 P1 (degrades); V2-015 and V2-016 P1 — both can change a stored or graded artifact, neither blocks. |
| Does each negative test prove mutation did not occur? | Yes — every drill and isolation test compares the competitive hash either side, and the restart drill refuses to pass if the kill left no orphaned claim. |

## Unresolved risks

1. **V2-016 needs a rules decision.**
   **— Withdrawn at `49d6514`:** V2-016 is closed. Published coherence and the
   grades derived from it are the deterministic formula score; retrieval is
   commentary. Nothing is outstanding for the rules owner. The original text
   follows as written.
   Default is now the deterministic formula
   score. If the competition wants the RAG blend, it belongs inside Phase 1 with
   the rest of scoring — which makes an LLM outage block a round rather than
   degrade its prose. There is no third option where it both affects grades and
   sits outside the certified envelope.
2. **The narrative worker must be supervised in the competition stack.** The
   systemd unit is documented; deploying it is an outstanding action, and it is
   now a line on the launch checklist.
3. **Retry semantics for "newer approved content" are structural, not
   editorial.** A retry cannot duplicate rows, because identity is the natural
   key. There is no concept of an operator-approved briefing that a retry must
   not overwrite; if instructors gain the ability to edit narratives, that
   guard has to be added with it.
4. **`degraded` is per job, not per call.** An operator sees that five of six
   calls fell back, not which team's briefing is template text. Enough to page
   on, not enough to answer "is *my* briefing real?" — which matters if a
   student disputes one.
5. **Old rounds still do not reconcile.** V2-015 is fixed going forward; rounds
   resolved before this change keep whatever Phase 2 wrote into their hashed
   rows. The data migration moves SC prose out, which changes where text is
   stored but no published result.


---

# Rework addendum — `49d6514`

Two audits followed the first submission. Both are closed.

## Rework 1 (audited at `a339782`) — two runtime blockers

**R1, instructor observability.** The job rows carried type, state, degradation,
model name, template version, attempts and a sanitized error, and nothing read
them but a management command. `GET /api/games/<id>/round-control/` — the
existing round-status surface — now returns a `narratives` block with those
fields and a state summary. No new subsystem, no frontend workflow. The
endpoint is also scoped to the cohort that owns the game, following the
ownership rule already used for student accounts, because `IsInstructor` checks
only the role and this data carries a model name and error text.

**R2, unsafe RAG configuration.** `COMPETITION_RAG_AFFECTS_COHERENCE` could let
Phase 2 write a hashed field that grading reads. Default-off was rejected as
insufficient — a supported deployment could flip it — so the write path was
removed rather than gated, and `require_safe_rag_configuration()` now stops
resolution before the transaction opens if the retired flag is set.

Focused verification: 8 endpoint/isolation tests (8.1 s), 62 round-control
contract tests (47.1 s), and `core.tests.test_durable_narratives` once from the
freeze — 35 tests, 47.0 s. Evidence:
`evidence/durable-narratives-rework/`. The SIGKILL drill, live-provider matrix,
determinism matrix, concurrency matrix and full suite were not re-run; their
evidence stands against its own revision `ef01237`.

## Rework 2 (documentation only) — the record contradicted the code

The runtime passed independent verification; the release record did not match
it. `V2_FINDINGS_REGISTER.md` still marked V2-016 open and assigned it to the
rules owner, and the operator guide still told operators that enabling the flag
blends the LLM score into the published number. Neither was true at `49d6514`,
and leaving them would have made the final audit report a P1 NO-GO for a defect
that no longer exists.

Corrected: the register closes V2-016 with the adopted rule, and the operator
guide says plainly that the flag is retired and setting it stops resolution.
No runtime code was changed and no tests were run; the source tree digest is
unchanged at `0c284a835d41f1a6b1ab0e1ea76b8e20cfe1e0032c13a6def75fd3e9f651003b`.

## Adopted rule for V2-016

**Published coherence, and the grades derived from it, are the deterministic
formula score. Retrieval is instructor commentary and nothing else.**

Nothing is outstanding for the rules owner. Including retrieval in a grade is
still a legitimate choice, but it is now a Phase-1 change — inside the
transaction the manifest hashes, certified with the rest of scoring — and not a
configuration flag.

## Unresolved risks, restated at `49d6514`

Item 1 of the original list is withdrawn: V2-016 is closed and needs no rules
decision. Items 2–5 stand as written — worker supervision is still a deployment
action, retry has no notion of operator-approved content, `degraded` is per job
rather than per team, and rounds resolved before the split still do not
reconcile with their manifests.

One item is added:

6. **`calculate_coherence(context, skip_rag=False)` keeps a permissive
   default.** No supported path reaches it — `_run_phase_1` always passes
   `skip_rag=True`, which the audit confirmed — so it is a trap for a future
   caller rather than a live defect. Changing the signature was out of scope
   for a focused rework and is left flagged.
