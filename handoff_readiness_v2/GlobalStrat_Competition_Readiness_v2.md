# GlobalStrat+ — Competition Readiness v2

**Purpose.** A second verification pass against the release candidate `competition-rc-2026.08.27.3`. Phase 1/2 work is accepted; this pass **pressure-tests the claims the first report makes**, on the premise that a green gate proves the test passed, not that the test was sufficient.

**Scope.** Platform functionality and features only. Human-process items (volunteer cycle, sign-offs, second operator) are deliberately out of scope here.

**Standing rules, unchanged from v1.**
- Findings are logged before they are fixed. Investigate the whole register, then repair.
- Every finding: ID, area, description, reproduction, severity (P0 blocks · P1 degrades · P2 cosmetic), evidence.
- All destructive verification on disposable isolated stacks. Production read-only.

**Framing for the agent.** The first pass was competent and found real defects. This pass assumes the *remaining* defects are the ones the first pass's method could not surface. Do not re-run passing tests for reassurance — attack the assumptions underneath them.

---

## V2-A · The determinism claim vs. the LLM in the resolution path

**Why this is first.** The report states resolution "drove real LLM narrative generation," and separately claims a round "re-runs to a byte-identical result" with an `output_sha256`. Those two statements are in tension. If any model output is inside the hashed envelope, determinism is not guaranteed under model version change, provider drift, temperature, or sampling. This is the single claim most likely to be quietly false, and it is the claim a disputed result depends on.

**Establish, with evidence:**

1. **Exact boundary.** Enumerate every field in the canonical output that feeds `output_sha256`. State, per field, whether it is computed deterministically or model-generated. Produce the list, not a summary.
2. **Scoring isolation.** Prove no LLM output reaches: leaderboard position, any score component, any state carried into the next round, or any value a team could cite in a dispute. Trace the data path; do not infer from intent.
3. **Replay under model change.** Re-run a completed round with (a) a different model version or endpoint, (b) an unavailable LLM endpoint. Determinism must hold in both. If the resolution *fails* when the LLM is unavailable, that is a P0 availability defect on its own — narrative is cosmetic and must not be able to block or fail a resolution.
4. **Non-determinism sweep beyond the LLM.** Audit the full resolution path for other unseeded entropy: wall-clock reads, `now()` in ordering or tie-breaks, map/dict iteration order, floating-point accumulation order across teams, database row order without an explicit `ORDER BY`, UUID or auto-increment values entering computation, locale- or timezone-dependent formatting. Any of these breaks replay in ways a seed does not fix.
5. **Cross-environment replay.** Replay a round on a *different* machine/container from the one that produced it. Same hash, or explain the difference.

**Acceptance.** A written determinism boundary statement: what is hashed, what is not, and why the excluded material cannot affect any competitive outcome. Replay verified across model change, LLM outage, and a second environment.

---

## V2-B · A4 balance and exploits — treat as untested, not passed

**Why.** One exploit was found and closed (FX hedging premium). The playthrough used 24 bots across four preset strategy profiles — aggressive-R&D, marketing-heavy, balanced, conservative. Those profiles play the *intended* game. They cannot find the unintended one, because they were written by someone reasoning about intended play. The report itself concedes that a real prize motivates real exploit-hunting.

**Do adversarial search, not strategy simulation.**

1. **Search the decision space, not the strategy space.** Randomised and extremal decision vectors — boundary values, zero, maximum, rapid oscillation between extremes, identical repeated decisions every round, deliberately incoherent combinations. Look for any input producing outsized or nonsensical output.
2. **Named exploit classes to attempt explicitly:**
   - *Timing* — submitting at the deadline boundary, resubmitting during resolution, ordering effects between teams processed earlier vs. later.
   - *Information* — inferring rivals' decisions from response payloads, timing differences, leaderboard deltas, cached responses, or any endpoint that leaks pre-resolution state.
   - *Numeric* — negative values, overflow, precision loss, rounding that favours one direction, currency conversion asymmetries.
   - *Economic* — any risk-free arbitrage across FX, trade finance, sourcing or inventory; any loop that generates value without cost; whether progressive disclosure creates an advantage for teams that ignore early rounds.
   - *Degenerate-but-legal* — a single strategy that wins regardless of rivals, or an early-round lead that becomes mathematically unassailable.
   - *Collusion* — two teams coordinating to advantage one. Determine whether the shared world economy permits it and whether it is detectable from the audit trail.
3. **Self-play convergence.** Run many bot games with a simple optimiser (hill-climbing or random search over decision vectors) rather than authored profiles. If it converges on a single dominant line, that line is what a motivated team will find.
4. **Sensitivity analysis.** For each decision dimension, sweep the range and plot the outcome. Flat regions mean the decision does not matter (a design problem); cliffs mean small changes swing the result (a fairness problem). Report both.

**Acceptance.** An updated exploit report separating *closed* from *accepted-and-covered-by-rules* from *accepted-and-uncovered*. Sensitivity plots for each decision dimension. An explicit statement of the strongest strategy found and its margin over a competent baseline.

---

## V2-C · RD-03 and the deploy-freeze consequence

**Why.** RD-03 correctly refuses a backup whose code revision differs from the running build. The unstated consequence: **any deploy during the competition orphans every pre-existing backup.** A mid-competition hotfix would leave the event with no usable recovery point.

1. Confirm the behaviour and its blast radius: after a deploy, which prior backups become unrestorable?
2. Determine whether a documented, tested override exists for an operator who accepts the schema-skew risk — and if not, whether one should.
3. Verify that a fresh post-deploy backup restores cleanly, so the mitigation actually works.
4. Ensure the runbook states this as a **hard rule**: no deploys inside the competition window; if unavoidable, immediate post-deploy backup, verified by restore, before the next round opens.

**Acceptance.** Behaviour documented with a tested mitigation path; runbook updated from note to rule.

---

## V2-D · Load figures pinned to the real field

**Why.** "Expected and 3×" is meaningless without a stated expected. Pin it.

1. State the modelled field: number of teams, members per team, concurrent sessions, and the deadline-burst profile.
2. Verify the worst realistic case explicitly — **all teams submitting in the final 60 seconds**, plus resolution running while users are active, plus repeated refreshes on a slow connection.
3. Re-run at the pinned figure and 3×, and identify the point at which it actually degrades. A pass at 3× tells you less than knowing where the ceiling is.
4. Confirm no submission is lost or duplicated under burst, and that the audit trail remains complete under load.

**Acceptance.** Load results stated against a named field size, with the observed failure point and the failure mode.

---

## V2-E · Post-competition data retrieval

**Why.** Round reports exist during play. The final round will include a **defence round** in which finalists present their own run, and disputes may be raised after close. Both require historical access.

1. Verify a team can retrieve every prior round's report after the competition closes, after the round is advanced, and after the game is marked complete.
2. Verify an operator can retrieve any team's full decision history with timestamps and actor, post-close, from the UI — not from the database.
3. Assess whether an end-of-run team summary (decisions by round, market conditions, position vs. rivals) is producible from stored data without new capture. Report what exists and what would need building; **do not build it in this pass.**

**Acceptance.** Post-close retrieval verified for both roles. A written statement of what an end-of-run report could contain from existing data.

---

## V2-F · Failure modes the playthrough could not produce

**Why.** The playthrough ran clean against injected adversarial *events* — a missing team, an operator correction, a deactivation. Those are scripted scenarios. Infrastructure failure is not.

Verify behaviour under:
1. Database connection loss mid-resolution.
2. Backend restart mid-resolution.
3. LLM endpoint timeout or error during resolution (see V2-A).
4. Disk full during pre-resolution `pg_dump`.
5. Two operators issuing conflicting actions concurrently (close + extend; process + correct).
6. Clock skew between application and database.
7. A team's session expiring mid-submission.
8. Network partition between frontend and backend at the deadline.

For each: does it fail closed, is the state recoverable, and is the failure visible to the operator?

**Acceptance.** Each scenario exercised on an isolated stack, with outcome and recovery path recorded. Any that fails open is P0.

---

## V2-G · Audit trail sufficiency under dispute

**Why.** The audit trail was verified as *present*. This pass asks whether it is *sufficient* — the test is not whether events are logged, but whether a specific challenge can be answered from them alone.

Attempt to answer each, using only stored data through operator tooling:

1. "We submitted before the deadline and the system says we didn't."
2. "Our decision was recorded differently from what we entered."
3. "Another team saw our decisions."
4. "The round was re-run after we were told it was final."
5. "The operator changed something without telling us."
6. "The result is wrong — prove the calculation."

**Acceptance.** Each answerable, with the exact query or screen that answers it, recorded in the runbook as a dispute-response procedure.

---

## V2-H · Regression on the v1 repairs

Short pass. Re-verify that the seventeen register items and the post-tag repairs (CR-017, RD-01/02/03, V-1/V-2, S-1) hold on the current deployed build, not on the build they were fixed against. Confirm particularly that CR-011's FX premium did not introduce a new imbalance elsewhere — a balance fix is itself a balance change.

---

## Deliverables

1. **V2 findings register** — new findings only, triaged, with reproduction.
2. **Determinism boundary statement** (V2-A) — the authoritative answer to what is reproducible and what is not.
3. **Updated exploit report** (V2-B) — with sensitivity analysis and the strongest strategy found.
4. **Load results against a named field size** (V2-D), including the observed ceiling.
5. **Failure-mode matrix** (V2-F) — scenario, behaviour, recovery, severity.
6. **Dispute-response procedures** (V2-G) — added to the operator runbook.
7. **Runbook amendments** — deploy freeze as a rule (V2-C); dispute procedures (V2-G).
8. **Updated launch checklist** with v2 gates.

## Out of scope

New features. The end-of-run report (assess only). Anything requiring human participants. Individual-level tracking or role permissions.
