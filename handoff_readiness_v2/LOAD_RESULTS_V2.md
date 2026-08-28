# V2 load result against a named field

Modelled field: **24 teams**, **4 members/team**, up to **96 authenticated
sessions**, final-60-second saves, active refreshes, and operator resolution.

Existing evidence at 96 requests/concurrency 24 accepted and audited 86/86,
uniformly rejected 10/10 in flight at close, locked 24/24, and measured p50 643
ms, p95 913 ms, p99 1,608 ms. At 288/concurrency 72 it accepted/audited
259/259, rejected 29/29 uniformly, locked 24/24, and measured p50 2,127 ms,
p95 2,452 ms, p99 2,473 ms. No payload was lost or duplicated
(`handoff_readiness/evidence/deadline-*.json`).

Degradation is visible at 3× (p95 2.7× baseline), while correctness holds. This
is not a ceiling. The run did not combine 96 distinct sessions, slow refreshes
and resolution, so the actual failure point/mode is unknown. V2-D is **BLOCKED**.
