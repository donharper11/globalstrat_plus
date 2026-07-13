# Rework W5 — Real 10-round outcome-verification E2E

**Spec:** `rework/REWORK_SPEC_2026-07-13.md` §4 W5 · **Observes:** `STANDING-DISCIPLINE.md`, rework §5
**Status:** Complete — deterministic 10-round SC outcome verification, green.

## What the gap was
CC-22 (`test_cc22_e2e.py`) is a smoke-and-persistence test: it proves *one* round
advances without crashing and that decisions persist. Its own spec §2 advertises
"10 rounds with automated decisions + event injection + expected-outcome
verification." That was hedged as conditional (§2.11) because pre-CC-19 there
were no SC outputs to verify. CC-19/19B now produce them, so this closes the gap.

## What was built
New module `core/tests/test_cc22_multiround_e2e.py`. It drives the **real** SC
engine functions in their real pipeline order across **10 real `Round` rows**
for **two teams** with contrasting supply-chain postures, against the real
Consumer Electronics scenario loaded into the test DB:

- `run_sc_state` — fires the seeded **"Taiwan Earthquake — Semiconductor Capacity
  Shock"** SC event (forced to fire exactly once at round 5 via
  `probability_per_round=1`, `earliest_round=5`, `max_occurrences=1`) and carries
  the disruption's recovery forward across rounds via real `SupplierState`
  persistence;
- `calculate_revenue` — Channel-1 lost-sales throttle;
- `calculate_sc_disruption_costs` — Channel-2 real costs;
- `score_sc_resilience` — persists `ResilienceScoreHistory`.

**Fragile** team: 100% `tsmc_taiwan`, no contingency, thin buffer.
**Resilient** team: 50/50 `tsmc_taiwan`(TW) + `samsung_foundry_korea`(KR), deep
buffer, and a contingency rule rerouting disrupted semiconductor volume to Samsung.

## Observed outcome (the actual trajectory, `W5_TRACE=1`)

```
 round | fragile cf/lost/score              | resilient cf/lost/score
  R1   | cf=1.00 lost=$         0 score= 12.63 | cf=1.00 lost=$         0 score= 74.20
  R2   | cf=1.00 lost=$         0 score= 12.63 | cf=1.00 lost=$         0 score= 74.20
  R3   | cf=1.00 lost=$         0 score= 12.63 | cf=1.00 lost=$         0 score= 74.20
  R4   | cf=1.00 lost=$         0 score= 12.63 | cf=1.00 lost=$         0 score= 74.20
  R5   | cf=0.60 lost=$   160,000 score=  7.63 | cf=0.90 lost=$    40,000 score= 71.70  <-- SHOCK
  R6   | cf=0.60 lost=$   160,000 score=  7.63 | cf=0.90 lost=$    40,000 score= 71.70
  R7   | cf=0.60 lost=$   160,000 score=  7.63 | cf=0.90 lost=$    40,000 score= 71.70
  R8   | cf=0.60 lost=$   160,000 score=  7.63 | cf=0.90 lost=$    40,000 score= 71.70
  R9   | cf=1.00 lost=$         0 score= 12.63 | cf=1.00 lost=$         0 score= 74.20
  R10  | cf=1.00 lost=$         0 score= 12.63 | cf=1.00 lost=$         0 score= 74.20
```

Assertions (all pass):
1. **Baseline** — pre-shock (R1–4) both teams undisrupted (cf=1, lost=0).
2. **Resilience trend** — resilient out-scores fragile **every** round (74.2 vs 12.6 baseline; 71.7 vs 7.6 under shock).
3. **Lost sales on disruption** — R5 fragile cf→0.60, $160k lost; resilient cf only 0.90, $40k lost (50% healthy KR source + 50% reroute).
4. **Recovery** — disruption persists through the event's recovery window (R5–R8), then capacity and lost-sales return to baseline at R9 (real `run_sc_state` recovery carry-forward).
5. **Determinism** — an identical parallel game reproduces the score and capacity trajectories exactly.

## Commands
```
$ python3 manage.py test core.tests.test_cc22_multiround_e2e --noinput
Ran 1 test in ~5.5s
OK
```

## Honest scope note
This harness runs the SC engine steps against real DB state, so multi-round
recovery carry-forward is genuinely exercised. It seeds adoption results rather
than also running the full adoption/financials pipeline — W5 is about SC
*outcomes* (resilience trends, lost sales, recovery), and the whole-engine
advance-round path is already covered by the CC-22 advance smoke test
(`test_cc22_e2e.py::test_07`).
