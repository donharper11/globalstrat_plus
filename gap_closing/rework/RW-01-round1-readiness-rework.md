# GlobalStrat+ Round 1 Readiness — REWORK REQUIRED

**Date:** 2026-08-23
**Auditor:** independent (did not build any part of GSP-R1-01..R1-12)
**Subject:** GSP-R1-12 claim that "Round 1 technical readiness is now a PASS"
**Audited against:** `gap_closing/5_globalstrat_plus_gap_closing.md` exit criteria
**Repo state audited:** `main` @ `5d46d18`, verification game #19

---

## Verdict

**NOT A PASS. Two rework items.**

A PASS is a clean bill of health with no conditions attached. The GSP-R1-12 report is
accurate — every factual claim in it was independently verified and not one misstatement
was found — but two of the five exit criteria for the blocking finding (R1-09-F1) are not
actually satisfied by the evidence presented.

This is **not** a rejection of the work. The Vertex root cause is correct, the fix is real,
and the anomaly's specific signature is gone. What is missing is evidence for two criteria
that the rehearsal was not designed to exercise.

| Exit criterion (from the gap-closing report) | Status |
|---|---|
| Root cause identified and documented | **PASS** |
| Vertex-equivalent produces product-market rows with nonzero revenue | **PASS** |
| Leaderboard ranking reflects actual financial/market performance | **REWORK — RW-1** |
| Regression test added to prevent recurrence | **REWORK — RW-2** |
| Verified on fresh controlled game | **PASS** (game #19 is real and correctly processed) |

---

## Independently verified — do NOT redo this work

All of the following were checked against live systems, not read from the report.

| Claim | Verification method | Result |
|---|---|---|
| Commit `5d46d18` real, HEAD, pushed | `git log`, `git rev-parse` vs `origin/main` | Confirmed |
| `gap_closing/` preserved unchanged | `git status` — still untracked | Confirmed |
| 9 compliance/scoring tests pass | **Re-run WITHOUT `--keepdb`** (fresh test DB) | `Ran 9 tests ... OK` |
| Game #19 exists and was processed | Django ORM against live DB on .38 | Created 02:37:36 UTC |
| 4/4 teams locked | `DecisionSubmission.status` | All four `locked`, timestamped |
| Two product-market rows per team | `RoundResultProductMarket`, round 1 | Exactly 2 each |
| All teams positive revenue and PI | `RoundResultFinancials` / `...PerformanceIndex` | Confirmed |
| Workhorse/Vertex-equivalent $13.18M, PI 58.75 | ORM | Helix Digital, **exact** |
| Full results table (12 values) | ORM | **Matches the report to the cent** |
| Three nonzero adoption rows per team | `RoundResultAdoption` | Confirmed |
| Public site 200, backend + FRP active | curl, `pgrep`, public API path | frpc pid 920; 9 gunicorn workers |
| Deployed bundle == tested bundle | Live HTML vs report | Both `main.e6fdf1c6.js` |
| UI not shell-only / spinner-stuck | Drove the live site headless | Real login page, **0 console errors, 0 5xx** |

The report's disclosure that Zenith ranks 2nd despite leading revenue, with the PI-composite
explanation, is **correct and appropriately volunteered**. It is not a finding against it.

### Hypotheses tested and DISMISSED — do not re-investigate

1. *Three teams share identical revenue to the cent, so the demand engine may ignore team
   decisions.* **False.** Total adopters equal total units billed exactly (delta 0) for all
   four teams, and the Bass engine differentiates properly by segment — Helix wins Enterprise
   (5,074 adopters), Zenith wins Value Seekers (6,084). Identical totals follow from identical
   production volumes, which is correct behaviour.
2. *The UI was exercised against a locally served bundle, so it may differ from production.*
   **False.** The public site serves `main.e6fdf1c6.js`, exactly the bundle tested.

---

## RW-1 — The rehearsal cannot evidence "ranking reflects performance"

**Exit criterion:** *"Leaderboard ranking reflects actual financial/market performance."*

**Finding.** Game #19 cannot demonstrate this, because the four synthetic teams submitted a
near-identical decision set. Verified from `DecisionMarketing` for all 8 round-1 rows:

| Input | Solaris | Zenith | Helix | Cipher |
|---|---|---|---|---|
| promotion_budget | 300,000 | 300,000 | 300,000 | 300,000 |
| sales_team_count | 6 | 6 | 6 | 6 |
| distribution_investment | 150,000 | 150,000 | 150,000 | 150,000 |
| production_volume | 9,500 / 10,000 | 9,500 / 10,000 | 9,500 / 10,000 | 9,500 / 10,000 |
| retail_price | 999 / 699 | **1299 / 999** | 999 / 699 | 999 / 699 |

Price on one team is the only material variation. The consequences:

- Total PI spread across all four teams is **1.17 points** (58.37 – 59.54).
- The gap between 1st and 2nd is **0.02 points**.
- Three of four teams have byte-identical revenue ($13,184,400.00).

The GSP-R1-12 report discloses this as a "conservative, known-valid Round 1 decision pattern"
— that disclosure is honest — but it does not draw the consequence: **a run in which the
inputs barely differ cannot show that the ranking tracks performance.** It shows only that
near-identical inputs produce near-identical outputs. The one team that did differ materially
(Zenith: +35% revenue, +72% net income) ranks second, which the report explains via the PI
composite; that explanation may well be right, but a 0.02-point margin on a single
differentiated data point is not evidence for the criterion.

**Why it matters.** R1-09-F1 was raised precisely because a ranking did not reflect financial
reality. Closing it on a rehearsal that cannot distinguish good from bad performance leaves
the original risk unmeasured.

**Required work.** Run one further fresh controlled game with **materially differentiated**
strategies across the four teams — meaningfully different promotion budgets, retail prices,
production volumes and (ideally) market/segment focus, such that a reasonable person can state
in advance which team should perform best and why.

**Exit criteria for RW-1:**
1. Fresh game, four teams, Round 1 locked and processed with no errors.
2. Decision inputs differ materially across teams (documented as a table like the one above).
3. Resulting PI spread is wide enough to discriminate — state the spread; a sub-1-point spread
   across four deliberately divergent strategies is itself a finding to investigate.
4. The final ranking is accompanied by a written, defensible performance narrative: for each
   team, why its rank follows from its decisions and results.
5. No team with zero or negative revenue ranks above a team with positive revenue.
6. Results table captured in the handoff report as with GSP-R1-12.

---

## RW-2 — No regression test for the recurrence invariant

**Exit criterion:** *"Regression test added to prevent recurrence."*

**Finding.** Commit `5d46d18` (GSP-R1-12) adds **no test code at all** — it contains exactly
two Markdown files, 257 insertions. Verified with `git show --name-only`.

The report instead cites existing coverage in `CC18ComplianceTest`. That coverage is real and
passing, but it asserts the **cause**, not the **symptom invariant**. Precisely, the two
relevant tests assert:

- `test_freeze_blocks_customer_adoption_credit` — under a compliance freeze, `new_adopters`,
  `adjusted_fit_score` are zeroed and `best_product` is `None`.
- `test_performance_index_composite_rewards_financials_and_penalizes_freeze` — a team with
  $10M revenue / $3M net income scores above a peer with $2M / −$1M **with fit scores pinned
  equal at 0.7 for both**, and a freeze lowers a team's PI relative to its own unfrozen value.

Neither asserts the property that actually failed in game #17: **a team with zero revenue must
not outrank a team with positive revenue.** The PI test holds the market/fit components equal,
so it cannot catch a recurrence in which a non-financial component dominates — which is exactly
the shape of the original anomaly. A different route to the same symptom would pass silently.

**Required work.** Add a regression test that asserts the invariant directly, independent of
which mechanism produced it.

**Exit criteria for RW-2:**
1. A new test exists, committed with a `GSP-R1-*` reference.
2. It constructs (or processes) a round in which one team has zero revenue and at least one
   other has positive revenue, with the zero-revenue team given a **high** market/fit standing
   — i.e. it recreates the original anomaly's shape rather than a freeze-specific path.
3. It asserts the zero-revenue team does not rank above any positive-revenue team by PI.
4. It fails if the invariant is violated — demonstrate this by temporarily inverting the
   assertion or stubbing the guard, and record that the test actually fails in that state.
   A test that cannot be shown to fail is not a regression test.
5. Full `core.tests.test_cc18_compliance` suite still passes without `--keepdb`.

---

## Explicitly out of scope

- The Vertex root-cause analysis — accepted, correct.
- GSP-R1-10 and GSP-R1-11 implementation — accepted.
- `handoffs_v3/round1-live-rehearsal-protocol.md` — reviewed; substantive and operationally
  sound (preflight, lock gate, post-processing safety gate, monitoring, incident/rollback that
  correctly forbids reopening a processed round and bars `--flush`, row edits or a PostgreSQL
  restart without owner approval plus a verified backup). It remains a **platform-owner manual
  acceptance item** and is not affected by this rework.
- Game #19 itself — leave it intact as evidence; do not flush or delete it.

---

## Reproduction commands used by this audit

```bash
# Tests, fresh DB (NOT --keepdb, so schema drift cannot be masked)
cd ~/projects/globalstrat+/backend
python3 manage.py test core.tests.test_cc18_compliance --noinput

# Commit contents
git show --name-only --format="" 5d46d18

# Live results for game 19 (Django shell)
#   Team / RoundResultFinancials / RoundResultPerformanceIndex / RoundResultProductMarket
#   / RoundResultAdoption / DecisionSubmission / DecisionMarketing, filtered game_id=19

# Deployed bundle vs tested bundle
curl -s https://globalstrat.camdani.com/ | grep -oE 'main\.[a-z0-9]+\.js'
```

---

## Summary for the platform owner

The engineering is sound and the reporting is honest — notably more accurate than is typical.
Two criteria are unevidenced rather than failed. RW-2 is small (one test). RW-1 is one more
rehearsal run with divergent inputs. Once both land, Round 1 technical readiness can be signed
off as a genuine unconditional PASS.
