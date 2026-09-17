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
- [x] Narrative worker supervised in the competition stack. The unit was
      documented long before it ran, and that gap is the reason this gate
      stayed open: V2-068 recorded that committing a unit is not deploying it,
      and V2-006's closure had rested on a worker running nowhere. **Verified
      on this host 2026-09-17:** `globalstrat-narratives` is **active and
      enabled**, installed during the 2026-09-15 deployment. Ticked on that
      observation rather than on the unit file's existence.
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
- [x] Application runs as a non-owner database role that cannot `SET ROLE
      postgres` (V2-072). Cut over on production **2026-09-16** on owner
      authorisation, per `ops/V2-072_CUTOVER_RUNBOOK.md`; ticked
      **2026-09-17 under R33**, which re-rated the finding as mitigated for
      GlobalStrat+ and moved the remaining estate exposure to its own
      operations item. The 2026-09-05 "owner acceptance" stays withdrawn as
      never given (R19); this tick rests on the cutover, not on that claim.
      **What evidences it:** the restrictions were exercised against
      `192.168.50.38` itself, not inferred from a container — as
      `globalstrat_plus_app`, `SET ROLE postgres`, `CREATE ROLE`,
      `CREATE DATABASE`, `DROP TRIGGER` on an append-only audit table and
      `UPDATE` on that table were each refused; `globalstrat-backend` and
      `globalstrat-narratives` restarted and are serving on
      `DB_USER=globalstrat_plus_app`, with the login endpoint answering 401
      rather than the 500 a database authentication failure would give;
      `install_audit_guards --check` and `migrate --check` both clean.
      **Residual step, stated rather than assumed:** this gate's original
      wording also required `ops/provision-app-role.sh --check` to pass
      against `192.168.50.38/globalstrat_plus` after cutover, and no
      transcript of that run exists — the `--check` evidence on file is from
      the disposable proof harness (exit 1 on a wrong grant, exit 0 once
      corrected), which proves the tool works, not that it passed on
      production. It needs the root-owned app credential, so it is the
      owner's to run. **This mitigates GlobalStrat+ only:** `donwh` is
      unchanged — still a member of `postgres`, still holding CREATEROLE and
      CREATEDB, still the credential V2-048 exposed, still owner of the
      database and all 193 tables, and still shared with GlobalStrat v1 and
      BECSR, whose access history remains unreviewable.
- [ ] `ops/provision-app-role.sh --check` is run after every migration, not
      only at cutover. A default privilege grants the app role DML on each new
      table, a future audit table included; the re-run is what takes it back
      off (V2-072).
- [ ] Full backend suite run and green on the freeze candidate. The seven
      standing red tests are repaired at `b562c63`, but **no full suite has been
      run since**, and the suite has never been green: 842 tests at `acee4ea`
      gave 4 failures and 3 errors (V2-074). Added 2026-09-12; GSP-CRV2-09 owns
      the run.
- [ ] Browser pass over the participant and operator surfaces the merged work
      changed and could not build. **ATTEMPTED 2026-09-12, NOT PASSED — and it
      is the reason this gate was worth adding.** The pass ran on `46b4bbe`
      against a disposable stack, in Chromium, in **both** English and
      Simplified Chinese, and changed no runtime code. The production build
      itself passes (exit 0, warnings only) and `react-scripts test` passes, so
      **the build is not a finding**. Seven defects were found and **none is
      repaired**: V2-101 through V2-107, of which **V2-107 is a P0** — the
      pricing screen's own default row is refused 400 while the screen reports
      success. **Coverage, stated so nobody reads this as a full pass:** one
      firm, one market, one scenario (`consumer_electronics_2026`, Team 1,
      North America); the other firms, markets and two scenarios were not
      driven. **Two of the seven intended checks could not be verified at all
      — the results-screen price-adjustment notice and the not-for-sale notice
      — because no route reaches that screen (V2-103).** Extend Deadline was
      inspected but never executed; the cohort-cap path was driven through the
      API from the signed-in session rather than by clicking the roster
      widgets, so V2-104's success toast is read from source, not seen on
      screen. Still outstanding for the same reason it always was: the pass
      covered the price band, cohort caps and round control, not every surface
      the merged work touched. Added 2026-09-12 (V2-041, V2-042, V2-080).
- [ ] GSP-CRV2-12 Stage 4 — the two bilingual walkthroughs. **The code half of
      the language sweep has landed and is not in question** (V2-069's four
      residual defects repaired, bilingual parity demonstrated by rendering all
      99 messages in both languages, and a seven-assertion prevention control
      running in the suite and in CI). **Stage 4 was explicitly not performed**,
      so CRV2-12 is not complete — only its code half is. Six named checks are
      listed in `completion/GSP-CRV2-12-completion.md` §7. Added 2026-09-12.
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
      change. Added 2026-09-12. **RUN 2026-09-12 AND PASSED, gate still open.**
      At `e398fc6` a round carrying 11 `decision_research_purchase` rows, a
      deadline price-band adjustment and a not-for-sale row replayed
      byte-identically — input `ca459d0c…`, competitive hash `94b6282a…`, no
      section diffs, exit 0 — and three negative controls each refused before
      the engine ran, one of them on the new section itself. **Single
      environment, one round, one scenario, development-grade.** It discharges
      the focused replay R18 asks for; it is **not** certification, and this
      gate stays open until GSP-CRV2-09 regenerates the integrated
      four-environment evidence against the release-candidate commit (V2-086).
      Note V2-116: `determinism_fixture.py` does not run at head, so CRV2-01's
      evidence cannot currently be regenerated.
- [ ] R28 starting-field **balance** measurement. The authoring half is done —
      eight distinct profiles per scenario at `d94d6b1` (V2-109) — but the
      measurement R28 requires, that no profile carries an advantage play
      cannot overcome, **cannot be completed while V2-110 is live**: a solvent
      team losing a whole round to zero production is then punished up to 17.81
      index points by the commercial-inactivity guard, which ordered the
      finishing field under identical play. The builder declines to certify and
      that is the correct call. GSP-CRV2-11 Stage 2 balance stays open. Added
      2026-09-12.
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
`route_inventory.py:194-202`; and, of the three deployment actions this
paragraph listed, **one remains**. Verified on this host 2026-09-17:
`globalstrat-narratives` is active and enabled, so the narrative worker is
supervised; the application runs as a non-owner database role, cut over
2026-09-16 and ticked above under R33. What is **not** established is
`COMPETITION_REQUIRE_CLEAN_BUILD=true` (or `ENVIRONMENT=production`): it has no
reference in `deploy/` or `docs/`, and confirming it would mean reading
`/etc/globalstrat-plus.env`, which carries the database credential. So it is
recorded as **unverified from here** rather than assumed either way — the
deployment owner can settle it in one command.

Added to the register 2026-09-12 from ten completion reports: **V2-075
through V2-116**, including two P0s that were open and unrepaired when this
paragraph was written. **Both have since been repaired, pending closure by the
auditor — status corrected 2026-09-17, because a stale P0 in a launch checklist
misleads the audit it exists to serve.** **V2-107** — the pricing screen's
default row was refused while the screen reported success, so a team could lose
a round's decisions believing they were saved; that is the silent loss R17 ruled
against. Repaired 2026-09-16 at `1855b25`. **V2-110** — a solvent team could
lose an entire round to zero production and was then punished up to 17.81 index
points by the commercial-inactivity guard, against a best-single-lever value of
12.40; it decided the finishing order under identical play. The cause was found
and repaired at `1b6ef85`: a compliance freeze fired for not filing a customs
document that progressive disclosure forbade the team to file until round 5, so
the trigger is now gated on the effective unlock round. **Two questions it
raised remain open and are not repaired by that fix:** whether a team frozen out
by its *own* compliance failure should count as not competing (V2-110), and the
guard's severity itself — ruled 2026-09-17 by **R32**, which moves enforcement
to the standings rather than overwriting a carried index, with implementation
open against the engine owner (V2-119). Also open from that pass:
V2-101 through V2-106 and V2-108. The CRV2-12 language sweep contributes
V2-096–V2-100, renumbered from the V2-075–V2-079 its builder drafted, which
collided because that branch was cut before this register's block reached
integration. Repaired pending closure: V2-075 (the legacy
`/simulation-control/` cross-cohort reset, P0), V2-079 (the route-inventory
false positive, P1), V2-085 (preference re-authoring, under R25/R27), V2-087
(two decision-write routes unguarded by the paid-research change, P1), V2-091,
V2-092 and V2-095 (`price_band.py` outside the determinism ordering scan —
found only in the merged tree). Ruled and closable by the auditor: V2-084 (R29). Open: V2-076,
V2-078, V2-080 through V2-083, V2-086 (the v5→v6 envelope with no replay),
V2-088 (organisational-structure cash charged outside every calculator, P1),
V2-089, V2-090, V2-093 and V2-094. Also repaired pending closure and awaiting
the auditor, not closed here: V2-033, V2-041, V2-042, V2-060, V2-071 and
V2-074. See `completion/REGISTER_BACKLOG_2026-09-12.md`.

V2-010 and V2-011 are closed at `8ddd983`; they are no longer a rules blocker.
v1 GO and evidence from the pre-10–13 ruleset cannot substitute for the final
integrated verdict.
