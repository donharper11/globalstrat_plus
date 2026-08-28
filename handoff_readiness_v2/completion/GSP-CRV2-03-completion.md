# GSP-CRV2-03 completion report — durable Phase-2 narrative execution

**Finding closed:** V2-006 (P1)
**Findings opened:** V2-015 (P1, repaired here), V2-016 (P1, rules decision)
**Frozen revision:** `ef01237a6542f5950f8447531a927ce96046bb7e`
**Source tree digest:** `1e17a18eba73b33876449d9982048197ce33acf9fa184eac22bd073186d750c3`
**Branch:** `crv2-03-durable-narratives`, on the GSP-CRV2-02 baseline `7272a2f`

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

1. **V2-016 needs a rules decision.** Default is now the deterministic formula
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
