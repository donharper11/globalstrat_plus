# Competition launch checklist v2

- [x] Findings logged before repair.
- [x] Expanded deterministic envelope implemented/unit-tested.
- [x] LLM structurally isolated; no-key regression green.
- [x] Expanded replay: changed model, outage, second environment — game 37
      round 1, four runs from one verified source tree, one competitive
      hash, four narrative hashes; `evidence/determinism/`.
- [x] Unordered-query entropy sweep closed — 168 sites ordered (93 inline, 75
      via a local name, the latter found by a failing replay: V2-012), 6
      justified exemptions, AST guard + forward/reverse insertion test;
      `ORDERING_AUDIT.md`.
- [x] Random/extremal exploit search and bounded sensitivity characterisation
      complete — legal-space screen, grouped sweeps and tournament; V2-018 and
      V2-020 through V2-025 closed; `GSP-CRV2-06_COMPLETION_REPORT.md`.
- [x] Operator concurrency fail-closed — 0 of 214 registered mutating routes
      unguarded, 1200 races, 0 deadlocks, 0 5xx;
      `OPERATOR_CONCURRENCY_MATRIX.md`. **Amended 2026-09-12, not re-ticked:**
      that count rested on one false positive — a boundary marker matched by
      substring against a same-named function in the legacy engine (V2-079).
      The detector is repaired at `d9cbd43` and the offending route is deleted
      at `a37bb92`; the inventory then read **0 unguarded of 217** mutating
      routes. Re-measured again after the paid-research merge, which introduced
      and repaired two genuinely unguarded lifecycle routes (V2-087): **219
      mutating, 37 lifecycle-mutating, 21 guarded, 16 exempt, 0 unguarded**,
      both `--check` commands clean. This is a re-measurement, **not** a
      re-certification — the removal handoff claims no gate closed and
      GSP-CRV2-09 owns re-certification.
- [x] Phase-2 narratives durable and recoverable — jobs committed with the
      numbers, SIGKILL drill recovers, competitive hash unmoved;
      `NARRATIVE_WORKER_OPERATIONS.md`.
- [ ] Narrative worker supervised in the competition stack (systemd unit
      documented; deployment action outstanding).
- [x] Deploy freeze and break-glass path documented.
- [x] Fresh pre-resolution backup restored on an isolated stack; tampered and
      out-of-root dumps refused; CRV2-07 failure walkthrough.
- [x] Field pinned: 24 teams × 4 members / 96 sessions.
- [x] Field and 3× traffic profiles carried with reconciled writes — 96 and
      288 sessions, p95 90.1 ms / 175.0 ms, zero 5xx, transport failures,
      deadlocks or lost writes; `GSP-CRV2-07_LOAD_REPORT.md`.
- [ ] Combined deadline burst + refresh + Phase-1 resolution under load. CRV2-07
      measured refresh/save/lock traffic at field and 3× but explicitly did not
      drive instructor resolution under load; do not relabel that evidence.
- [x] Supported load ceiling measured at at least 3× field; staged
      authentication procedure and session-readiness gate proven.
- [x] Post-close browser retrieval captured for both roles; all six disputes
      answerable through supported paths; `GSP-CRV2-08_COMPLETION_REPORT.md`.
- [x] Failure and recovery walkthrough complete — concurrent process, restart,
      deadline refusal, backup failure, database loss and verified restore;
      `GSP-CRV2-07_FAILURE_REPORT.md`.
- [x] Submission audit evidence exposed in instructor tooling.
- [x] Six dispute procedures added to runbook.
- [x] Backend regression: 387/387 PASS, VM, 2026-08-28, from frozen commit
      `ef01237` (50 determinism + 31 concurrency + 28 durable-narrative tests).
- [x] Resolution refuses an unidentified build; replay refuses a source-tree
      mismatch before mutation.
- [ ] Competition stack sets `COMPETITION_REQUIRE_CLEAN_BUILD=true` (or
      `ENVIRONMENT=production`) — deployment action, not yet done.
- [x] Frontend production build PASS (warnings), 2026-08-28.
- [x] Frontend clean install, Jest and production build pass on the supported
      toolchain; V2-009 closed by GSP-CRV2-05.
- [ ] For every competition heat, set `SimulationInstance.settings['is_competition'] = True`
      and confirm its course has a non-null `instructor_id`; verify all heats with
      the audit snippet in `completion/GSP-CRV2-10-stage6-completion.md`. An
      unflagged heat silently loses the V2-033 cross-cohort protection.
- [ ] Application runs as a non-owner database role that cannot `SET ROLE
      postgres` (V2-072, open P0 — the 2026-09-05 owner acceptance was
      withdrawn as never given; see R19).
- [ ] Full backend suite run and green on the freeze candidate. The seven
      standing red tests are repaired at `b562c63`, but **no full suite has been
      run since**, and the suite has never been green: 842 tests at `acee4ea`
      gave 4 failures and 3 errors (V2-074). Added 2026-09-12; GSP-CRV2-09 owns
      the run.
- [ ] Browser pass over the participant and operator surfaces the merged work
      changed and could not build. `node_modules` was absent in both builders'
      worktrees, so `MarketingPage.js` / `ResultsPage.js` (the price-band legal
      range, the blank-price alert, the "clear the price box" interaction and
      the results-screen not-offered notice) and `RoundControlCard.js` were
      never built, linted or clicked. Locale key parity was checked; a backend
      200 is not evidence of frontend completion. Added 2026-09-12 (V2-041,
      V2-042, V2-080).
- [ ] `reset_simulation` withheld from the competition deployment. Its unscoped
      `TRUNCATE`/`UPDATE` statements are unchanged and reach every instance on
      the host, swallowing failures (V2-076). The routed form was deleted under
      R16; the CLI form was not. Added 2026-09-12 — operational control, not a
      code change.
- [ ] Downgrade guard for migration `0085_price_band_blank_price`: a resolved
      round can now legitimately contain null `retail_price` rows under the
      not-for-sale rule, so a rollback below `0085` must price or delete those
      rows first. Added 2026-09-12 (V2-041).
- [ ] Focused replay regression for the v5 → v6 manifest envelope change. Paid
      research adds a hashed output section, so the envelope moved and **no
      replay was run** (V2-086), though R18 requires one for a change inside the
      CRV2-01 determinism boundary. Note when reading any replay across this
      point: **every round will differ even where no outcome does**, because the
      envelope gained a section — a hash diff here is not evidence of an engine
      change. Added 2026-09-12.
- [ ] Decision rules and economic legal space certified (GSP-CRV2-10).
- [ ] Economy, starting-field and stakeholder calibration certified
      (GSP-CRV2-11).
- [ ] Player-facing bilingual language sweep complete (GSP-CRV2-12).
- [ ] Integrated breadth bug sweep complete (GSP-CRV2-13).
- [ ] Independent integrated re-audit, single backend/frontend regression and
      final GO/NO-GO complete (GSP-CRV2-09 — runs last).

Decision: **NO-GO for a prize competition at this checkpoint.**

Closed with evidence from named revisions: GSP-CRV2-01 (V2-001, V2-002,
V2-012, V2-013, V2-014), GSP-CRV2-02 (V2-004), GSP-CRV2-03 (V2-006, V2-015,
V2-016), GSP-CRV2-04 (V2-007), GSP-CRV2-05 (V2-009), GSP-CRV2-06
(V2-018, V2-020 through V2-026, V2-028; V2-019 and V2-027 withdrawn),
GSP-CRV2-07 (V2-029), and GSP-CRV2-08 (V2-030 through V2-032 and V2-034
through V2-036; V2-033 withdrawn under the shared-pilot rule).

Outstanding: GSP-CRV2-10 through 13, followed by GSP-CRV2-09's final integrated
re-audit; V2-017, which leaves 216 Django admin write routes outside the audited
lifecycle boundary — its route-inventory blind spot is confirmed still open at
`route_inventory.py:194-202`; and three deployment actions — supervise the
narrative worker, set `COMPETITION_REQUIRE_CLEAN_BUILD=true` (or production
environment), and run the application as a non-owner database role so it cannot
drop its own audit guards.

Added to the register 2026-09-12 from six merged completion reports: **V2-075
through V2-094**. Repaired pending closure: V2-075 (the legacy
`/simulation-control/` cross-cohort reset, P0), V2-079 (the route-inventory
false positive, P1), V2-085 (preference re-authoring, under R25/R27), V2-087
(two decision-write routes unguarded by the paid-research change, P1), V2-091
and V2-092. Ruled and closable by the auditor: V2-084 (R29). Open: V2-076,
V2-078, V2-080 through V2-083, V2-086 (the v5→v6 envelope with no replay),
V2-088 (organisational-structure cash charged outside every calculator, P1),
V2-089, V2-090, V2-093 and V2-094. Also repaired pending closure and awaiting
the auditor, not closed here: V2-033, V2-041, V2-042, V2-060, V2-071 and
V2-074. See `completion/REGISTER_BACKLOG_2026-09-12.md`.

V2-010 and V2-011 are closed at `8ddd983`; they are no longer a rules blocker.
v1 GO and evidence from the pre-10–13 ruleset cannot substitute for the final
integrated verdict.
