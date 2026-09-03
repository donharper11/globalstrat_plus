# GSP-CRV2-10 — governing rule decisions

Decisions adopted while implementing Stages 2–4 that the handoff specification
does **not** uniquely determine. Each one could defensibly have gone another
way; recording which way it went, and why, is what makes it a rule rather than
an accident of implementation.

Reversing any of these is a rules decision, not a bug fix, and each entry names
what would have to change with it.

---

## R1. The platform-switch write-off is cash-effective

**Decision.** The write-off is subtracted in `total_opex`, so it reduces
operating income, net income and — through net income, with no add-back —
operating cash flow. It is also a tax deduction.

**Why it is not determined by the specification.** A write-off of stock is
commonly a *non-cash* charge: the cash left when the inventory was built, and
the write-down only recognises that the asset is worth less. Treated that way,
it would reduce inventory value and be added back in the cash-flow
reconciliation, changing P&L but not cash.

**What governs the choice made.** Two things, in order:

1. The Stage 4 rule says the switch is *charged to the team*. In this
   simulation cash is the binding constraint teams plan against, so a charge
   that never touches cash is not felt as a cost and would not shape the
   decision the rule exists to make costly.
2. `retirement_expense` — the closest existing sibling, also a write-off of
   stranded value — is already treated as cash-effective here. Two write-offs
   behaving differently in the same statement would be the harder thing to
   defend.

Accepted by the Stage 4 re-audit as a valid simulation rule on this basis.

**If reversed:** add the charge back in `operating_cf`, reduce
`inventory_value` by the written-off amount, and invert the cash assertions in
`WriteOffAccountingTests`. The P&L, tax and stored-line assertions stand
either way.

## R2. The write-off is a percentage of the *latest closing* stock

**Decision.** `unsold_on_platform` reads the most recent closing snapshot at or
before the switch round, not a sum across rounds.

**Why it matters.** Summing every round's `units_unsold` would write off stock
that was sold rounds ago, because each row is a closing position rather than a
movement. BECSR records the same reasoning for the same reason.

**If reversed:** nothing else changes, but the charge becomes a function of how
many rounds a product has existed rather than of what it is actually carrying.

## R3. The write-off percentage is authored, not fixed

**Decision.** `platform_switch_write_off_pct`, read from the scenario, default
`0.15`.

**Why.** It is a balance lever. A fixed constant would make re-basing equally
costly in every scenario, and calibration (GSP-CRV2-11) has no way to move it.

## R4. Licensing changes price, not lead time

**Decision.** `method` selects between the authored `development_cost` and
`license_cost`. It does not shorten the development clock.

**Why it is not determined by the specification.** The handoff says method must
affect "lead time, price, or both". Stage 2 made it affect price materially,
which satisfies the requirement. A licensing lead-time advantage would have
been invented rather than derived, so it was not.

**Ruled on directly by the handoff owner.** Do not add a licensing lead-time
rule without a new decision.

## R5. A platform cannot be ready in the round it was requested

**Decision.** `MIN_DEVELOPMENT_ROUNDS = 1`. An authored `development_rounds: 0`
is raised to one round.

**Why.** V2-040: a zero-round generation made the request and the capability
simultaneous, so there was no window in which a rival could respond. The clock
is the whole competitive content of a platform decision.

**If reversed:** authored zero-round generations become instantly available
again, and `PlatformTimingTests` inverts.

## R6. Payment, the development clock and the funding round are one event

**Decision.** A platform is charged exactly once, in `funded_round`, and its
clock starts in that same round. An `unfunded_draft` is charged nothing and
ages not at all.

**Why.** Before this, an unaffordable platform could be charged in its
submission round while labelled unfunded, and the clock could start from a
different round than the payment. Splitting the three made "when did this cost
land?" unanswerable from the data.

## R7. A re-base takes effect in the game's current round, never a named one

**Decision.** `ProductRebaseView` takes the round from the game. The request
body cannot name it.

**Why.** A client-named round would let a team backdate a switch into a round
that has already been scored and published — the precise history rewrite the
round-versioned association exists to prevent.

## R8. A rival's write-off is not public

**Decision.** `platform_switch_write_off` is exposed on a team's own results
and deliberately omitted from the competitor block.

**Why.** The line reveals both that a rival re-based and roughly how much stock
they were carrying. Competitive intelligence in this simulation is what a team
can infer from published market outcomes, not what the API volunteers.

---

## Still open — not decided here

- **A8, "a finalised platform is fully modifiable"** remains a rules decision
  for Stage 3B. Freezing ready platforms is the intent, but until Stage 3B
  lands, both the old upgrade path and re-basing are reachable, which is
  deliberate: removing one before the other exists would leave a window with
  no route to a better product.
- **A5, no operating budget and no overspend financing**, is untouched by
  Stage 4.
