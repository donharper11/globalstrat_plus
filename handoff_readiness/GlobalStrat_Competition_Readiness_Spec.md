# GlobalStrat+ — Competition Readiness Spec

**Objective.** Make GlobalStrat+ fit to run a prize competition (¥10–15k, ~6 rounds, 2 weeks, multiple concurrent teams) where a disputed result must be defensible and an exploitable strategy must not decide the outcome.

**Two phases, strictly sequenced.** Phase 1 produces findings; Phase 1 fixes nothing. Phase 2 repairs a triaged register. Do not begin Phase 2 until the register has been reviewed and prioritised.

**Standing rule.** Every finding gets an entry in the register with: ID, area, description, reproduction steps, severity (P0 blocks the competition · P1 degrades it · P2 cosmetic), and evidence (screenshot, log, request trace). No fixes during Phase 1 — a fix mid-audit invalidates the rest of the pass.

---

## Phase 1 — Audit

### A1 · Click-through walkthrough
Traverse every reachable screen and state as (a) instructor and (b) student, across a full 6-round cycle from setup to final results. Include the paths users take when things go wrong: back button mid-decision, refresh during submission, duplicate tab, session timeout, browser close and return, direct URL entry to a later round.

Record: dead ends, unhandled errors, ambiguous labels, missing confirmations, and any screen where a user cannot tell what to do next.

### A2 · Round lifecycle integrity
The highest-risk area. For each round: open → decisions accepted → deadline → resolution → results published.

Probe specifically: submission after deadline · partial submission at deadline · no submission at all · concurrent submissions from two members of the same team · a team submitting twice · resolution triggered while a submission is in flight · a team joining late · a team abandoning mid-competition.

Record what the system does in each case and whether it is defensible if it decided a prize.

### A3 · Determinism and reconstruction
Given a completed round, can the result be reconstructed exactly from stored state? Same world state and same decisions must produce the same outcome, twice.

Check: is any market/event randomness seeded, or drawn at runtime? Is every decision stored with a timestamp and submitting user? Can a dispute be answered from the database alone, without inference?

Report what is currently reconstructible and what is not.

### A4 · Balance and exploit probe
**Play adversarially.** The goal is to find the strategy that wins without playing well.

Areas most likely to yield: international trade finance and FX hedging (least battle-tested, most likely to be arbitrageable) · R&D investment ordering · supply chain sourcing under progressive disclosure · any decision that can be repeated or timed to exploit resolution order · anything that produces a dominant outcome regardless of rivals.

Also: is there a degenerate but legal strategy that makes the competition uninteresting? Does an early-round lead become unassailable?

### A5 · Concurrency and load
Simulate the expected competition load and 3× it. Concurrent decision submission across teams at the deadline is the realistic worst case — model that specifically, not just page views.

Record: response times under load, database contention, any lost or duplicated submissions, behaviour when resolution runs while users are active.

### A6 · Instructor controls
The control room under pressure: can the operator extend a deadline, correct an erroneous submission, roll back a round, re-run resolution, remove a team, and see who submitted what and when? Anything missing here becomes a live problem during the event.

### A7 · Access, isolation and integrity
Can a team see another team's decisions before resolution — through the UI, an API endpoint, a predictable URL, or a response payload? Can a user act on a team they don't belong to? Are decision endpoints validated server-side, or does the UI enforce the rules? Assume competitors with a financial incentive will look.

### A8 · Bilingual parity
EN/ZH: any missing strings, truncated layouts, or divergent meaning in decision labels. A mistranslated decision label in a prize competition is a dispute.

---

## Phase 2 — Repair and harden

Work the triaged register. P0 first; nothing ships with an open P0.

### Beyond the register — required for competition play

**Full audit trail.** Every decision: team, submitting user, timestamp, payload, round. Immutable. Every resolution: inputs, seed, outputs. This is what answers a dispute.

**Seeded determinism.** All randomness derived from a stored seed. A round must be re-runnable to an identical result.

**Server-side rule enforcement.** Every constraint the UI enforces must be enforced again server-side.

**Deadline handling made explicit.** One defined behaviour for late and missing submissions, applied uniformly, documented in the rules published to students.

**Operator recovery paths.** Deadline extension, submission correction, round re-run — each logged with who did it and why.

**Backup before every round resolution.** Automatic snapshot, restorable. The cheapest insurance available.

**Rate limiting** on decision endpoints.

### Verification
Re-run A1–A8 against the repaired build. Then a full dry-run competition with volunteer teams, treated as live: real deadlines, real resolution, an attempt to break it. Fix what the dry run finds before announcing.

---

## Deliverables

1. Findings register (all phases, triaged, with reproduction steps)
2. Fix log mapped to register IDs
3. Exploit report — strategies found, whether closed or accepted, with recommended rules language for any left open
4. Load test results at expected and 3× load
5. Operator runbook — what to do when a team disputes, a submission is lost, resolution fails mid-round, or the platform is unreachable at a deadline
6. Recommended competition rules text covering deadlines, late submissions, ties, disconnections, and disputes

---

## Out of scope

New features. Role permissions. Individual-level tracking. Anything not required to run a fair, defensible competition on the existing feature set.
