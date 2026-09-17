# R32 — the inactivity control enforces on the standings, not the carried index

**Ruling:** R32, competition owner, 2026-09-17 (`OWNER_RULINGS_2026-09-17.md`).
**Finding:** V2-119, question 1. Question 2 is untouched and stays open.
**Branch:** `crv2-11-inactivity-guard-rank-only`, from `main` at `0fd9a39`.
**Builder:** engine owner. **No gate is claimed closed.**

---

## 1. What changed, and where enforcement now lives

The rule is unchanged: **a commercially inactive firm must not finish above a
firm that competed.** What changed is where it is enforced.

| | Before | After |
|---|---|---|
| Control | `performance.py::_enforce_inactive_revenue_invariant` | the published sort key in `leaderboard.py::update_leaderboard` |
| Mechanism | replaced the firm's **carried index** with `min(active indexes) − 0.01` | a **competed flag leads the published key**, so no index or tie-break can lift an inactive firm above an active one |
| Severity | unbounded; scaled with how far the firm had climbed | none — the index is not touched at all |
| Round-level cost of not competing | composite cap (−5.00) **plus** the rewrite | composite cap (−5.00), and only that |

**Why the standings and not a capped index change.** The ruling says enforce on
the standings. A finishing order is decided in exactly one place in this
codebase — `update_leaderboard`'s `published_key` — and that key already
carries the published competition tie-break (cumulative operating cash flow,
cumulative revenue, then this round's resilience). Putting the flag at the head
of that same key means there is still **one** notion of rank: the demotion is
not a second sort layered on top, it is the first element of the existing one.
Capping the index change instead would have kept the enforcement in the score,
which is what the ruling moved away from.

The flag leads the key, so the property holds **totally**, not pairwise: every
active firm outranks every inactive firm regardless of index spread. Because the
shared-rank test compares whole keys, an inactive firm cannot even finish
*level* with an active one — consistent with the old control, which placed it
strictly below (`− 0.01`).

**One classification, still shared.** `is_commercially_inactive` and
`material_revenue_floor` are untouched. The performance step now publishes the
result as `context.commercially_inactive_team_ids` (a `frozenset`), declared on
`RoundContext`, and the standings only *read* it. The two controls consume one
computation, so they cannot disagree about who was competing — which is what
V2-022 adopted. A context that never ran the performance step carries an empty
set and demotes nobody; that is `bootstrap_round_zero`, which ranks before any
round is played and where R22 requires a shared opening rank.

Files: `backend/core/engine/performance.py`, `backend/core/engine/leaderboard.py`,
`backend/core/engine/utils.py` (the `RoundContext` declaration).

---

## 2. The invariants the handoff said not to weaken

**(a) An inactive firm still cannot outrank one that competed.** Proven on the
standings, which is where "finish above" is decided —
`InactiveFirmNeverOutranksAnActiveOne` in
`backend/core/tests/test_inactivity_rank_guard.py`: a firm carrying 90.00 that
did not compete ranks below one carrying 60.00 that did; in a six-firm field
with **interleaved** indexes (95/80/70/65/50/10) the three active firms take
ranks 1–3 and the three inactive take 4–6; and with every published criterion
equal the inactive firm does not even share the rank. Against the unmodified
engine the six-firm case failed with *"6 not less than 1 — a firm that did not
compete finished above one that did"*.

`test_cc18_compliance.py::test_zero_revenue_high_fit_team_cannot_outrank_positive_revenue_team`
(GSP-R1-13, the Game 17 anomaly) previously asserted this property on
`index_value`, because the old control enforced it by rewriting that value. It
now asserts it on `LeaderboardEntry.rank` **and** additionally asserts the
round cost is the bounded cap. The Game 17 anomaly was a *leaderboard* anomaly,
so this is the assertion the test always wanted. This is a relocation of the
assertion, not a relaxation — stated plainly because it is a test I changed.

**(b) The composite cap is exactly as authored.** `COMMERCIAL_INACTIVITY_COMPOSITE_CAP
= 0.25` and its application site are untouched by this diff.
`test_the_composite_cap_still_applies_its_bounded_five_points` holds
`satisfaction_score == 0.25`, `index_change == −5.00`, `index_value == 95.00`;
the pre-existing `test_voluntary_commercial_inactivity_caps_composite`
(GSP-R1-15) still passes unmodified.

**(c) The classification is unchanged and still shared.** No edit to
`material_revenue_floor` or `is_commercially_inactive`; all of
`MaterialRevenueFloorTests` passes unmodified.
`test_the_scored_index_and_the_standings_agree_on_who_competed` proves both
controls act on the same team set in one round, and
`SharedClassificationTests` now guards structurally that the standings read the
shared classification rather than re-deriving one from revenue.

**(d) Insertion-order invariance (V2-012).** The old guard computed
`min(active_indexes)` *before* mutating, then mutated inside the same loop.
The replacement mutates nothing and derives from a set-membership test, so the
trap is gone by construction. Held by `StandingsAreInsertionOrderInvariant`
(reversing the team order changes no rank; building the inactive set in either
order changes no rank) and, end to end, by the pre-existing
`test_row_insertion_order_does_not_change_the_competitive_hash`, which replays
the whole Phase-1 pipeline over reordered rows and still passes.

**Ordering scan / `RESOLUTION_SERVICES`.** Nothing needs adding.
`leaderboard.py` and `performance.py` are under `ENGINE_ROOT` and are already
swept by `test_every_iterated_queryset_declares_its_order`; this change adds no
queryset and no loop over one. `RESOLUTION_SERVICES` scopes `core/services`,
and this change imports no new service —
`test_the_scanned_service_list_is_what_the_engine_actually_calls` (the test that
caught `price_band.py`) passes, which is what proves the scope still follows the
code. The `ORDER_EXEMPT` entry for `leaderboard.py`'s
`RoundResultFinancials.objects.filter` aggregate is untouched and still
reachable.

---

## 3. The 17.81-versus-5.00 event, before and after

The red run of the new tests against the **unmodified** engine reproduces the
mechanism exactly and measures the severity curve directly. Identical event
(a firm classified commercially inactive), varying only the index it carried:

| carried index | old cost | new cost |
|---:|---:|---:|
| 20.00 | −5.00 | −5.00 |
| 55.00 | **−7.16** | −5.00 |
| 70.43 | **−22.59** | −5.00 |
| 120.00 | **−72.16** | −5.00 |

That is the ruling's objection in one table: under the old control the cost of
one identical event was a function of how well the team had been playing. The
mechanism is confirmed to the cent —
`test_the_carried_index_is_never_replaced_by_the_weakest_active_rival` failed
on the old code with `Decimal('33.84') == Decimal('33.84')`, i.e. the inactive
firm's index landing exactly on `min(active) − 0.01`.

On the recorded Green Pioneer shape (carried **70.43**, weakest active rival
carrying 52.63), the old code produced **55.47** and the new code produces
**65.43 (−5.00)**, matching the −5.00 the `ZERO_PRODUCTION_DEFECT_2026-09-12.md`
report projected for the post-repair field.

**Honest limit on this reproduction.** The register's **−17.81** is from the
8-team, 10-round fixed-policy replay (`r28_eight_profile_balance.json`, name
seed `20260912`), where the ceiling was set by that field's own active firms.
My fixture is a synthetic three-firm field, so the same mechanism yields
**−14.96** rather than −17.81. **I did not re-run the 8-team replay** — it is
release-scale evidence, which `EXECUTION_PROTOCOL` Phase 2 keeps out of the
development loop, and the integrated regeneration belongs to GSP-CRV2-09. What
is proven here is the mechanism and the severity curve, not a byte-identical
reproduction of that replay.

---

## 4. Stored values that change, and evidence that invalidates

**Stored values.**

- `team.performance_index` and `round_result_performance_index.index_value` /
  `index_change` — for a commercially inactive firm whose index sat at or above
  the weakest active firm's, these no longer collapse to `min(active) − 0.01`.
  They are now `previous + index_change`, with `index_change` bounded by the
  composite cap. This also ends the carried-state consequence the earlier report
  flagged: the rewrite was the base every later round accumulated from, so it
  cost the game rather than the round.
- `leaderboard_entry.rank` — an inactive firm is now demoted explicitly. Before,
  it was demoted implicitly, because its index had already been rewritten.
- `leaderboard_entry.performance_index` — now publishes the carried index.

**The competitive hash.** `performance` and `leaderboard` are both manifest
**output** sections, so `output_sha256` moves for any round in which the old
control would have fired. Per the 2026-09-16 measurement the control has
**never fired in stored play** (448 index rows, worst `index_change` −5.82,
none at or below −10), so no stored round's hash is expected to move on value
grounds. That is a prophylactic change, and known to be one.

**Evidence this invalidates.**

1. **All of it, on identity grounds.** This commit changes files under
   `backend/`, so `source_tree_sha256` changes. Per `DETERMINISM_BOUNDARY.md`
   every replay artifact is bound to its own commit and source digest — CRV2-01's
   four-environment replay covers **its** commit, not this one. Earlier replay
   evidence is an immutable record of its own revision.
2. **V2-110 Part D / R28's eight-profile replay.** Its recorded trajectories for
   the four collapse rounds are no longer reproducible under this commit: the
   −17.81 / −17.31 / −13.60 events become −5.00. `r28_eight_profile_balance.json`
   and the tables quoting those figures are now historical records of the old
   control, not predictions of current behaviour.
3. **`evidence/player-language/STATIC_STRING_INVENTORY.md:852`** catalogues the
   participant-facing string `"; zero-revenue ranking guard applied"` at
   `performance.py:398`. That string is removed; a new, clearer line is appended
   by the standings instead. **That inventory row is stale and needs re-cutting**
   — I did not edit the inventory.
4. `evidence/adversarial-balance/harness/rule_probe_body.py` refers to
   `_enforce_zero_revenue_invariant`; that name was already stale before this
   change, and the function it describes is now gone entirely.

The resolution log text changed (one line removed from the performance step, one
added by the standings). `context.log` is not a manifest section, so this is
outside the competitive hash.

---

## 5. V2-119's second question — deliberately not implemented

R32 leaves open whether a firing must be **visible in the stored row** rather
than only in a resolution log. **I did not implement it, and I am flagging that
my design makes it cheap**, exactly as the handoff asked.

Two things now exist that did not before: the classification is a first-class
value on the context (`commercially_inactive_team_ids`) at the moment both
controls run, and `leaderboard_entry.rank` is now *itself* the enforcement, so a
dispute can at least see that an inactive firm was placed below the active
field. What still does **not** exist is any stored field saying "this firm was
classified commercially inactive this round" — persisting it would be roughly a
one-field migration on `round_result_performance_index` plus one assignment.
**That is the owner's call, not mine, and I have not made it.** I note only that
the cost of saying yes is now small.

V2-110's remaining rules question — whether a team frozen out by its own
compliance failure counts as not competing — is untouched. The classification is
byte-for-byte what it was.

---

## 6. Commands, counts, durations

All against disposable PostgreSQL via `backend/scripts/test-postgres`, under
`flock -w 1800 /tmp/globalstrat-backend-test.lock`. Never the production
database at `192.168.50.38`; no systemd environment file read. The `--tmpfs` /
`fsync=off` workaround proved **unnecessary** on this host for focused labels —
containers came up in ~11s.

| # | Command | Result | Duration |
|---|---|---|---|
| 1 | `test-postgres core.tests.test_leaderboard_tiebreak` (harness probe) | 2 tests, **OK** | 11.3s wall |
| 2 | `test-postgres core.tests.test_inactivity_rank_guard` — **against unmodified engine** | 14 tests, **10 failures + 1 error** (intended red) | 11.7s wall |
| 3 | `test-postgres core.tests.test_scoring_dispositions` (pre-change baseline) | 14 tests, **OK** | 0.323s tests |
| 4 | `test-postgres core.tests.test_cc18_compliance` (pre-change baseline) | 15 tests, **OK** | 1.859s tests |
| 5 | `test-postgres core.tests.test_manifest_determinism` (pre-change baseline) | 57 tests, **OK** | 16.949s tests |
| 6 | `test-postgres test_inactivity_rank_guard test_scoring_dispositions test_cc18_compliance test_leaderboard_tiebreak --parallel 8` | 45 tests, **OK** | 28.9s wall / 2.163s tests |
| 7 | `test-postgres test_manifest_determinism test_zero_production_compliance_freeze test_round_zero_adoption test_engine --parallel 8` | 133 tests, **OK** | 43.4s wall / 16.7s tests |
| 8 | `git diff --check` | clean | — |
| 9 | `test-postgres test_inactivity_rank_guard test_scoring_dispositions test_cc18_compliance test_leaderboard_tiebreak test_manifest_determinism --parallel 8` — **re-run against the frozen commit** | 102 tests, **OK** | 16.9s tests |

Baselines (3–5) were taken **before** any edit, so every later result is
attributable. The red run (2) is the proof the tests fail without the change;
its failure values are the measurements in §3. Run 9 was taken after the commit,
against a clean working tree, so the green result is anchored to the frozen
commit on `crv2-11-inactivity-guard-rank-only` rather than to an uncommitted
tree — the ordering `EXECUTION_PROTOCOL` Phase 3 asks for.

The pre-commit hook ran and passed (`aide-checks` revision `77b8ced`, matching
`checks/.aide-checks-rev`; 2 checks ran, 0 blocking failures). **No
`--no-verify` was used.**

Not run, deliberately: the full backend suite (GSP-CRV2-09 owns it), the
four-environment cross-environment replay, and the release-scale eight-profile
balance replay.

---

## 7. What I could not verify

- **The −17.81 figure itself**, byte for byte. Mechanism and severity curve are
  reproduced; the exact magnitude depends on the replay's own field (§3).
- **That no stored competitive hash moves.** I did not re-resolve stored rounds.
  The claim rests on the 2026-09-16 measurement that the control never fired in
  448 stored index rows — an inference from that evidence, not a fresh replay.
- **Integrated regression beyond the labels in §6.** Focused suites only, per
  the execution protocol.

---

## 8. Proposed register wording for V2-119

Not applied — the handoff reserves the register to the owner.

> **Status cell —** **Question 1 ruled (R32, 2026-09-17) and implemented;
> question 2 open.** The control no longer overwrites a carried performance
> index. The rule it carried — a commercially inactive firm must not finish
> above a firm that competed — is preserved exactly and is now enforced on the
> standings: a competed flag leads `leaderboard.py`'s published sort key, so no
> index or tie-break can lift an inactive firm above an active one, and the
> firm's carried score is not touched. `_enforce_inactive_revenue_invariant` is
> deleted. The classification is unchanged and is now computed once by the
> performance step and read by the standings, so the two controls still cannot
> disagree about who competed. The round-level consequence of not competing
> remains the composite cap, bounded at 5.00 and applied to the round. Measured
> against the old code on one identical event, cost fell from −7.16 / −22.59 /
> −72.16 (at carried indexes of 55.00 / 70.43 / 120.00) to a flat −5.00; the
> success-scaling severity is gone. Engine change inside the CRV2-01
> determinism boundary: it changes stored index values where the control would
> have fired, earlier replay evidence covers its own commit, and the
> eight-profile replay's −17.81 / −17.31 / −13.60 collapse rounds are now
> historical. **Question 2 — whether a firing must be visible in the stored row
> rather than only in the resolution log — remains open and was deliberately
> not implemented**, though the builder notes the classification is now a
> first-class value on the resolution context, which makes persisting it cheap
> should the owner rule that way. Evidence: `completion/R32_INACTIVITY_RANK_ONLY_2026-09-17.md`,
> `core/tests/test_inactivity_rank_guard.py` (14 tests, red against the
> unmodified engine). **Stale as a result:** the
> `STATIC_STRING_INVENTORY.md:852` row for the removed
> `"; zero-revenue ranking guard applied"` string.
