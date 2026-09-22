# R47 — compliance investment is charged from cash, 2026-09-22

**Branch:** `crv2-11-compliance-investment-charge`, cut from
`crv2-release-integration` at `90b2dea` (verified an ancestor before anything
was touched). **Final runtime commit `ee94c37`**; the full suite ran at
`1f0c5e4`, which differs from it only by evidence files.
**Observes:** `specs/STANDING-DISCIPLINE.md`,
`handoff_readiness_v2/handoffs/EXECUTION_PROTOCOL.md`, owner ruling R47 as
recorded in `OWNER_RULINGS_2026-09-22.md`, and the owner's amendment relayed
during the build ("Show its own line on the income statement").
**Precedents followed:** R36 (`R18_R36_ENGINE_2026-09-17.md`) and R23.

**No gate is claimed closed by this document.** `V2_FINDINGS_REGISTER.md`,
`LAUNCH_CHECKLIST_V2.md` and every `OWNER_RULINGS` file were left untouched;
§10 proposes register text.

Commits, oldest first:

| Commit | What |
|---|---|
| `3d61540` | The charge: `funding_need.compliance_investment_total`, both calculators, the widened parity assertion, committed spend, the two participant surfaces, tax; `core/tests/test_compliance_investment_charge.py` (14 tests) |
| `3020eaa` | `determinism_fixture.py --no-compliance-investment` and a per-round `compliance_rows=` figure |
| `1566c40` | Replay evidence at `3020eaa` (superseded by `1f0c5e4`, kept in history) |
| `ee94c37` | The two first-full-suite findings, both mine (§6) |
| `1f0c5e4` | Replay evidence re-taken at `ee94c37` |
| *(next)* | This document |
| *(last)* | Regenerated string inventory, alone |

---

## 0. MISMATCH DETECTED — read this first

```
Spec reference: R47 amendment, owner's words: "Show its own line on the
                income statement." The relay asks for a distinct
                compliance_expense key in context.opex, its own row in the
                financial statements (financials.py) and wherever statements
                are rendered, in tax deductions and in committed spend.
                Same brief: "MANIFEST_SCHEMA_VERSION must stay 6; you are
                changing values, not the shape of a hashed section."
Actual state:   The income statement a student or instructor reads is
                RoundResultFinancials, rendered by results_api /
                FinancialReportsPage. It has no compliance column. It is the
                hashed `financials` output section (manifest_sections.py:493).
                manifest_version.py's own rule -- "bump whenever the reviewed
                inventory changes what bytes a round hashes to", with 2 -> 3
                cited for exactly this case, "the platform_switch_write_off
                financial line" -- makes a new column there schema version 7,
                with a migration, manifest_schema_v7.json, a PROVENANCE entry
                and test_checked_in_inventory_matches_the_live_registry all
                moving. A new zero-valued field in every financials row also
                changes every round's bytes, so the control replay the brief
                demands (a round with the lever unused hashing the same as at
                90b2dea) is impossible by construction under v7, and
                require_schema_version refuses a cross-version comparison.
Location:       backend/core/models/results_financials.py:40-66;
                backend/core/services/manifest_version.py:9-23;
                backend/core/engine/financials.py:95-118, 382.
Proposed action: The owner chooses one of two, and it is not mine to choose:
                (a) its own stored column under schema v7 -- the ruling as
                    worded, at the cost of every stored replay comparison
                    across the bump and one more version to interpret; or
                (b) its own line everywhere the envelope is not touched
                    (engine, tax, committed spend, the pre-lock surfaces),
                    carried inside strategy_expense on the stored statement
                    under v6 -- the brief's constraint as worded.
                Built here: (b), with the fold at exactly one site
                (financials.py:382) so (a) is one column, that line and the
                v7 procedure away. Halting on the stored column only.
```

Everything else in the brief is built and proven. What "its own line" means on each surface, as it stands at `ee94c37`:

| Surface | Own line? | Where |
|---|---|---|
| Engine opex record `context.opex[team]` | **yes** — `compliance_expense`, its own key, never added into `strategy_expense` there | `costs.py` |
| `funding_need.decision_outlays` | **yes** — `compliance` | `funding_need.py` |
| Committed spend `rd_costs.committed_outlay` / `budget_assessment` | **yes** — `lines['compliance_investment']`, inside `committed_total` | `rd_costs.py` |
| Decision Summary `budget_summary`, Finance context `budget_status` | **yes** — `compliance_committed`, beside `platform_development_committed`; `committed_total`, `unallocated` and `projected_ending_cash` carry it | `views/decisions.py` |
| Tax deductions `calculate_tax.total_opex` | **yes** — its own term | `costs.py` |
| `financials.py` totals: `total_opex`, operating income, net income, cash | **yes** — its own variable and its own term | `financials.py:108,121` |
| **Stored statement `RoundResultFinancials`** | **no** — inside `strategy_expense` (§0) | `financials.py:382` |
| **Student/instructor statement pages, exports** | **no** — they render the stored row, which has no such column; the R23 precedent (`research_expense`) has a column but `FinancialReportsPage.js:884` does not render it either | `results_api.py`, `FinancialReportsPage.js` |
| Lock refusal sentence | inside the committed total it names — the existing `committed_spend_exceeds_cash`, no new sentence (§4) | `rd_costs.describe_budget_problems` |

## 1. State at head (`90b2dea`)

`ComplianceInvestment` (`cc31_models.py:147`; `submission`, `market`,
`investment_amount`, unique per submission and market) is written by the
per-type route `compliance-investments` (V2-137's repair, `_TYPE_MAP` at
`views/decisions.py:500`) and by the whole-submission route, both through
`validate_compliance_investments`. `strategy_effects._process_compliance`
reads it and raises `TeamMarketCompliance.compliance_level`. The amount was
charged nowhere: `decision_outlays` had eight lines and none was compliance;
`calculate_operating_expenses` booked `rd`, `platform_capex`, `marketing`,
`research` and `org_transition` and asserted parity over those five; the
only "compliance" cost in the engine was CC-18 detentions from
`compliance_engine`. `compliance_investment` was already a hashed **input**
section (`manifest_sections.py:371`), confirmed at head — nothing new enters
the envelope from this build.

Red, mechanically: the test file alone against `90b2dea` fails at import —
`cannot import name 'compliance_investment_total' from
'core.services.funding_need'` (4.2 s). That is the finding stated as code:
at head, no calculator has the function.

## 2. Design

**One function.** `funding_need.compliance_investment_total(submission)`,
placed beside `org_transition_charge` in the module `test_manifest_determinism`
already scans as a resolution service (a new service module would have
failed `test_the_scanned_service_list_is_what_the_engine_actually_calls`).
It sums `investment_amount` over the submission's rows in `id` order. No
price is invented and no scenario data is read: the row *is* the decision, so
the charge and the decision cannot disagree, a round with no rows costs
nothing, and re-resolving recomputes the same amount rather than a
cumulative one.

**Both calculators, one assertion.** `decision_outlays` gains
`lines['compliance']` from it, after the submission guard, beside `research`
(a compliance row cannot exist without a submission, unlike R36's structure
switch, so the guard placement matches R23 rather than R36).
`calculate_operating_expenses` reads the same function into
`compliance_expense`, and the parity assertion is widened:

```python
_shared = (_outlays['rd'] + _outlays['platform_capex']
           + _outlays['marketing'] + _outlays['research']
           + _outlays['org_structure'] + _outlays['compliance'])
_engine = (rd_expense + platform_capex + marketing_expense
           + research_expense + org_transition
           + compliance_expense)
```

**The line chosen, and why.** In the engine and every calculator it is its
own line, `compliance_expense` / `compliance` / `compliance_investment` /
`compliance_committed`, per the owner's amendment. On the stored statement it
is carried inside `strategy_expense`, at one site, for the reason in §0 —
compliance investment is a market-strategy decision made on the Market
Strategy page beside market entry and partnerships, which are the other
components of that stored line, so the holding position is at least the
right neighbour. `total_opex`, operating income, net income and closing cash
include it; `calculate_tax` deducts it as its own term. The fold is the only
thing that changes when the owner decides §0.

**Committed spend.** `rd_costs.committed_outlay` gains
`lines['compliance_investment']` in the position `research_purchases` and
`org_transition` occupy, and `budget_assessment` adds it to `committed_total`.
Both participant surfaces V2-057 holds equal publish it separately as
`compliance_committed`; `total_allocated` (the budget declarations) is
deliberately unchanged, as R23 and R36 left it.

**Cash and the equity rule.** Because the line is in `committed_total`, the
lock validator's `committed_spend_exceeds_cash` refusal, the Summary's
`lock_blockers`, the Finance context's `projected_ending_cash` and
`unallocated` all see it (`test_the_summary_and_finance_context_agree_with_the_refusal`);
because it is in `decision_outlays`, V2-024's `eligible_uses` and
`maximum_new_equity` see it (`test_the_equity_funding_rule_counts_it`: with
$1,500,000 invested against $1,000,000 cash, the team may raise exactly
$500,000).

**No new sentence.** The existing refusal names the committed total and the
cash; it did not name research purchases or the structure switch either and
was accepted for both. No catalogue entry, no zh-CN sentence, no frontend
change, no computed `t()` key. The frontend's BudgetBar shows the charge
through `unallocated`; `compliance_committed` is in both payloads for a page
to render when GSP-CRV2-12 decides how, exactly as
`platform_development_committed` waits today.

**Determinism.** `MANIFEST_SCHEMA_VERSION` stays **6** (`manifest_version.py`
untouched, `git diff --stat 90b2dea..HEAD` lists it not).
`test_checked_in_inventory_matches_the_live_registry` passes, which is the
independent proof that no hashed field was added or reclassified.

## 3. Tests: red, then green, then falsified

`core.tests.test_compliance_investment_charge`, 14 tests on
`build_minimal_game` with a JWT student, both markets active for both teams
so the rival is the control in a resolved round: `OneCalculatorTests` (6,
including the tax deduction), `CommittedSpendTests` (3),
`AffordabilityTests` (3, `en` and `zh-CN`), `ResolvedRoundTests` (2,
`process_round`, charged team versus control team: `strategy_expense`,
`net_income`, `cash_closing` and `Team.cash_on_hand` all differ by exactly
the investment, and by nothing when nothing is saved).

| Variant | Result |
|---|---|
| Tests only, at `90b2dea` | `FAILED (errors=1)`, `ImportError` — 4.2 s |
| First green attempt | 13 of 14; the 14th asked the minimal fixture to lock, which it refuses on portfolio/marketing/strategy items unrelated to cash. Rewritten as the control it should have been: an affordable investment draws no cash sentence — 12.7 s |
| Green | 14 OK inside 303 OK (§5 row 2) |
| **F1** — engine side only removed (`compliance_expense = D('0')` in `costs.py`) | `FAILED (failures=3)`: `test_the_charge_appears_in_both_calculators` and `test_the_statement_and_cash_carry_the_charge` stop with **`AssertionError: funding_need.decision_outlays disagrees with the cost engine … shared 600000.00 vs engine 0`**; `test_the_parity_assertion_covers_the_new_line` fails `AssertionError not raised` (its patch now matches the broken engine). The round stops, which is the point. |
| **F2** — both sides removed | `FAILED (failures=4)`: no assertion fires and no charge lands — `Decimal('0') != Decimal('600000')` in both calculators and the funding rule, `Decimal('0.00') != Decimal('600000')` on the resolved statement. |

Both falsifications restored with `git checkout HEAD -- <paths>`; the tree at
`3d61540` afterwards was clean.

## 4. Cash: a team cannot commit what it cannot fund

`test_the_lock_is_refused_and_nothing_is_locked`: $1,500,000 saved through
the real route against $1,000,000 cash, `POST …/lock/` in `en` and `zh-CN`
→ 400 carrying `participant_message('committed_spend_exceeds_cash', …)`
rendered with `$1,500,000.00` / `$1,000,000.00`; the submission stays
`draft` and cash stays $1,000,000. The Summary's `lock_blockers` carry the
same sentence; `budget_summary.committed_total`, `compliance_committed`
(1,500,000.0) and `unallocated` (−500,000.0) agree with `budget_status`'s
`committed_total`, `compliance_committed`, `projected_ending_cash` and
`unallocated` on the Finance context (V2-057's three surfaces).

## 5. Commands, results, durations

Every backend run: `cd backend && flock -w 1800
/tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>`, each on
its own disposable `postgres:16-alpine` container. The production database
at `192.168.50.38` was never contacted; `/etc/globalstrat-plus.env` was never
read. One agent, one lock, strictly sequential.

| # | Command | Result | Wall |
|---|---|---|---|
| 1 | `test_compliance_investment_charge` at `90b2dea` (red) | errors=1, ImportError | 4.2 s |
| 2 | `test_compliance_investment_charge test_org_transition_charge test_paid_research test_funding_need test_rd_costs test_silent_section_saves test_scoring_dispositions test_equity_issuance test_decision_limits test_engine test_manifest_determinism test_calibration --parallel 8` | **303 OK** | 43.9 s |
| F1 | `test_compliance_investment_charge`, engine side removed | failures=3 | 12.7 s |
| F2 | same, both sides removed | failures=4 | 13.5 s |
| 3 | **`core --parallel 8` (first freeze candidate, at `1566c40`)** | **1503 run, failures=1, errors=1** (§6) | 2 m 04.7 s |
| 4 | `test_determinism_fixture_runnable test_audit_integrity test_compliance_investment_charge --parallel 8` after `ee94c37` | 78 OK | 42.2 s |
| 5 | **`core --parallel 8` (second freeze candidate, at `1f0c5e4`, runtime = `ee94c37`)** | **1503 OK, exit 0** — started 2026-09-22 14:12:51 UTC | 2 m 08.7 s |
| 6 | `python3 backend/scripts/check-participant-strings` | PASS, 5216 units, 0 findings | — |
| 7 | `git diff --check` | clean | — |
| 8 | `manage.py dump_read_inventory --check` | "Read inventory is current." | — |
| 9 | `generate_inventory.py --check` at `1f0c5e4` | stale — line numbers and source fingerprint only, no new player-facing string; regenerated in the last commit | — |

**The full suite ran twice, against the budget of one, because the first
freeze candidate genuinely failed (§6).** No runtime code changed after run 5
began.

Line endings: every touched file is LF and stays LF.

## 6. The two first-full-suite failures — both mine

1. **`test_audit_integrity.SensitiveReadInventoryTests.test_the_checked_in_inventory_matches_the_live_url_conf`** —
   `dump_read_inventory --check` reported `read_inventory.json` out of date.
   Regenerating it showed one added model name, `Decision`, on the Finance
   context route. `read_inventory.py:87` word-matches every registered
   decision model name — including the legacy `programs.Decision` — against
   a view's source text, comments included. My comment
   `# R47: as on the Decision Summary.` in `views/decisions.py` was taken
   as a read of that model. Reworded to
   `# R47: the same figure the summary endpoint publishes.`; the checked-in
   inventory restored unchanged; `--check` current. Not a runtime behaviour
   change, but a runtime file, so the freeze moved and the suite was re-run.
2. **`test_determinism_fixture_runnable.DeterminismFixtureIsRunnableAtHead.test_platform_development_is_seeded_only_where_the_rules_allow`** —
   `(0, 5) != 0`. My fixture flag had made `seed_round` return a tuple; the
   V2-116 test expects the development count. It returns the count again and
   `main` counts compliance rows from the table.

Neither is a pre-existing defect and neither was papered over.

## 7. Replay evidence — `evidence/determinism/r47-compliance-charge/`

Disposable stack: container `globalstrat-r47-replay-pg`, databases
`globalstrat_r47` / `globalstrat_r47_control`, `COMPETITION_BACKUP_DIR` in
the session scratchpad (`require_disposable_backup_dir` accepted it),
`--phase2-timeout` default, LLM endpoint `127.0.0.1:9` (unreachable, as run C
of CRV2-01). The base tree is `git archive 90b2dea` with `GIT_REVISION` set.
`pg_dump`/`pg_restore` 18.3 against server 16 — client newer, the direction
`competition_backup._restore_stderr_is_benign` already handles; §1.9's hazard
is the reverse.

| Run | Recorded at | Replayed at | Lever | Competitive hash | Result |
|---|---|---|---|---|---|
| 1 | `ee94c37` | `ee94c37` | used, `compliance_rows=5` | `17f1f48d877b9273a7b561bc04eb25400da53cb68b1822bfe2dfd8de3e51db47` | exact, exit 0 |
| 2 control | **`90b2dea`** | `ee94c37`, `--allow-source-mismatch` | unused, `compliance_rows=0` | `763b827b089e161164f71b54346bc42b3433b1acb7bf17d8f825eb42bd8715aa` | exact, exit 0 |
| 3 negative | `ee94c37` | **`90b2dea`**, `--allow-source-mismatch` | used (run 1's backup) | expected `17f1f48d…`, actual `2fcac81cdbdd112dee39e2242474dde75bb58ad868a25e7011bf56aabdb6105b` | differs, exit 3 |

Source digests `861fafdf01f0e048b3b34b349c73b4b71ddf18ebde4398f61f3ec2d6489047c8`
(`ee94c37`, 457 files) and `51725d6aafd2463e9cb6f9a061ad5f22c5e7ae9298e76ff500947ac7be9e2a3e`
(`90b2dea`). Run 3's section diff is exactly the charge: `team.cash_on_hand`
and `total_equity` lower by `400000` / `400000` / `200000` for the three
investing teams, unchanged for the fourth, with `financials`,
`market_revenue`, `performance`, `share_price`, `leaderboard`, `coherence`
and `ai_investor_holding` moving as consequences. The same three runs taken
first at `3020eaa` (`1566c40`) showed identical per-team figures; the hashes
differ across takes only because each recording is a fresh game whose name
and team names sit in every natural-key token.

Phase 2 reached the Qdrant host `192.168.50.186` (vector search, outside the
competitive hash and not the production database).

## 8. What this invalidates

- **Any stored replay for a round carrying a `ComplianceInvestment` row**:
  run 3 shows such a round hashes differently under this engine. By V2-137
  there is no such round anywhere.
- **Nothing for rounds without one**: run 2 is the proof, at the base
  commit's own hash.
- **Balance evidence**: the silent-saves record (§6 there) named a free
  $10,000,000-per-market lever; it now costs its face value from cash. Every
  playthrough to date was played with the lever at zero for every team, so
  none is contradicted; none covers the lever priced.
- **`evidence/adversarial-balance` and V2-057's cell wording** that list
  the committed-spend lines: one more line, `compliance_investment`.
- **`1566c40`'s evidence** is superseded by `1f0c5e4` (same findings, final
  commit).

## 9. zh-CN

No new sentence. `FIELD_LABELS.investment_amount` (`compliance investment` /
`合规投入`) already exists and is unused by this build. `test_zh_terminology`
is inside the full run.

## 10. Proposed register text (for the auditor to apply or reject)

**R47 row (rulings table):** *Compliance investment costs money, charged
from cash at resolution.* Implemented at `ee94c37`, pending closure and
**pending one owner decision** (§0): its own stored statement column under
schema v7, or its own line everywhere except the stored `financials` row
under v6. Built as the latter.

**Status cell for the silent-saves P0 (compliance-lever paragraph):**
> **Status update 2026-09-22 — R47 implemented at `ee94c37`, pending
> closure.** `funding_need.compliance_investment_total` sums the team's
> saved rows; `decision_outlays` (`compliance`), the engine
> (`compliance_expense`, its own `context.opex` line), `committed_outlay`
> (`compliance_investment`) and both participant surfaces
> (`compliance_committed`, inside `committed_total`) read it, and the
> V2-024 parity assertion is widened over it — with the engine side alone
> removed the round stops (`shared 600000.00 vs engine 0`), with both removed
> four tests fail on the missing charge. A team cannot lock more than it can
> fund through the existing `committed_spend_exceeds_cash` refusal, in both
> languages, and the equity rule counts it as an eligible use. Deducted for
> tax. `MANIFEST_SCHEMA_VERSION` stays 6; replay at the R47 commit is exact
> for a round with five investment rows, a base-recorded round with none
> replays to its own hash at the R47 commit, and the charged round replayed
> at the base tree differs by exactly each team's investment. **Open:** the
> owner's amendment ("its own line on the income statement") requires a new
> column on the hashed `financials` section and therefore schema v7; the
> stored statement carries the amount inside `strategy_expense` at one
> documented site until the owner rules on the bump.

## 11. What a reviewer should distrust

Only what I could not resolve here:

1. **The stored-statement line (§0)** — needs the owner: v7 with its own
   column, or v6 with the fold. I built one and named the other; I did not
   choose.
2. **No browser.** No page changed, so nothing was clicked; the pre-lock
   figure a student sees is `unallocated` on BudgetBar and the refusal
   sentence, asserted through the API only.
3. **Whether `compliance_committed` should be rendered as its own row on the
   Summary and Finance pages, and under which label** — a GSP-CRV2-12 wording
   decision; the payload carries it, no page reads it.


---

## 12. The mismatch resolved — own column, envelope v7 (2026-09-22, integrator)

The owner's ruling won over the brief's "stay at v6", which was the
integrator's constraint and not the owner's. The builder's session was killed
twice by API errors while doing this; its uncommitted work was committed as
`58d150b` and finished by the integrator.

**What changed.** `compliance_expense` column on `RoundResultFinancials`
(`0089`, default 0, no existing migration altered); no longer folded into
`strategy_expense` anywhere; `MANIFEST_SCHEMA_VERSION` 6 → 7 with a history line
and `manifest_schema_v7.json` + `PROVENANCE.json`; the row rendered on the
statement students and instructors read (`FinancialReportsPage.js` through the
new `incomeStatementRows.js`, "Compliance investment" / 合规投入 via the
catalogues, and `research_expense` rendered too — it had a column since v6 and
was never shown, recorded here as a defect and repaired in the same pattern);
`DETERMINISM_BOUNDARY.md` updated.

**Two test findings, both test-side.** (1) `test_ledger_rows_exist_at_the_team_ids_that_used_to_freeze_them`
forced the team sequence to 135 after its own `setUp` had built a fixture game;
R47's new tests moved the count so that setUp's teams sat on 135–137 and the
insert collided. It now takes the lowest free triple at or above 135 whose three
UFLPA draws all fall under 0.15, and asserts that premise. (2) The string
inventory was stale; regenerated in its own commit.

**Runs.** Focused batch 240 → 1 error (the test above) → fixed → 78 OK on the
two modules together. **Full backend suite: `Ran 1506 tests`, OK, 116 s.** Full
Jest: 27 suites / 296 tests. Inventory `--check` clean. Replay evidence in §7's
README, v7 section: charged round `95c85bc7fd3a…` exact; control `520a1a6fdd32…`
exact; a v6 recording is **refused** under v7 (exit 1), which is the version
rule doing its job. The replay gate's refusal wording said "version-1" whatever
the versions; repaired after the full run above, so the certifying full run is
the one on the merged integration tree.

**Production.** `manage.py migrate core 0089` joins the `0088` maintenance
action already on the launch checklist; it adds a column, no privilege change.

**Unresolved, genuinely.** The Summary/Finance pages carry `compliance_committed`
in their payload but no row reads it (a CRV2-12 wording decision); no browser
pass; 合规投入 unreviewed by a native speaker.
