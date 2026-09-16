# Owner rulings — 2026-09-16

Two rulings, given by the competition owner on 2026-09-16 in response to a
briefing that set out the options and their costs. Recorded here and nowhere
else, per the standing rule that a ruling exists in an `OWNER_RULINGS_<date>.md`
document with a date and the owner's answer. Neither was proposed as a decision
by a builder: both questions were put to the owner unanswered, with options.

Continues R1–R29 (`OWNER_RULINGS_2026-09-11.md`, `OWNER_RULINGS_2026-09-12.md`).

---

## R30 — the committed-credential guard's exemption for the CRV2-10 probe harness

**Ruling: ratify the pin.**

**The question put.** Merging the parked CRV2-10 Stage 1 evidence brought in
`handoff_readiness_v2/evidence/decision-rules/harness/stack.py`, whose line 39
reads `DB_PASSWORD = os.environ.get('DB_PASSWORD', '***REMOVED-CREDENTIAL-V2-048***')`.
That literal is the placeholder the V2-048 history rewrite substituted for the
real password, recorded under the same name in
`V2-048_HISTORY_REWRITE_RECORD.md:35` — a redaction marker, not a credential. The
`no-committed-secrets` guard cannot tell the two apart and failed the merge.
Three options were put: ratify a line-pinned exemption; drop the harness file
from the evidence merge; or edit the line to default to an empty string.

**What ratification means, stated plainly.** The allowlist entry is keyed to that
exact file, line and field, with its reasoning recorded inline. A genuine
credential placed at that exact position would be exempt. The entry is
deliberately brittle: if the line moves, the exemption stops matching and the
finding returns to be re-judged.

**What it does not dispose of.** The same file names the `donwh` role and the
database host in clear. That is the V2-048 / V2-072 access question and is
untouched by this ruling.

---

## R31 — the language model must not reach a graded score

**Ruling: sever it.** The communication score stops feeding
`RoundResultCoherence.blended_score`. It remains as feedback for the student and
the instructor, and it is not graded.

**The question put.** A student's written communication is scored 0–1 by a model
at submit time, stored as `coherence_contribution`, and blended into
`blended_score` in Phase 1 as `0.9 × formula + 0.1 × communication`. That score is
graded (`grading.py`), published, and inside the hashed manifest section
`coherence` (`manifest_sections.py:512`). **V2-016 is recorded closed on the claim
that a language model cannot reach a graded number; this path contradicts that
closure.** Three options were put: sever the path; keep it and withdraw the
determinism claim, with a human moderation route for disputes; or require
instructor confirmation of each model score before it counts.

**Why the ruling is decisive now.** `team_communication` holds no rows: no
submission has ever been scored, so nothing is retroactive and no published mark
changes. That stops being true the first time a cohort submits.

**What follows from it, for the builder — none of it ruled here beyond the sever
itself:**

- Graded coherence returns to the deterministic formula. A result can again be
  reproved from stored data, which is the claim the competition rests on.
- V2-016's closure becomes true rather than contradicted, and can be re-certified
  against the severed code rather than against its original repair.
- **The marking-scale question registered as V2-117 dissolves with the path.** It
  asked whether to restore the previous strictness after the model change; with
  the component no longer graded there is no strictness to restore. V2-117 should
  be closed by this ruling, not left open.
- The defect whereby submitting *any* communication **lowered** a team's
  coherence — the component maxes at 26 against a 0–100 formula score — stops
  affecting grades. It must still be recorded as a finding, because it was in the
  shipped code and the register's rule is that findings are recorded before they
  are repaired.
- Writing quality no longer affects standing. That consequence was stated when
  the question was put and is accepted.
