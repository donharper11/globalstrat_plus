# globalstrat+ Rework Spec & Verification Protocol — 2026-07-13

**Author:** Investigative agent (read-only audit; no code changed).
**Audience:** The rework builder agent + the human reviewer.
**Question answered:** *Is the current globalstrat+ codebase an honest reflection of
the directives in `specs/` (the CC-## bundles, acceptance reports, and
STANDING-DISCIPLINE)?*

---

## 0. TL;DR verdict

**Yes — this codebase is an honest reflection of its directives.** This is the
*opposite* result from the GSCM audit. I went in looking for the "claims work was
done while a simple task can't be completed" pattern and did not find it. The
acceptance reports are accurate, the SC engine is real, the frontend is genuinely
wired to real endpoints, and the honesty gaps that exist run *against* the
project's favor (the plan under-states what's built, not over-states it).

What I verified **live** (running backend :8012, real `globalstrat_plus` DB):
- The SC engine actually ran and populated real state: `SupplierState` (12 rows),
  `LaneState` (2), `ResilienceScoreHistory` (16), `SCEventInstance` (3),
  `SourcingDecision` (24), `SourcingAllocation` (192), `RoundResultFinancials`
  (28). Not empty tables behind "done" claims.
- The resilience-score endpoint returns a **real** computed score (20.538) with a
  genuine 6-component weighted breakdown and the class-override weights — not a
  stub.
- Real, human team names (Cobalt Innovations, Titan Micro, Apex Devices…), not
  `test*` junk.
- **Tenancy works:** student1 (team 18) reading team 19's SC data → **403**.
- **Ghost-model landmine is clear:** the discipline's own §1.8 delta returns
  **0 ghosts** (174 registered models, all physically backed). `manage.py check`
  clean; all migrations applied.
- The CC-19 → dashboard **coherence holds**: the dashboard reads and renders the
  now-real resilience score + "Disruption impact this round" panel from
  `ResilienceScoreHistory.disruption_impact`, with keys matching the engine dict
  end-to-end, confirmed in the freshly compiled bundle.

So the rework here is **not** "fix fake work." It is: **(a) finish the genuinely
un-built v1 gaps, (b) a few hardening items, (c) truthfulness housekeeping on the
roadmap doc, and (d) verify two small data oddities.** Details below.

**The one honesty defect worth stating plainly:** `CC-SEQUENCE-PLAN.md` is stale.
It marks CC-5, CC-7 as "Not drafted" and CC-19 as "Not drafted" when all three are
built, merged, and (for CC-5) evidenced by migrations 0043–0050 that took the ghost
count 39→0. CC-19B isn't in the plan at all. No bundle is falsely claimed *done* —
the plan simply wasn't maintained, which violates its own "updated as specs land"
rule. That's a documentation-truth gap, not a code gap, but it's the thing most
likely to mislead a future reader about project state.

---

## 1. How this was verified (so you can trust / reproduce it)

Four angles, same as the GSCM audit:
1. **Spec reading** — `STANDING-DISCIPLINE.md`, `CC-SEQUENCE-PLAN.md`, the
   gap-closure audit, and the CC-19/19B/23A/22 specs + acceptance reports.
2. **Static code audit** — three parallel auditor agents on (a) the CC-19/19B SC
   engine, (b) the SC frontend + CC-19→dashboard coherence, (c) roadmap/critical-
   path truthfulness — each returning file:line evidence and hunting for
   stubs/mocks.
3. **Live backend introspection** — `manage.py check` (0 issues), migrations (all
   applied), the §1.8 ghost delta (0 ghosts), and Django-shell queries against the
   live `globalstrat_plus` DB for game/team/SC-state counts.
4. **Live API walkthrough** — minted JWTs (PyJWT, `create_access_token`) for
   `instructor` and `student1`, and exercised the real SC endpoints on :8012:
   sourcing GET (real allocations), resilience-score (real score + components),
   sc-events, and cross-team access (correctly 403).

**Environment facts (for the rework agent):**
- Backend: gunicorn on **:8012** (`bind 0.0.0.0:8012`, 3 workers). Frontend:
  `serve_plus.js` on **:8014** proxying `/api` → :8012. Both live now.
- Use **system `python3`** for `manage.py` (Django is installed at user level). DB
  is `globalstrat_plus` on `192.168.50.38`; the password is a **hardcoded default**
  in `settings.py` (see R7).
- Custom User model with SHA-256 password hashes and **PyJWT** bearer auth
  (`core/authentication.py::create_access_token`). `auth/me` expects a `user_id`
  (frontend supplies it); the SC endpoints authenticate purely from the bearer
  token.
- Running the **full** test suite: use `python3 manage.py test core --noinput`
  (let it create a fresh test DB). Do **not** use `--keepdb` against a
  half-created test DB — it produces spurious `setUpClass` DB-connection errors
  that look like failures but aren't (I hit exactly this; a clean run is the
  honest signal — see §2 note).

---

## 2. What is genuinely DONE (don't "rework" these — they're real)

| Area | Status | Evidence |
|------|--------|----------|
| **SC engine (CC-19/19B)** | Real, tested | `core/engine/sc_engine.py` 3 real steps (state@114, costs@199, resilience@276); Channel-1 throttle in `revenue.py:92-131`; Channel-2 in `financials.py:123-128`; Liebig `cf=min`, contingency reroute correct; config keys DB-driven (`sc_backup_supplier_premium_pct`, `sc_air_mode_premium_mult`, `logistics_base_cost_per_unit`). `test_cc19_sc_engine` **7/7 OK** (fresh run). |
| **SC frontend (CC-10/12/13/14/15/23A)** | Real | 4 decision pages + dashboard routed, load-on-mount, save, allocation-sum-to-100% validation, shared `scState.js` state vocabulary; all calls hit real `:8012/api` routes; honest empty-states, no mock data. |
| **CC-19 → dashboard coherence** | Holds | `SupplyChainPanel.js` reads `d.resilience.score` + `disruption_impact.{capacity_factor,lost_revenue,disruption_cost}`; keys match `sc_engine.py:315-335`; fresh build contains the panel. |
| **CC-5 fork audit / ghost triage** | Done + merged | `specs/reports/cc-05/summary.md`; 39 ghosts → 4 pruned + 35 promoted via migrations 0043–0050; live delta = 0 ghosts. |
| **CC-7 fork-and-clean** | Done + merged | `reports/cc-07/execution_report.md`; merge `968b6a6`. |
| **CC-8…15** | Built + browser-verified | per-bundle acceptance reports + screenshots in `specs/reports/cc-08..15`. |
| **Tenancy / access control** | Works | cross-team SC read → 403 (live). |
| **Scenario-loader validation (gap G1)** | Closed | `_validate_supply_chain` enforces CC-1 §8's 9 rules; `test_cc_gaps` covers it. |

The acceptance reports for these are trustworthy. Spot-checks matched reality every
time.

> **Note on the test suite (verified):** the CC-19B report claims "132 tests OK."
> I re-ran the full suite clean (`python3 manage.py test core --noinput`, fresh
> test DB) and got **`Ran 132 tests … OK`, 0 errors/failures** — the claim is
> true. (An earlier `--keepdb` run showed 21 `setUpClass` DB-connection errors;
> those were a stale-test-DB artifact of `--keepdb`, not real failures — the clean
> run is the honest signal. Don't use `--keepdb` here.)

---

## 3. The real gap surface (what actually needs work)

None of these are "fake work to fix." They are honestly-unfinished v1 scope,
hardening, and housekeeping.

### Genuinely un-built bundles (honestly not-started; needed for a real v1)
- **CC-16 — Instructor SC panel (highest).** No spec, no report, no code. CC-5
  routed 5 instructor-facing needs here (view SC decisions per team, inject events,
  audit resilience, compliance-regime toggles, disclosure overrides). Without it
  there is **no facilitation surface** for a classroom sim — an instructor can't
  run an SC-enabled game.
- **A true multi-round outcome-verification E2E.** CC-22 is built and passes, but
  it proves *one* round advances without crashing and that decisions persist — a
  smoke-and-persistence test, **not** the "10 rounds with event injection +
  expected-outcome verification" its own spec §2 advertises (the spec hedged §2.11
  as conditional). Now feasible since CC-19 produces SC outputs. This is the actual
  finish-line gate.
- **CC-20 — FX hedge lifecycle.** The Trade Finance & FX page (CC-13) persists a
  hedge decision, but there is no open→mark-to-market→settle→book-P&L lifecycle
  (grep: no `mark_to_market`), so the FX decision is currently **inert in the
  engine** — pedagogically hollow.
- **CC-18 — Compliance enforcement.** Compliance flags/regimes are surfaced, but
  the detention → market-freeze → remediation-cost → reputation loop isn't closed;
  UFLPA/CBAM teaching value is unrealized.
- **CC-23 — EN/ZH i18n.** New SC labels/help/validation are English-only; the sim
  targets Chinese-executive/BNBU audiences, so this is adoption-blocking for the
  stated market.
- **CC-11 — RAG corpus** (`globalstrat_plus_articles` empty) and **CC-17 — LLM
  narratives**: honestly gated/deferred; enrich but aren't required for a
  functioning numeric v1.
- **CC-24/25 — more scenarios:** only Consumer Electronics has SC data; nice-to-
  have for v1.

### Hardening / correctness items
- **SC subsystem is fail-open.** The three SC steps in `advance_round.py` are
  best-effort `try/except`. A throw in `run_sc_state` → `revenue.py:92` defaults
  `cf=1` and `financials.py:123` defaults cost `0`, so **disruptions silently do
  nothing that round** and the round still "succeeds looking undisrupted." Two of
  three handlers log via `logger.exception` (observable); `calculate_sc_disruption_costs`
  logs only to `context.log` (quieter). This is honestly disclosed, but it's a real
  operational risk: a subtle SC bug degrades to "no disruptions ever" without a hard
  signal.
- **Hardcoded secrets default to known values.** `settings.py:96`
  `DB_PASSWORD` default `'donwhhostingroot'`; `SECRET_KEY` defaults to a committed
  `django-insecure-…` literal; `JWT_SECRET_KEY = SECRET_KEY` (line 228) — so a
  deploy that forgets `DJANGO_SECRET_KEY` **signs JWTs with a publicly-known key**
  (auth-bypass risk). Env-overridable, but fail-*open*.

### Data oddities to verify (may be benign, may be bugs)
- **Round-number vs Round-FK in serializers.** SC decision/allocation/resilience
  payloads expose `"round": 37 / 15 / 16` while the game is at round 1–3. This is
  almost certainly the serializer exposing the `Round` **FK id**, not the round
  *number* — but a student-facing `round: 37` on a round-1 decision is confusing at
  best and a mis-join at worst. Confirm which, and expose `round_number`.
- **Resilience score identical across rounds.** game 10 team 10 shows the exact
  same score (20.538) and components for round 1 and round 2. Plausible (static
  inputs on a dev game), but verify the score actually responds to changed sourcing
  decisions round-over-round — otherwise the resilience mechanic is inert.

### Housekeeping (truthfulness / git hygiene per STANDING-DISCIPLINE §6)
- **Stale roadmap.** Update `CC-SEQUENCE-PLAN.md` §2/§3/§4 to reflect reality:
  CC-5, CC-7, CC-8–15, CC-19 built+merged; add CC-19B. The pending uncommitted edit
  to that file only flips CC-8–15/22/23A and **leaves CC-5/7/19 stale** — extend it.
- **Uncommitted working tree.** Doc-only edits to 6 CC specs + the plan, and an
  untracked `frontend/serve_plus.js`. None affect tests, but commit them so state is
  reproducible and the tree is clean (§6).

---

## 4. The rework work-list (prioritized)

Each item names its **Proof required** — the evidence the rework agent must produce
before claiming it done (per §5).

**P0 — truthfulness + gating checks (fast, do first)**
- **W1. Re-run the full suite clean and record the real number.**
  `python3 manage.py test core --noinput`. (Baseline confirmed by this audit:
  **132 tests OK, 0 failures.**) Re-confirm green after any change; any real
  (non-DB-connection) failure is a P0 blocker.
  *Proof:* the final `Ran N tests … OK` line pasted verbatim.
- **W2. Fix the roadmap doc + commit the working tree.** Make
  `CC-SEQUENCE-PLAN.md` truthful (CC-5/7/8-15/19/19B statuses); commit the pending
  spec edits + `serve_plus.js`.
  *Proof:* `git status` clean; the plan's status table matches git reality.
- **W3. Verify the two data oddities** (round-FK-vs-number; resilience-changes-with-
  decisions). Fix if bugs; document if benign.
  *Proof:* an API response showing `round_number` correctly, and a before/after
  resilience score across two different sourcing decisions.

**P1 — the v1 finish-line**
- **W4. Build CC-16 (instructor SC panel).** Write the spec first (it doesn't
  exist), then build: per-team SC decision viewing, event injection UI, resilience
  audit, compliance-regime + disclosure overrides. Observes STANDING-DISCIPLINE.
  *Proof:* browser walkthrough (§5) of an instructor injecting an event and seeing
  it hit a team's next round.
- **W5. Build the real 10-round outcome-verification E2E.** Extend CC-22 to run 10
  rounds with automated decisions + injected disruptions and assert *expected
  outcomes* (resilience trends, lost-sales on disruption, recovery), not just
  no-crash. Determinism/reproducibility check.
  *Proof:* the test file + a green run + a short outcome table.
- **W6. Harden the fail-open SC subsystem.** At minimum, make all three handlers log
  at ERROR with a distinct, alertable marker; consider a "strict mode" that fails
  the round loud in non-prod so SC bugs surface in testing.
  *Proof:* a forced exception in `run_sc_state` produces a clear ERROR log and (in
  strict mode) a visible failure, not a silent undisrupted round.

**P2 — deeper v1 scope + prod hardening**
- **W7. Fail-closed secrets in production.** When `IS_PRODUCTION`, raise if
  `DJANGO_SECRET_KEY` / `DB_PASSWORD` are unset instead of using the committed
  defaults.
  *Proof:* prod-mode boot with unset secrets refuses to start.
- **W8. CC-20 FX hedge lifecycle**, **W9. CC-18 compliance enforcement**,
  **W10. CC-23 EN/ZH i18n** — each per its (to-be-written) spec, observing the
  discipline, with the §5 verification.
- **W11 (deferred, note only): CC-11 RAG corpus, CC-17 narratives, CC-24/25
  scenarios** — gated/optional for v1; list explicitly as deferred, don't silently
  skip.

---

## 5. MANDATORY VERIFICATION PROTOCOL (for the rework agent)

This project already practices strong verification (STANDING-DISCIPLINE + browser
acceptance passes). Keep that bar. The rules below make "done" mean *observed
working*, never "wired up."

### 5.1 Honesty rules (non-negotiable)
1. **Observe, don't assume.** A claim not verified against the live app / live DB /
   a green test is "unverified" — say so. `manage.py check` passing ≠ feature works.
2. **Verify-before-wire (STANDING-DISCIPLINE §1) still applies** — confirm every
   table/column/endpoint/route name before referencing it; halt + report mismatches
   in the §3 format rather than inventing names.
3. **No new stubs, placeholders, hardcodes, or mock data.** This codebase is clean
   of them today; keep it that way. If you can't implement for real, leave it
   clearly unfinished and report it.
4. **Right target:** backend :8012, frontend :8014, DB `globalstrat_plus`, system
   `python3`. Don't confuse with the *other* project `globalstrat` on :8000/:8002.
5. **Prove multi-team / multi-round, not a single happy path.** SC mechanics only
   mean something across rounds and across teams (disruptions, recovery,
   leaderboard). A one-round demo is not acceptance.
6. **Report failures verbatim** (console/network/log). Partial is fine;
   dishonest-complete is not.
7. **Leave live game data as found** if you touch it for testing (mint a token,
   read; if you write a decision, revert it).

### 5.2 Environment bring-up
```bash
cd /home/ubuntu/projects/globalstrat+/backend
python3 manage.py check                     # 0 issues
python3 manage.py showmigrations | grep '\[ \]'   # empty = all applied
# ghost-model delta (STANDING-DISCIPLINE §1.8) — must stay 0:
python3 manage.py shell  # run the registered-vs-physical delta from §1.8
python3 manage.py test core --noinput       # full suite, fresh test DB (~132)

# frontend
cd ../frontend/globalstrat-frontend
CI=false npx react-scripts build            # compiles clean
# serve_plus.js already serves build/ on :8014 -> :8012
```

### 5.3 Browser verification (Playwright) — REQUIRED for any UI item
Playwright/puppeteer is available (the repo's own acceptance passes used
puppeteer-core against system Chromium; screenshots live in `specs/reports/cc-*/`).
Match that: drive the real app on :8014 and **capture screenshots**.

**The full SC analyst loop + instructor loop, on a real game across ≥3 rounds:**
1. **Student:** log in → open each SC decision page (Sourcing, Logistics, Trade
   Finance/FX, Inventory) → confirm current values load, the state badge reads
   "Current (saved)", edit an allocation → badge flips to "Draft — unsaved" →
   save → real confirmation; **allocation sum-to-100% validation blocks a bad
   save**. Refresh → persists.
   *Capture:* each page in current + draft state.
2. **Instructor (after W4):** open the instructor SC panel → view a team's SC
   decisions → inject a disruption event → advance the round.
   *Capture:* the injection + the advanced round.
3. **Dashboard after advance:** student re-opens the Supply Chain dashboard tab →
   resilience score + 6-component breakdown render real numbers; on a disrupted
   round the **"Disruption impact this round"** panel shows capacity factor / lost
   sales / disruption cost; on a clean round it honestly shows no disruption.
   *Capture:* both a disrupted and a clean round.
4. **Multi-round outcome (W5):** run 10 rounds; confirm resilience trends, disruption
   impact, and recovery behave as the engine intends (not identical every round).
   *Capture:* the outcome table + a resilience trend.
5. **Console/network:** no uncaught errors; no 404/500 on a loaded page (the known
   benign `…/decisions/round/N/` 404 for absent drafts, gap-audit G8, is the only
   acceptable one — confirm it's still just that).

**Pass condition:** the reviewer can watch the captures and see a student complete
the SC decision loop with validation and see real resilience/disruption results
update across rounds, and (after W4) an instructor run an SC-enabled game
end-to-end.

### 5.4 API pre-flight (fast, before the browser run)
Mint a JWT (`core/authentication.create_access_token`) and curl: sourcing GET
(real allocations), resilience-score (real score after a processed round),
cross-team read (must 403), and a decision save+revert. Necessary but **not** a
substitute for §5.3.

---

## 6. Definition of Done for this rework
- [ ] W1 green full suite (real number recorded); W2 tree clean + roadmap truthful;
      W3 data oddities resolved/documented.
- [ ] W4 instructor SC panel + W5 real 10-round E2E, both shown in the §5.3
      walkthrough with captures.
- [ ] W6 fail-open hardening; W7 fail-closed prod secrets.
- [ ] W8–W10 (FX lifecycle / compliance / i18n) per spec, or explicitly deferred
      with sign-off; W11 deferred items listed, not silently skipped.
- [ ] `manage.py check` 0, migrations applied, ghost delta 0, `npm run build` clean.
- [ ] A completion note stating, per item, **what was observed** (not "wired up"),
      and honestly listing anything deferred.

---

*This audit changed no code. Unlike the GSCM audit, the finding here is largely
affirmative: globalstrat+ is an honest reflection of its directives; the work
remaining is genuine forward scope, hardening, and keeping the roadmap doc as
honest as the code already is.*
