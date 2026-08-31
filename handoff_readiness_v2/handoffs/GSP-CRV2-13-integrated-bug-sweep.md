# GSP-CRV2-13 — Integrated bug sweep

**Observes:** `specs/STANDING-DISCIPLINE.md`, `handoffs/EXECUTION_PROTOCOL.md`
**Source:** `handoff_readiness_v2/RULES_AND_CALIBRATION_ASSESSMENT.md` Part D
**Owner:** QA engineer who implemented none of 10–12
**Sequence:** after 10, 11 and 12; before GSP-CRV2-09.

## Objective

Find the ordinary defects — the ones that are embarrassing on launch day because
they were always findable. The v2 programme has verified determinism,
concurrency, audit integrity, load and disputes. Those are the failure modes
someone reasoned about. This handoff looks for the ones nobody did.

Scoped deliberately: this is a **breadth** pass over the product as a student and
an instructor actually use it, not a re-run of any earlier handoff's depth.

## What this is not

Do not rerun CRV2-01's replay matrix, CRV2-02's race matrix, CRV2-03's provider
drills, CRV2-04's integrity evidence, CRV2-06's tournament or CRV2-07's load
profiles. Cite them. This handoff runs breadth over surfaces those handoffs
proved a property *about*, not the properties themselves.

## Stage 1 — reachability inventory

Build it from the registries, the way EXECUTION_PROTOCOL requires: `core/urls.py`
and the DRF router for endpoints, the frontend route table and navigation for
pages, the model registry for decision types. Not by grepping for what looks
important.

Map every row to: covered by an existing automated test / covered by this
sweep's walkthrough / deliberately out of scope with a reason. A page or endpoint
in none of those three is the finding this stage exists to produce. BECSR's
`handoffs_v1/REACHABILITY_REGISTER.md` is the format to follow.

## Stage 2 — the known list

Confirm and dispose of Part D. These were noticed while reading for other
things; none was searched for.

| # | Defect | Where |
|---|---|---|
| D1 | `end_of_round` product retirement sets `status='retired'` but never deactivates `TeamProductMarket`, unlike the `immediate` branch | `core/engine/rd_processing.py:334-338` |
| D2 | The budget-vs-cash rule is written three times; `:1015` includes `research_budget`, `:548` and `:888` do not | `core/views/decisions.py` |
| D3 | Platform creation is skipped when any non-retired platform of that generation exists, so a team can never rebuild after retiring one | `rd_processing.py:70-76`, `views/decisions.py:596-601` |
| D4 | `except Exception: pass` around the org-structure development-speed modifier — it can silently never apply | `rd_processing.py:83-95` |
| D5 | `for market_id, seg_state in context.segments.items()` — the dict is keyed by segment id (`engine/utils.py:305`). Cosmetic today; the name invites a real bug | `preference_engine.py:60` |
| D6 | Round-0 adoption uses an unexplained `* 10` scale factor | `bootstrap.py:175` |

D2 and D6 may be closed by CRV2-10 and 11 respectively; confirm rather than
assume, and record which handoff closed each.

## Stage 3 — student walkthrough

One seeded game, two teams, a full round cycle, on the integrated candidate.
Exercise every decision area the scenario exposes — R&D, platforms, products,
marketing, market entry, financing, communications, org structure, tax,
alliances, government relations, supply chain — through the browser, in both
languages.

For each: does it save, does it survive a reload, does it lock at the deadline,
does it appear in the results, does the number shown before submitting match the
number charged? Record console and network errors throughout; a clean network
tab is part of the pass.

Include the states that are usually skipped and usually broken: empty states, a
first-round team with no history, a team that submits nothing, a team that
submits everything at once, pagination boundaries, a slow connection, a session
that expires mid-edit, the browser back button after a lock.

## Stage 4 — instructor and operator walkthrough

Create a game, configure it, enrol students, assign teams, open a round, watch
the dashboard, close, process, correct, advance, complete. Then the reporting
surfaces: results, leaderboard, grading, exports, audit evidence.

Reuse GSP-CRV2-08's completed game where doing so does not hide the create/join
flows.

## Stage 5 — targeted classes

Cheap, high-yield, and none of them re-runs an earlier matrix:

- **Arithmetic presentation:** does every financial statement balance on screen?
  Do the totals sum? Do percentages sum to 100 where they should? Do rounding
  differences show up as a cent that does not reconcile?
- **Boundary rounds:** round 1 with no prior round; the final round; the
  transition into `completed`.
- **Empty and extreme scenario data:** a team with no products, a market with no
  presence, a segment with no matching product, a scenario config value absent.
- **Cross-team leakage:** confirm the CRV2-04 scope guard covers the surfaces
  added since it was certified. Cite CRV2-04 rather than reproducing it.
- **All three scenarios load and play**, not only consumer electronics. Two of
  the three have had far less traffic.
- **The N+1 and slow-page pass:** a page that takes eleven seconds under a
  loaded round is a launch-day defect even when it returns the right answer.

## Acceptance

- A reachability inventory in which every route and page is tested, covered or
  reasoned out.
- Every Part D item confirmed and closed, or withdrawn with the reason.
- Both walkthroughs complete in both languages with no unexplained console or
  network error.
- Every finding logged before repair, with ID, area, severity, reproduction and
  evidence, per the standing rule.
- P0 and P1 findings repaired and verified by a focused automated test that
  fails without the repair — a defect found by hand and fixed without a test is
  a defect that comes back.
- A list, in the completion report, of what this sweep did **not** cover.

## Evidence

`handoff_readiness_v2/evidence/bug-sweep/` — reachability inventory, walkthrough
records and captures, console/network logs, the findings register delta, and the
focused tests added.

## Verification budget

Focused tests and the two walkthroughs. No full backend suite — CRV2-09 owns the
single integrated regression, and it runs after this handoff. If a repair here
touches a boundary an earlier handoff certified, name it and run that boundary's
focused regression only.
