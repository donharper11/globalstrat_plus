# Competition owner rulings — 2026-09-11

Four rulings issued by the competition owner on 2026-09-11, recorded here in
the form the programme record requires: the question as it was asked, the
ruling, the consequence, and what each one dispositions.

These are rules decisions, not implementation notes. Where a ruling names work,
the work belongs to the handoff owner named against it; reversing a ruling is a
new rules decision, not a bug fix.

Index entries for these rulings are in `GSP-CRV2-10_RULE_DECISIONS.md`
(R11–R14). The findings they disposition are annotated in
`V2_FINDINGS_REGISTER.md`.

---

## R11 — round-0 adopters are derived from the authored starter sales

**Question as asked.** `bootstrap.py:175` multiplies the round-zero Bass
increment by an unauthored constant:

```python
new_adopters = bass_p * population_size * average_starter_product_share * 10
```

The `* 10` entered the repository in the baseline snapshot (`111d541`,
2026-04-17) with the sole comment "Scale for meaningful numbers". No scenario
YAML authors a round-zero duration, an initial cumulative-adoption percentage,
or an adoption-scale parameter. Should the factor stand, be replaced by an
authored parameter, or be derived? Registered as **V2-060** (D6).

**Ruling.** The `* 10` is **retired**. Round-0 adopters are **derived from the
authored starter sales**: each team's authored starting unit sales, apportioned
across its home-market customer segments. The round-0 segment adoption table
must therefore reconcile with the round-0 product sales rows students see on
the same screens. **No unauthored constant** replaces it — not 10, not 1, and
not a new scale key invented for the purpose.

**Consequence.**

- The round-zero adoption table becomes an apportionment of an authored figure,
  so it can be checked against the scenario rather than accepted on faith.
- The two round-0 numbers a student can see side by side — segment adopters and
  product unit sales — must agree. Today they do not reconcile at any factor.
- The implementation needs a regression that pins the *authored source*, not
  another embedded constant. That is the standing requirement D6 already
  carried.

**Measurement: the factor is display-only.** Measured this session by four
10-round, 8-team replays of Consumer Electronics 2026 (factor 10 vs factor 1,
the same pair again with team names pinned, and a factor-10 control with
different names):

- **Zero** differing rows in rounds 1–10 across all ten result tables —
  adoption, product demand, AI take, reconciliation, financials, performance
  index, leaderboard, product-market, market revenue, coherence. Units,
  revenue, net income, cash, PI and rank are identical per team per round.
- Round-1 `cumulative_adopters` (205,216.11) equals round-1 `new_adopters`, so
  round-0 adopters never carry forward: `bass_engine.py:313-345` returns 0.0
  for `prev_round < 1`.
- The only rows that differ are the 40 round-0 customer adoption rows
  (8 teams × 5 NA segments), and only their `new_adopters` and
  `cumulative_adopters`, exactly ×10.
- `output_sha256` differs in every round 0–10, because the adoption manifest
  section spans all rounds and therefore carries round 0 inside every round's
  hash. Dropping the 40 round-0 rows makes every hash byte-identical. **Any
  hash comparison across this change will show all rounds differing even though
  no outcome differs.**

This **contradicts** `CRV2-13_D2_D6_FOLLOWUP.md`, which states that the
multiplier "changes the round-one Bass cumulative state and therefore later
competitive demand". That claim is wrong and is corrected in the V2-060
register entry. D6 is a presentation and provenance question, not a calibration
one.

**Not implemented here.** R11 belongs to the **GSP-CRV2-11** owner. This
release-integration branch records the ruling in force and changes no engine
code. The register entry for V2-060 stays open against that owner.

**Dispositions:** V2-060 (D6) — rules question answered; implementation open
with GSP-CRV2-11. Answers open question 9 of the
`GSP-CRV2-11-calibration-and-balance` Stage 1 report item.

---

## R12 — cohort caps: 8 firms per game, 3–5 members per team

**Question as asked.** V2-042: eight students were enrolled through the roster
surface and all assigned to a single team, leaving 11 active members on a team
whose `team_size_max` is 5. Neither the roster surface nor team management
consults `max_teams`, `team_size_min` or `team_size_max`. Are the authored
`CourseSection` defaults the intended competition caps, and what enforces them?

**Ruling.** The caps are **8 firms per game maximum** and **3–5 members per
team**. The authored `CourseSection` defaults are **correct as authored**; what
is missing is **enforcement**, not a different number.

**Consequence.**

- Both write surfaces — enrolment/roster and team assignment — must refuse a
  ninth firm, a sixth member, and a team that would drop below three, at the
  point of the write.
- The caps are a competition rule, so a refusal must say what the cap is and
  what to do; silently truncating a roster is not an acceptable implementation.
- No existing authored section data changes.

**Not implemented here.** Enforcement belongs to the builder who owns V2-042
(Stage 6 / course and enrolment code), and that code is explicitly outside this
branch's scope. Recorded only.

**Dispositions:** V2-042 — the rule is now settled; the finding stays **open**
against its enforcement owner.

---

## R13 — the Django admin is a read-only evidence surface

**Question as asked.** V2-017: Django's admin add/change/delete views are
function-based, so 216 admin write routes are invisible to the route inventory
that certified "0 unguarded mutating routes". A staff user could move round
state through `/admin/` with no lifecycle lock and no `OperatorAuditEvent`. Is
it acceptable to lose admin editing of competition data?

**Ruling.** **The Django admin is a read-only evidence surface for every
competition-domain model.** Lifecycle services and the instructor UI are the
**only supported write paths** into competition state.

**Consequence.**

- Every competition-domain admin is read-only: no add, no change, no delete, no
  admin actions, and inlines that cannot be saved.
- Losing admin editing of scenario and team-membership rows is **accepted**,
  not a regression to be restored. Operational changes go through the supported
  services, which lock and audit.
- `auth.User` and `auth.Group` remain writable. They are Django account
  administration, not competition state, and they sit outside the audited
  lifecycle boundary by design.
- The route-inventory blind spot itself (`route_inventory.py:129-136` skips any
  route with no view class) is **not** closed by this ruling. It remains a
  separate hardening item: the admin is now harmless, but the inventory still
  cannot see it.

**This dispositions V2-017.** The read-only conversion is implemented on this
branch (65 admins moved to `CompetitionReadOnlyAdmin`, joining 5 already
read-only through `AppendOnlyAdmin`), and the register entry is updated with
that disposition and with the correction that **SCEventInstance was never
registered in admin at all** — the original V2-017 text named it in error.

**Dispositions:** V2-017 — ruled; implementation landed here; the inventory
blind spot carried forward as the open remainder.

---

## R14 — A5 operating budget and overspend financing: deferred, not built

**Question as asked.** A5, carried as "still open" at the end of
`GSP-CRV2-10_RULE_DECISIONS.md`: the simulation has no operating budget and no
overspend financing mechanic. A team that wants to spend beyond its cash has
no loan facility; the spend is simply refused. Should a loan or overdraft
mechanic be built for this competition?

**Ruling.** **Deferred for this competition. The current rule stands.** Spend
beyond available cash is **refused**; a team that needs more cash uses the
**voluntary debt raise** already available in the financing decision. **No loan
mechanic is built.**

**Consequence.**

- Cash remains the binding constraint teams plan against, which is what makes
  the platform-switch write-off (R1) and every other cash charge felt as a
  cost.
- Teams must plan financing in the same round as the spend. That is the
  intended pedagogy, not an oversight.
- No new model, decision field, engine term or screen is added for A5.

**A5 closes as "deliberately not built", not as an open gap.** This matters for
the re-audit: GSP-CRV2-09 must not record A5 as an unclosed finding or an
incomplete mechanic. It is a scoped-out feature with a dated ruling behind it.

**Dispositions:** A5 — closed as deliberately not built. The "Still open" entry
at the foot of `GSP-CRV2-10_RULE_DECISIONS.md` is superseded by this ruling.
