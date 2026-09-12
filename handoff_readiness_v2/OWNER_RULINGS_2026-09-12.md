# Competition owner rulings — 2026-09-12

Eight rulings issued by the competition owner on 2026-09-12, recorded in the
form the programme record requires: the question as asked, the ruling, the
consequence, and what each dispositions. They follow R11–R14 in
`OWNER_RULINGS_2026-09-11.md`.

These are rules decisions, not implementation notes. Where a ruling names work,
the work belongs to the handoff owner named against it; reversing a ruling is a
new rules decision, not a bug fix.

---

## R15 — the price-band floor applies only to a product the team is selling

**Question as asked.** Ruling 2 (the price band) says a blank price is priced at
the band floor. The Stage 5 builder applied that to every active
product-market with no marketing decision, fabricating a `DecisionMarketing`
row at the floor with `production_volume = 0`. Is that what "blank" means?

**Ruling.** No. **"Blank" means a product the team is actually selling** — it
had a price last round, and this round the team either priced it outside the
±30% band or left the number out. In the owner's words: *"the floor price only
assumes a price existed in the previous round (say $100) and the team
mis-priced … or blanks out a price and forgot to enter a number. That's quite
different from not marketing — no promotion, no retail channel, no product
created to begin with."*

**The floor must never reach a product-market the team never marketed.**

**Consequence.**

- The rule applies where the anchor is a real prior-round price
  (`anchor_source == previous_round`) and the team has a marketing decision
  this round with no usable price.
- No `DecisionMarketing` row is fabricated for an unmarketed product-market.
  This is not cosmetic: `bass_engine.py:57-66` builds `retail_prices` only from
  marketing rows and `:108-110` gives a product with no row an attractiveness
  of 0, so an unmarketed product takes no demand today. A fabricated
  floor-priced row would enter the denominator at a very competitive price,
  take share from every rival, and then sell nothing — `bass_engine.py:159-166`
  caps sales at available production and books the rest as `lost_demand`.
  Rivals would be penalised for another team's inaction.
- "Blank" must become representable: the pricing surface refuses a price ≤ 0
  and drops unpriced rows, so today a team cannot submit one. An explicitly
  empty price on an otherwise-present marketing row is to be accepted, alerted
  while the round is open, and filled at the floor at the deadline.

**Dispositions:** GSP-CRV2-10 Stage 5 / V2-041 — implementation narrowed
accordingly; the builder's own finding about the fabricated row is answered.

---

## R16 — the legacy `/simulation-control/` engine is deleted

**Question as asked.** A second, older engine is still routed:
`POST /api/simulation-control/` (start, advance, pause, resume, reset) and the
`advance` action on `SimulationStateViewSet`, both calling
`core/services/round_engine.py` rather than the competition engine. It is
guarded by `IsInstructor` with **no ownership check**, and its `_reset` runs
unscoped SQL — `TRUNCATE … CASCADE`, `DELETE FROM programs`, `DELETE FROM
messages`, and `UPDATE team_performance` / `UPDATE simulation_state` with no
`WHERE instance_id` — with every failure swallowed. Patch it, scope it, or
remove it?

**Ruling.** **Delete it.** The owner's reasoning, recorded because it is the
general rule and not only this instance: *"If it's older and we have a newer
engine replacing it, why are we keeping it … I don't like loose items just
hanging around for no reason."* Investigate callers first to be safe, then
remove.

**Consequence.**

- The route, its view, the legacy `advance` action and the unused frontend
  export go. Whatever the removal inventory proves dead goes with them;
  anything ambiguous stays and is reported rather than guessed at.
- No legacy models or tables are dropped under this ruling. Deleting data
  structures is a separate, migration-bearing decision.
- The caller investigation was done before the ruling was sought and supports
  it: zero hits for `simulation-control`/`simulation-state` across all rotated
  nginx access logs and 60 days of backend journal; no test, management command
  or UI component calls it; the only definition outside the URL conf is an
  unused `controlSimulation` export. Other matches on this machine are separate
  repositories, not this deployment.

**Dispositions:** the unscoped-reset and ownership finding raised by the Stage 6
builder — ruled; removal handoff opened 2026-09-12.

---

## R17 — a contended student save must refuse fast **and** say so

**Question as asked.** V2-064: the V2-063 fast-fail refuses a student's write
whenever any exclusive operator action holds the game lock — a deadline change,
an event injection, a team edit — not only during Phase-1 resolution. The
message claims the round is being processed, which is false for most of those,
and the frontend autosave swallows the 409 without retrying while the status bar
still shows the last successful save. Narrow the scope, or keep it?

**Ruling.** **Keep the fast refusal for every exclusive operator action, and
tell the student.** Waiting is not restored.

**Consequence.**

- The message must stop claiming the round is being processed and must describe
  what actually happened.
- The interface must show the edit was **not** saved and retry it. A student
  losing an edit silently, while the status bar reads "Saved", is the defect —
  not the refusal itself.
- This is participant-facing work under GSP-CRV2-12's standard, in both
  languages.

**Dispositions:** V2-064 — ruled; implementation open against the decision-path
and frontend owners.

---

## R18 — a product retired at end of round sells through that round

**Question as asked.** V2-070: with V2-043 repaired, `end_of_round` and
`immediate` retirement stop sales at the same moment, so they differ only in
fire-sale recovery — 50% against 25%. `immediate` became a strictly worse
choice with no compensating benefit. Which way?

**Ruling.** **`end_of_round` means what a student expects: the product keeps
selling for that round, and retires at its end.**

**Consequence.**

- `end_of_round` gets its own market timing; it must not deactivate the
  product's market rows before the round resolves.
- The two options become a real trade-off — sell through at 50% recovery
  against exit now at 25% — so neither dominates and the authored recovery
  rates stand as authored.
- This changes what a round resolves, so it is inside the CRV2-01 determinism
  boundary and needs a focused replay regression, not only a unit test.

**Dispositions:** V2-070 — ruled; implementation open. V2-043's repair stands;
its market-deactivation half is superseded for the `end_of_round` timing.

---

## R19 — the V2-048 privilege risk was never accepted

**Question as asked.** V2-072: the register and the operations review both state
that on 2026-09-05 the competition owner accepted, as "not a competition-release
blocker", that the application's database role is a member of the `postgres`
superuser role and can `SET ROLE postgres`. The attribution appears only in
builder-authored files. Did the owner accept it?

**Ruling.** **No. That acceptance was never given.** The finding stands as an
**open P0**, and the remedy is to run the application as a non-owner role that
cannot escalate privilege or drop its own audit guards.

**Consequence.**

- Every record repeating the acceptance must be corrected, not merely
  annotated: the claim is withdrawn, with the date it was withdrawn.
- The register's legend is restored to meaning what it says — P0 blocks release
  — so this is a launch blocker until the role is replaced and re-audited.
- It joins the deployment actions already outstanding (supervised narrative
  worker, `COMPETITION_REQUIRE_CLEAN_BUILD`), and it is the reason the
  least-privilege item cannot be deferred past the freeze.
- **Process note, deliberately recorded:** an owner decision appeared in the
  programme record that the owner never made. Attribution of a ruling is now
  itself an audit item — a ruling exists when it is in an `OWNER_RULINGS_*`
  document with a date, and nowhere else.

**Dispositions:** V2-072 — acceptance withdrawn; open P0 against the DBA and
operations owner. V2-048's residual review item inherits the same status.

---

## R20 — the lock `NameError` is rated P1

**Question as asked.** V2-056: from 2026-09-01, every call to the student lock
endpoint for a team with a budget allocation returned a 500. P0 or P1 depends on
whether any real game was played in that window.

**Ruling.** **No real games were played in that window.** The finding is **P1**.
No participant was affected, no published result is in question, and no incident
note is required.

**Consequence.** The repair (already landed) stands on its own; there is nothing
to remediate for past play. What remains is the process finding behind it —
the defect survived ten days because the suite was red and unread (V2-071,
V2-074).

**Dispositions:** V2-056 — severity settled at P1.

---

## R21 — a refused student save need not leave an audit record

**Question as asked.** V2-066: a 409 refusal writes no audit row, no log line
and no request id, while operator refusals are recorded. Should a refused
student save leave evidence?

**Ruling.** **Leave it as it is.** No audit row is required for a refused
student write.

**Consequence.**

- V2-066 stays P2 and closes as accepted rather than staying open: nothing is
  written by a refused request, so there is no mutation to account for.
- The reach of this ruling is deliberately narrow — it does not weaken V2-036,
  which requires refused **operator** actions to be recorded, and it does not
  license dropping any other audit path.
- One consequence to carry into certification: CRV2-07's count of busy 409s is
  client-side only and has no server-side corroboration. It must be described
  that way and not cited as audited evidence.

**Dispositions:** V2-066 — accepted as-is; closed.

---

## R22 — CRV2-11 Stage 2's parity rule is ratified

**Question as asked.** V2-073: the `cbe2656` snapshot closed CRV2-11 Stage 2
while, in the same snapshot, deleting the Stage 2 acceptance criterion that no
archetype hold "a material unearned edge" — the builder rewrote its own gate and
then certified against the remainder. Ratify the rule it landed on, or re-audit?

**Ruling.** **The rule is ratified.** Round-zero equality of performance index
and rank is the **only** starter-parity requirement; teams open deliberately
different in position, price point and strategic problem; from round one,
divergence in index is an **outcome**, not a calibration gate, and no later-round
spread threshold applies.

**Consequence.**

- CRV2-11 Stage 2 may be treated as closed by GSP-CRV2-09 on this ruling — and
  on this ruling only, dated and attributed here, not on the builder's edit.
- The governance defect is **not** excused by the ratification, and V2-073 stays
  on the record as a finding: a builder deleting an acceptance criterion and
  certifying against what remained is not a closure, whatever the merits of the
  rule. The right sequence was to raise the question and get this ruling first.
- Round 0 shows every team joint first; a revenue ladder must not be presented
  as a score ladder.

**Dispositions:** V2-073 — rule ratified; the governance finding stays recorded.
V2-055 / CRV2-11 Stage 2 — closure now rests on a dated owner ruling.

---

## R23 — market research is a paid mechanic, and it is wired up now

**Question as asked.** `research_budget` is counted toward a team's committed
spend, but no surface can set it, nothing charges it, and market research
reports are free and unlimited. Is research free, and should the dormant field
be removed?

**Ruling.** **Research was never meant to be free.** Reports are a paid
mechanic; that they are free today is an oversight, not a design decision. It
is to be **wired up now, properly** — identify the reports that genuinely help
a team, put a cost on each, build the purchase surface, and land the mechanic.
**Only the final prices are deferred:** a uniform placeholder price is
acceptable, because "costs can always be calibrated and fine-tuned later".

The owner's framing, recorded because it generalises: the question is not what
to introduce before a competition, it is *"do we have what we need and are the
mechanics in place. If not, can it be put in place later."* Deciding research is
free, stripping the field and the check, and leaving no accommodation to add it
later was rejected as a non-starter.

**Consequence.**

- The catalogue and per-report prices are authored scenario data, so
  calibration is later a data change and never a code change.
- A report bought in a round is bought: re-opening it must not charge again.
- Delivered immediately on purchase — a report after the deadline is useless —
  and charged in the engine with every other outlay.
- The charge must appear in **both** `funding_need.decision_outlays` and
  `costs.py`'s `research_expense`. V2-024 exists because one calculator drifted
  from another; research must not repeat it.
- `research_budget` remains a **declaration**, like `marketing_budget` and
  `strategy_budget` — it feeds coherence scoring and is not a second cash gate.
- Reports already bought stay readable after close, for disputes and the
  defence round.

**Dispositions:** V2-057's open question ("is `research_budget` a live rule at
all") — answered: yes, research costs money. Implementation handoff opened
2026-09-12.

---

## R24 — an unpriced product with no price history is simply not for sale

**Question as asked.** Under R15 the band floor applies only to a product with a
prior-round price. So what happens to a **new** product — never sold, no anchor
— whose price a team leaves blank? The builder made the round refuse to resolve
until it was fixed.

**Ruling.** **It is not for sale that round.** The product does not go on sale,
the team is told why on its own results screen, and **the round always
resolves.**

**Consequence.**

- No heat can be stalled by one team's omission. This is decisive because
  `InstructorTeamDecisionsView` is read-only and R13 made the admin read-only:
  **there is no supported way for an instructor to set a missing price**, so a
  refusing round could only be cleared by reopening it mid-competition.
- The team's decision row is kept, not deleted — it is their record — and a
  `system` audit event records that the product was not offered and why.
- A null price is excluded from the demand path at source, so an unpriced
  product takes no demand and displaces no rival.
- The refusal at lock stays: a team that deliberately locks is still told to
  price it, at a moment when it can act.
- **Still with the owner:** whether a not-for-sale product should still be
  charged for the units it chose to manufacture. It is charged today, on the
  argument that not pricing a product does not refund the factory. Recorded as
  an open question, not as a ruling.

**Dispositions:** GSP-CRV2-10 Stage 5 — the blank branch is settled; V2-041
implementation continues.

---

## R25 — preference weight on unreachable features is re-authored

**Question as asked.** Measurement across all three scenarios found segments
demanding features no first-generation platform can deliver. For Value Seekers
NA the three unreachable demands are decorative — a team at level 0 still scores
0.80 of the credit, at a total cost of about 1 fit point — while the segments
carrying genuine upgrade pull (Tech Enthusiasts, Gen Z Digital Natives) also
require generation 2 to enter, so the teams meant to feel the pull cannot reach
them. Leave it, exclude dead weight from scoring, or re-author?

**Ruling.** **Re-author the decorative rows.** Wanting a better product should
be felt where a team can act on it. Scoring code does not change.

**Consequence.**

- Scenario data only; the existing scenario-load preference contract stands.
- Because fit scores move, this is a calibration change and not a data tidy: it
  requires a before/after preference audit and a ten-round replay against the
  pre-change baseline, with the hash comparison pinned so it is meaningful.
- Whether a segment teams cannot enter should carry upgrade pressure at all is
  a separate design question, to be reported with options rather than decided
  by a builder.

**Dispositions:** GSP-CRV2-11 Stage 5 — ruled; implementation open.

---

## R26 — a product that cannot be sold is still paid for

**Question as asked.** Under R24 an unpriced product with no price history does
not go on sale. The team may nonetheless have decided to manufacture units for
it. Are those units charged?

**Ruling.** **Yes. They are charged, and the units sit in inventory.** You built
stock you then could not sell. The factory ran and the money went out; not
pricing a product does not refund manufacturing.

**Consequence.** The production decision stands on its own: COGS is incurred and
the inventory is carried, exactly as for any unsold output. Forgetting a price
is therefore a real mistake with a real cost, which is the behaviour the
deadline alert exists to prevent. `revenue.py` processes the row with a zero
price rather than skipping it, which is the implementation of this rule.

**Dispositions:** GSP-CRV2-10 Stage 5 question 7 — answered; no change required
to the implementation as built.

---

## R27 — gated segments keep their demands as authored

**Question as asked.** Tech Enthusiasts, Aerospace & Defense and Gen Z Digital
Natives require a second-generation platform to enter, and also carry the
authored demand for second-generation features. So the "upgrade to reach them"
pull is only felt by teams that have already upgraded. Move it earlier, or
leave it?

**Ruling.** **Leave it as authored.** Entering the segment requires generation
2, and the features it wants arrive with generation 2, so the demand is
self-consistent: a team that can enter can also compete there.

**Consequence.** R25's re-authoring is the whole of the change — it fixed the
segments first-generation teams actually play in. The gated segments' rows are
untouched, and their measured drag stands as recorded (0.2564 / 0.0103 /
0.1489). Nothing further is owed here.

**Dispositions:** GSP-CRV2-11 Stage 5 item 4 — closed as deliberately
unchanged.

---

## R28 — every firm in a heat starts from a distinct position

**Question as asked.** A heat of 8 firms draws on 4 authored starter profiles,
so two teams begin identical. The rank churn the R25 calibration replay found
was entirely between these twins.

**Ruling.** **Author more starting profiles, so no two firms in a heat begin
from the same position.**

**Consequence.**

- Enough distinct profiles for a full heat at the R12 cap of 8 firms, in **all
  three** shipped scenarios.
- **R22 still binds and is not relaxed:** every team opens on the same
  performance index and the same rank. Profiles differ in strengths, market
  position, price point, volume, debt and strategic problem — never in opening
  score.
- Because new profiles are new competitive positions, balance must be
  **measured**, not asserted: no profile may carry an advantage that play cannot
  overcome. This is measurement the programme owes anyway — R22 ratified that
  round-zero parity is the only *gate*, which is not the same as leaving
  starting balance unmeasured.
- Mid-table rank becomes meaningful, because a rank difference stops being an
  artefact of two teams being the same team.

**Dispositions:** GSP-CRV2-11 Stage 2 — a new authoring task, opened
2026-09-12. Related: the handoff's standing question about all profiles sharing
`home_market: NA` is to be reported with measurement, not decided by a builder.

---

## R29 — the round-zero per-segment share column keeps its new meaning

**Question as asked.** At round zero the per-segment share column carried each
team's authored firm-level market share, copied onto every segment row; from
round one the same column carries the team's share of that segment's adopters.
R11 made round zero match. Keep it?

**Ruling.** **Keep the change.** The per-segment column answers one question in
all eleven rounds: what share of this segment's adopters did you win.

**Consequence.** The authored starting market share is unaffected — it still
sits on the round-zero market row (`bootstrap.py:418-427`), which is where a
firm-level figure belongs. What ends is a firm-level number standing in for
segment data: at round zero the Market Research segment view ranked rivals by a
figure that had nothing to do with the segment being examined, and the
scorecard's strongest/weakest segment read the same column.

**Dispositions:** GSP-CRV2-11 R11 — the implementation as built is confirmed.

---

## Open with the owner at the close of 2026-09-12

Recorded here so they are not lost, and explicitly **not** ruled:

1. **`scenario_rd_spend_target`**, orphaned by R10 and still standing.
2. **Report prices** under R23 — the catalogue ships at a uniform placeholder;
   the real price list is deferred calibration, not an open defect.
