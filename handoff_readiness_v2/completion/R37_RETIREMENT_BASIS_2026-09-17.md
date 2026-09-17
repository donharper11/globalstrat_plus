# R37 — the fire sale is priced off the stock that is actually left

Branch `crv2-12-r37-retirement-basis`, cut from `crv2-release-integration` at
`7b777ee` (past the `021c483` merge of R18/R36). Runtime commit **`cebbb88`**.
Isolated worktree; nothing pushed; no frontend file touched.

**No gate is closed by this document.** Closure is the auditor's.

---

## 1. What changed

One function, `costs.calculate_retirement_costs`. Both the write-off **and**
the recovery are now computed from the inventory remaining after the product's
**final round of selling**:

| Timing | Final round of selling | Stock used |
|---|---|---|
| `end_of_round` | **this** round — it sells through it (R18) | this round's unsold units at this round's unit cost, from `context.revenue` / `context.cogs` |
| `immediate` | the **previous** round — it stops selling before adoption | the previous round's unsold units, from stored `RoundResultProductMarket` rows — **unchanged** |

Two small helpers make the two bases nameable rather than inline:
`_stock_left_after_final_sale` and `_stock_left_before_this_round`.

**The write-off moves with the recovery, by necessity.** Pricing the recovery
off one position while writing off another would describe two different
inventories in a single P&L. The ruling speaks of the recovery; the write-off is
the value of that same stock, so they cannot be split.

The authored rates are untouched — 50% and 25%. This changes the basis, not the
rate.

---

## 2. The ordering difficulty dissolved, and my earlier note was wrong

The ruling and the brief both anticipated that the recovery step would have to
**move** to run after that round's sales are known. It did not, and I want to
be exact about why, because the reason corrects something I wrote last time.

`calculate_retirement_costs` **already runs after** the sales are known:

```
Step 10  calculate_revenue            (advance_round:817)
Step 11  calculate_cogs               (:827)
         …
         calculate_inventory_costs    (:839)
         calculate_retirement_costs   (:840)
Step 12  generate_financial_statements(:856)
```

My previous report said the figures were "not available at that point in the
pipeline". **That was true of the stored rows and false of the figures.**
`generate_financial_statements` does not write this round's
`RoundResultProductMarket` rows until `:856`, so a *database* read at `:840`
genuinely cannot see them — but `context.revenue[(team, product, market)]
['units_unsold']` and `context.cogs[...]['unit_cost']` have been populated since
`:817` and `:827`. `calculate_inventory_costs` at `:839` already reads exactly
those two maps for exactly this kind of figure, which is the proof that the data
was reachable all along.

So: **no step moved, and nothing about where the cost is booked changed.**
`financials.py:124-125` consumes `context.retirement_costs` and
`context.retirement_revenue` exactly as before, and operating income is composed
unchanged. The only other production caller,
`management/commands/recalculate_financials.py`, calls `calculate_revenue` and
`calculate_cogs` before `calculate_retirement_costs` (`:113-121`), so it is
correct there too — checked rather than assumed.

---

## 3. `immediate` does not move — and it was not safe to assume so

This is the part that could have gone silently wrong.

`revenue.py:69-71` builds `context.revenue` by iterating
`DecisionMarketing.objects.filter(submission=submission)` — **with no filter on
product status or `is_active`**. A product retired `immediate` is deactivated in
`process_rd` before adoption, so it is allocated no demand and `units_sold` is
zero — but if the team still carries a marketing row for it, `units_produced` is
that row's `production_volume` and therefore
`units_unsold = units_produced - 0 = production_volume`.

**A single shared "this round" basis would therefore have moved `immediate`,
and moved it by the whole of that production.** That is why the timing branch
stays explicit instead of relying on the emergent fact that a retired product
usually has no revenue row. `test_immediate_does_not_move_when_this_round_has_figures`
seeds exactly that situation — an `immediate` retirement *with* current-round
figures present — and pins the result to $1,000.00 write-off and $250.00
recovery, the pre-R37 numbers to the cent.

The falsification run confirms it from the other side: against the pre-R37
engine, **both `immediate` tests pass unchanged**.

### One observation, recorded not acted on

The ruling's premise is that for `immediate` "what is left" and "the previous
round's unsold units" are the same stock. In the ordinary case they are. In the
case just described — a team that ordered production in the round it retires the
product immediately — they are **not**: those units are built, charged COGS and
charged inventory holding, are never sellable, and are **not** part of the
retirement write-off. They sit as ordinary unsold inventory.

That is pre-existing behaviour, unchanged by R37, and I did not touch it: the
ruling is explicit that `immediate` must not move. Flagged because the premise
is not strictly universal, not because I think R37 got it wrong.

### A second interaction, also recorded

`calculate_inventory_costs` (`:839`) charges holding cost on this round's unsold
units for every product, including one retiring `end_of_round`. Under the old
basis the holding charge and the retirement write-off fell on *different*
rounds' stock; under R37 they fall on the **same** stock in the same round — the
team pays to hold it and then writes it off. That reads as correct to me (it did
hold the stock, and then disposed of it), and the rates are unchanged, but it is
a genuine change in how two charges interact and an owner may want to look at it.

---

## 4. Tests

`core/tests/test_product_retirement.py` — **14 tests**, up from 11.
`RetirementRecoveryRateTests` is rewritten around R37; the R18 timing classes
are untouched.

The fixture keeps the two positions **deliberately different** — 100 units held
going into the round, 40 still held after selling through it — so no test can
pass by reading the wrong one.

| Test | Pins |
|---|---|
| `test_end_of_round_is_priced_off_the_stock_left_after_selling` | $400 write-off, $200 recovery — the 40 units actually left |
| `test_end_of_round_does_not_read_the_position_before_its_final_round` | the write-off is **not** the pre-sale position |
| `test_end_of_round_falls_back_when_it_was_not_offered_this_round` | no marketing row ⇒ final sale was last round ⇒ the full 100 units |
| `test_immediate_is_priced_off_the_previous_round` | $1,000 / $250 |
| `test_immediate_does_not_move_when_this_round_has_figures` | **$1,000 / $250 with current-round figures present** |
| `test_the_authored_rates_are_unchanged_on_identical_stock` | 50% vs 25% measured on the *same* 100 units, so it compares rates and not positions |

### Proof it fails without the change

`costs.py` reverted wholesale to `7b777ee`, the new tests kept. No import
breaks — every symbol the module imports exists there — so the failures are
**behavioural**, which is what makes them evidence:

```
Ran 14 tests in 0.110s
FAILED (failures=2)

FAIL: test_end_of_round_is_priced_off_the_stock_left_after_selling
      AssertionError: Decimal('1000.00') != Decimal('400.00')
FAIL: test_end_of_round_does_not_read_the_position_before_its_final_round
      AssertionError: Decimal('1000.00') == Decimal('1000.00')
```

The old engine pays the team out on $1,000 of stock it no longer has, where
$400 is what is left. **Exactly two tests fail and they are exactly the two that
assert R37.** The two `immediate` pins, the fallback case, the rate test and all
eight R18 timing tests pass against the old engine — the change is localised to
the `end_of_round` basis and nothing else moved.

---

## 5. Commands, counts and durations

`backend/scripts/test-postgres <labels> --parallel 8`, each under
`flock -w 1800 /tmp/globalstrat-backend-test.lock`, each against its own
disposable `postgres:16-alpine` container. **Production at `192.168.50.38` was
never contacted and no systemd environment file was read.** No full suite.

| # | Labels | Result | Test time | Wall |
|---|---|---|---|---|
| 1 | `test_product_retirement` `test_manifest_determinism` `test_engine` `test_platform_lifecycle` `test_org_transition_charge` `test_funding_need` `test_paid_research` `test_rd_costs` `test_cc18_compliance` `test_cc20_fx_engine` | **OK, 266 tests** | 16.516s | 44.065s |
| F | `test_product_retirement`, `costs.py` reverted to `7b777ee` | `FAILED (failures=2)`, 14 tests | 0.110s | — |

**Determinism / manifest: `core.tests.test_manifest_determinism` ran inside run
1 and passed** (its 57 tests are part of the 266). `MANIFEST_SCHEMA_VERSION` is
**6**, unmodified — `git diff --name-only -- backend/core/services/` is **empty**,
so no manifest module, schema inventory or version file was touched. No model
field, no migration, no section.

After the falsification run `costs.py` was restored with
`git checkout HEAD -- …`; the tree matches `cebbb88`.

Diff scope: `backend/core/engine/costs.py` and
`backend/core/tests/test_product_retirement.py`. Nothing else.

---

## 6. What evidence this invalidates — confirmed, not assumed

**Nothing new.** I checked this rather than inheriting the brief's expectation.

R37 changes a charged amount **only on the `end_of_round` path**. The set of
rounds whose stored results and `output_sha256` move is therefore the set of
rounds containing an `end_of_round` retirement — which is **exactly** the set
R18 already invalidated when it changed that timing's market access. The
intersection is total, not partial, so no replay evidence that survived R18 is
invalidated by R37.

Specifically **not** invalidated:

* any round with no retirement — untouched;
* any round whose only retirements are `immediate` — the branch reads what it
  read before, and two tests pin the figures to the cent;
* CRV2-01's canonical-serialisation, envelope-enumeration and iteration-order
  evidence — no section, field or ordering changed, and run 1 re-proves it.

Superseded within this repo: the three R18-era `RetirementRecoveryRateTests`
assertions, which asserted the old basis ($1,000 / $500 for `end_of_round`).
**Replaced, not deleted** — the file now pins both bases separately.

---

## 7. What I could not verify — carried forward, not dropped

* **The replay regression is still owed, and still blocked.** R18 required a
  focused replay regression; it has not been run.
  `handoff_readiness_v2/determinism_fixture.py` still cannot resolve a round at
  head — **V2-116** — and R37 does nothing to change that.
* **R37 does not make a replay reachable through `v6_envelope_fixture.py`
  either, and I checked rather than guessed.** That fixture seeds and asserts
  three things (a research purchase, a deadline price-band adjustment, a
  not-for-sale row) and resolves round 1 at v6 — but it contains **no product
  retirement at all**. Its only two matches for "retire" are comments about
  R10 feature-level R&D. So a replay built on it today would resolve a round
  with no `end_of_round` retirement in it and prove nothing about R18 or R37.
  **It remains the right pattern to extend** — it already resolves a round and
  asserts its own coverage — but extending it to seed a retirement is work that
  has not been done here.
* **No full suite** — GSP-CRV2-09's gate. I ran 266 tests across ten modules
  chosen by dependence on what I changed.
* **No end-to-end resolved round for R37.** As with R18, the basis is proved
  through the engine function against seeded context state, not by resolving a
  round and reading a team's cash. The two interactions in §3 — holding cost
  and write-off now landing on the same stock, and `immediate` production in a
  retirement round — are reasoned from the code, not measured in a resolved
  round.
* **No browser pass**; nothing student-facing changed.
* The behaviour change from last time — the org view creating the round's
  `DecisionSubmission` — **stands as recorded**, untouched by this work.

---

## 8. Register wording — for the owner to place

I did not edit `V2_FINDINGS_REGISTER.md`, `LAUNCH_CHECKLIST_V2.md`, any
`OPEN_FINDINGS_READTHROUGH_*` or any `OWNER_RULINGS_*` file.

### V2-070 — suggested status-cell addition

> **Status update 2026-09-17 — the basis question is ruled (R37) and
> implemented at `cebbb88`, pending closure.** R18 gave `end_of_round` its own
> market timing; R37 makes the money follow it.
> `costs.calculate_retirement_costs` now computes **both** the write-off and the
> fire-sale recovery from the inventory remaining after the product's *final
> round of selling* — this round for `end_of_round`, which sells through it; the
> previous round for `immediate`, which never sells in its retirement round.
> The two move together because pricing the recovery off one position while
> writing off another would describe two inventories in one P&L. **The authored
> rates are untouched** (50%/25%): the basis changed, not the rate. **No step
> moved and the booking did not move** — `calculate_retirement_costs` already
> ran after `calculate_revenue` and `calculate_cogs`, so this round's unsold
> units and unit costs were in `context.revenue`/`context.cogs` all along; the
> builder's earlier "not available at that point in the pipeline" note was true
> of the stored `RoundResultProductMarket` rows, which financials writes later,
> and false of the in-memory figures. **`immediate` does not move, and that was
> verified rather than assumed:** `revenue.py` builds its rows from
> `DecisionMarketing` *without* filtering on product status, so an
> `immediate`-retired product still carrying a marketing row does get a
> current-round entry — selling nothing but carrying whatever it produced — so a
> shared basis would have moved `immediate` by the whole of that production. The
> timing branch is therefore explicit and
> `test_immediate_does_not_move_when_this_round_has_figures` pins the figure to
> the cent. Proof: `core.tests.test_product_retirement`, 14 tests, OK, inside
> 266 passing tests across ten affected modules; it fails without the change —
> with `costs.py` alone reverted, **exactly 2 of 14 fail and they are exactly
> the two that assert R37** (`1000.00 != 400.00`), while both `immediate` pins
> and all eight R18 timing tests still pass. **No manifest change:**
> `MANIFEST_SCHEMA_VERSION` stays **6**, no model field, no migration, no
> section. **Evidence invalidated: nothing beyond what R18 already invalidated**
> — confirmed rather than assumed, because R37 changes a charged amount only on
> the `end_of_round` path, so the rounds whose hashes move are exactly the set
> R18 had already moved. **Not closed, and the reason is unchanged from R18:**
> the focused **replay regression is still owed** and still blocked by
> **V2-116**; `v6_envelope_fixture.py` seeds *no product retirement*, so it
> cannot supply that replay today either, though it remains the right pattern to
> extend. **Two interactions recorded for the owner, neither acted on:** the
> ruling's premise that for `immediate` "what is left" and "the previous round's
> unsold units" are the same stock does not hold for a team that orders
> production in the round it retires immediately — those units are built,
> charged COGS and holding cost, never sellable, and not part of the write-off;
> and under the new basis the inventory holding charge and the retirement
> write-off now fall on the **same** stock in the same round, where before they
> fell on different rounds' stock.

---

## 9. Files changed

```
backend/core/engine/costs.py                  | 103 ++++++++++++-----
backend/core/tests/test_product_retirement.py | 144 ++++++++++++++++------
```

No migration, no model change, no manifest section, field or version change.
`aide-checks` (vendored `77b8ced`) ran on the commit and passed — 2 checks, 0
blocking failures; `--no-verify` was not used.
