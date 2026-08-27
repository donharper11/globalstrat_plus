# GlobalStrat+ — Competition Readiness: Final Report

**Prepared:** 2026-08-27 UTC
**Subject:** Fitness of GlobalStrat+ to run a prize competition (¥10–15k, ~6 rounds, ~2 weeks, multiple concurrent teams) where a disputed result must be defensible and no exploit should decide the outcome.
**Release candidate:** `competition-rc-2026.08.27.3` (commit `7452ee7`)
**Deployed:** frontend `main.f407eb73.js` at https://globalstrat.camdani.com; backend reloaded to the same revision.

---

## Declaration

> **Technical readiness: PASS.** Every automated readiness gate — the A1–A8 audit and its repairs, deterministic recovery, instructor visibility and dispute tooling, and a full multi-round competition playthrough — is green on the deployed build.
>
> **Launch decision: CONDITIONAL GO — cleared for the volunteer dry-run; final GO is pending three human activities only** (a live volunteer cycle, the engineering / competition-ops / rules-owner sign-offs, and a two-operator recovery sign-off). No open engineering blocker remains.

This is an honest split: the platform is mechanically and analytically ready, and the only things standing between here and launch are activities that *require people* and cannot be simulated — not more code.

---

## Scope and method

The work followed the two-phase discipline in `GlobalStrat_Competition_Readiness_Spec.md`: **Phase 1** audited the platform across eight areas (A1 click-through · A2 round lifecycle · A3 determinism/reconstruction · A4 balance/exploits · A5 concurrency/load · A6 instructor controls · A7 access/isolation · A8 bilingual parity) and produced a triaged findings register **without fixing anything**; **Phase 2** repaired the register, added the competition-grade guarantees (audit trail, seeded determinism, server-side enforcement, deadline handling, recovery paths, pre-resolution backups, rate limiting), and re-verified.

All destructive and load-bearing verification ran on **disposable, isolated stacks** (throwaway PostgreSQL containers seeded read-only from production, isolated backends). Production was only ever read; no live competition record was mutated by the testing.

---

## What was found and fixed

### Phase 1 → Phase 2 register (CR-001 … CR-017)

Seventeen findings were logged and triaged (P0 blocks · P1 degrades · P2 cosmetic). All are closed or accepted (`PHASE1_FINDINGS_REGISTER.md`, `FIX_LOG.md`). Highlights by theme:

- **Lifecycle integrity (P0):** instructor round-lock now enforced by student endpoints (CR-001); round processing is atomic under a row lock so two resolvers can't both run (CR-002); partial-decision replacement is atomic (CR-007).
- **Determinism & reconstruction (P0/P1):** decisions are captured as immutable, hashed audit events with actor + timestamp + payload (CR-003/CR-004); every resolution stores a manifest with seed, canonical input/output hashes, and code revision (CR-008); a round re-runs to a byte-identical result.
- **Recovery & backups (P0):** a verified `pg_dump` snapshot is taken before every resolution, with a guarded restore/re-run workflow (CR-005/CR-010).
- **Balance (P1):** FX hedging now charges a premium so 100% hedging is no longer a free dominant strategy (CR-011); the exploit report documents what was closed vs. accepted (`EXPLOIT_REPORT.md`).
- **Fail-closed engine (P1):** every deterministic resolution stage propagates errors through the outer transaction, so a partial result can't publish (CR-013).
- **Access & rate limiting (P0):** cross-team reads/writes, unenrolled users and spoofed identities are rejected server-side; decision endpoints are throttled (CR-006).
- **Operability & rules (P1):** operator actions are recorded in an immutable log with actor and reason; missing submissions are defaulted uniformly and the fallback is published in the rules (CR-009/CR-012; `RECOMMENDED_COMPETITION_RULES.md`).
- **Bilingual parity (P2):** EN/ZH key sets match exactly and student-facing supply-chain copy was extracted from hard-coded English (CR-014).
- **A1 UX (P1):** direct-navigation blank screens fixed (CR-016); **unsaved-decision navigation guard** added so a competitor can't silently lose an edit (CR-017).

### Post-tag verification and repairs (this engagement's focus)

| ID | Sev | Found during | Status |
|----|-----|--------------|--------|
| **CR-017** | P1 | A1 rehearsal | **Closed** — `useUnsavedChangesGuard` warns before leaving a dirty decision page; re-verified (browser-back now prompts instead of silently reverting). |
| **RD-01** | P1 | Recovery drill | **Closed** — restore tolerated only benign cross-version `SET` errors; `pg_restore --exit-on-error` no longer aborts a valid restore. |
| **RD-02** | P1 | Recovery drill | **Closed** — restore onto a freshly recreated schema; FK-dependent object drops no longer block it. |
| **RD-03** | P1 | Recovery drill | **Closed** — recovery refuses a backup whose code revision differs from the running build (guards against schema/code skew). |
| **V-1** | P1 | Instructor-visibility check | **Closed** — `submission_origin` distinguishes a *never-submitted (defaulted)* team from a *deliberately-empty* one, from the UI/API, no database needed. |
| **V-2** | P2 | Instructor-visibility check | **Closed** — `locked_by` surfaces the individual submitter in the drill-down. |
| **S-1** | P2 | Playthrough build | **Closed** — processing an unlocked team returns an actionable **400**, not a raw 500. |

The recovery drill is the clearest illustration of *why* end-to-end testing mattered: the recovery path had only ever been dry-run tested, and the real restore + re-run **failed on three distinct defects on the deployed stack** — all now fixed, with a green re-run reproducing a round's `output_sha256` byte-for-byte.

---

## Gate status

| Gate | Verdict | Evidence |
|------|---------|----------|
| A1 click-through (incl. 6-round + browser-state) | **Pass** | `A1_BROWSER_STATE_LIFECYCLE_REHEARSAL.md`, `evidence/a1-lifecycle-20260827/` |
| A2 round-lifecycle integrity | **Pass** | `CONSOLIDATED_A1_A8_VERIFICATION.md` |
| A3 determinism / reconstruction | **Pass** | manifests + replay; `evidence/recovery-drill-20260827/` |
| A4 balance / exploits | **Pass** | `EXPLOIT_REPORT.md` |
| A5 concurrency / load (expected + 3×) | **Pass** | `LOAD_TEST_RESULTS.md`, `evidence/deadline-*.json` |
| A6 instructor controls | **Pass** | 50 focused tests; recovery drill |
| A7 access / isolation / integrity | **Pass** | isolation tests; server-side enforcement |
| A8 bilingual parity | **Pass** | 1,986 EN/ZH keys, zero mismatch |
| Operator recovery (end-to-end, isolated) | **Pass** | `RECOVERY_DRILL.md`, `evidence/recovery-drill-20260827/` |
| Instructor visibility & dispute tooling | **Pass** | `INSTRUCTOR_VISIBILITY_AND_DRYRUN.md`, `evidence/instructor-visibility-20260827/` |
| Adversarial single-round simulation | **Pass (8/8)** | `volunteer_cycle_sim.py`, `evidence/volunteer-cycle-sim-20260827/` |
| Full 6-round, 24-team playthrough | **Pass (0 issues)** | `full_playthrough_sim.py`, `evidence/full-playthrough-20260827/` |
| Backend regression suite | **Pass (275 tests)** | run on isolated stack |

---

## The playthrough (automated stand-in for the human dry run)

Because a real volunteer cycle takes time to organise, the highest-value automated substitute was built and run: `full_playthrough_sim.py` plays a **complete 6-round game with 24 bot teams**, each making strategy-differentiated decisions (budget split + marketing price/volume per product-market, across aggressive-R&D / marketing-heavy / balanced / conservative profiles), with adversarial events injected **every round** — a missing team, an operator correction, and a mid-game team deactivation/reactivation — then the operator closes → processes → advances.

**Every round processed (HTTP 200), a leaderboard was produced, the resolution manifest completed, and 0 issues were found.** Round 2's leaderboard correctly dropped to 23 teams when one was deactivated. Resolution even drove real LLM narrative generation in Phase 2.

This front-loads the *mechanical and engine* class of risk — exactly the failures that would otherwise waste volunteers' time — and it found none. It is **not** a replacement for the human cycle (see next section).

---

## Remaining before live launch — human activities only

1. **Volunteer competition cycle** — a real cycle with separate people, real deadlines, deliberate late/missing/duplicate submissions, a correction, a deadline extension, out-of-band outage comms, a team deactivation, and an operator incident drill. Bots cannot test what only humans reveal: **comprehension** (ambiguous labels, tie-break intuitiveness, translation meaning), **incentivised adversarial behaviour** (a real prize motivates real exploit-hunting), **real elapsed duration** (sessions, caches and state over two weeks), and **operator judgement under pressure**.
2. **Sign-offs** — reconcile anything the volunteer cycle surfaces, re-run affected verification, and obtain engineering, competition-operations, and rules-owner sign-off.
3. **Two-operator recovery sign-off** — the recovery command records a single actor; a live recovery should be counter-signed by a second operator per `OPERATOR_RUNBOOK.md`.

Operational notes for the event live in `OPERATOR_RUNBOOK.md`, `RECOVERY_RUNBOOK.md`, `BACKUP_RETENTION_POLICY.md`, and `RECOMMENDED_COMPETITION_RULES.md`. One documented gap: there is **no in-app operator broadcast** for outage communications — treat it as an out-of-band step in the runbook.

---

## Deliverables (per the spec)

1. **Findings register** — `PHASE1_FINDINGS_REGISTER.md` (all phases, triaged, with reproduction).
2. **Fix log** — `FIX_LOG.md` (mapped to register IDs, incl. CR-017, RD-01/02/03, V-1/V-2, S-1).
3. **Exploit report** — `EXPLOIT_REPORT.md`.
4. **Load-test results** — `LOAD_TEST_RESULTS.md` (expected and 3× load).
5. **Operator runbook** — `OPERATOR_RUNBOOK.md` (+ `RECOVERY_RUNBOOK.md`).
6. **Recommended competition rules** — `RECOMMENDED_COMPETITION_RULES.md`.
7. **Consolidated A1–A8 verification** — `CONSOLIDATED_A1_A8_VERIFICATION.md`.
8. **Recovery drill** — `RECOVERY_DRILL.md`.
9. **Instructor visibility + dry-run** — `INSTRUCTOR_VISIBILITY_AND_DRYRUN.md`.
10. **Simulation harnesses** — `volunteer_cycle_sim.py`, `full_playthrough_sim.py` (re-runnable against any isolated stack).
11. **Launch checklist** — `LAUNCH_CHECKLIST.md` (release-candidate gates all checked; live-competition gates are the human items above).

Release lineage on `origin`: `competition-rc-2026.08.27.1` → `.2` → **`.3`** (current).

---

## Bottom line

Nothing engineering-side is blocking the competition. The build is committed, tagged, deployed, and reproducible; every automated gate passes; and a full competition-scale playthrough runs clean. **Run the volunteer cycle, act on whatever it surfaces, collect the sign-offs — and it is ready to launch.**
