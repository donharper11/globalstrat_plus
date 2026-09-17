# Open P0/P1 read-through — 2026-09-17

**Purpose.** Establish what is *actually* open, ahead of a code-freeze decision.
Every line below was checked against the working tree at `af43d8f`, not against
the register's own prose.

**Why it was needed.** Two scripted passes over the register misclassified the
same rows in opposite directions — the first read the *opening* words of each
status cell, the second keyword-matched the *end* — and both produced lists that
were wrong in ways an auditor would have inherited. The register's status cells
accumulate: a row opens "Open — not repaired", and the repair is appended
paragraphs later in the same cell. So a status must be read, not parsed.

**The headline.** The register **overstates what is open.** Of the 24 P0/P1 rows
a naive pass called open, **most are stale**. Three are genuinely open and were
verified open today. The rest split into rulings already given but not yet
reflected, work already merged, and a small tail of real work.

**No gate is closed by this document.** It is input to the freeze decision and
to GSP-CRV2-09; closure remains the auditor's.

---

## 1. Genuinely open, verified open today

| ID | Sev | State, verified | What closes it |
|---|---|---|---|
| **V2-064** | P1 | **Open — the half you ruled on is missing.** R17 ruled that a contended student save must refuse fast **and tell the student**. The backend half is done: `lifecycle_in_progress` exists in the catalogue and `views/decisions.py:231-251` returns it. The client half is **not** built — `contexts/DecisionContext.js:57-58` is still `catch (err) { console.error('Auto-save failed:', err); }`, and `lifecycle_in_progress` appears **nowhere** in the frontend. A student's edit is still discarded silently while the status bar reads saved. | Surface the refusal in the save path and retry it; assert it in a test that fails without the change. |
| **V2-105** | P1 | **Open — narrower than written.** Extend Deadline is a plain button and modal in `pages/InstructorDashboard.js:462`, outside the `RoundControlCard` that Stage 6 hardened, so its confirmation does not name the game. Neighbouring `pause` also emits a hardcoded `message.success('Game paused')`. | Name the game in the Extend confirmation as Stage 6 did for the others; catalogue the pause string while there. |
| **V2-080** | P1 | **Nearly closed.** `components/instructor/OperatorEventsPanel.js` now has 15 `t()` calls and **one** remaining hardcoded fallback; `InstructorDashboard.js` has **zero**. | Remove the last fallback and catalogue it in both languages. |

## 2. Ruled by the owner; implementation outstanding

| ID | Sev | Ruling | State, verified |
|---|---|---|---|
| **V2-070** | P1 | **R18** — a product retired `end_of_round` **sells through that round**. | **Not implemented.** `engine/rd_processing.py:358-366` makes the `end_of_round` branch identical to `immediate`: status retired and **every** `TeamProductMarket` row deactivated at once. No "sell through" behaviour exists, and no R18 reference appears in the engine or `test_product_retirement.py`. The 50% vs 25% recovery split (`costs.py:881`) therefore still makes `immediate` strictly dominated — the defect R18 was issued to remove. |
| **V2-088** | P1 | **None yet — this one still needs you.** | Open and unrepaired. The organisational-structure switch charges cash in the view (`cc32b_views.py:145-149`); it is audited, hashed and lock-guarded, but appears in **no** calculator, so the team's own spending figures never show it and reopening a round does not refund it. The ruling needed: does the charge move into the engine at resolution, or stay immediate and join the calculators? |

## 3. Ruled and already reflected — closable by the auditor, not open work

- **V2-072** (P0) — **R33**: mitigated for GlobalStrat+ on the 2026-09-16 cutover, proven against `192.168.50.38` itself; estate exposure carried as a separate operations item. **No longer a launch blocker.**
- **V2-073** (P1) — **R22**; the cell's own text ends "RULED 2026-09-12".
- **V2-084** (P1) — **R29**; the cell says it is closable by the auditor on that ruling.
- **V2-056** (P1) — **R20** settled the P0/P1 question: no real games were played in the window.
- **V2-057** (P1) — superseded by **R23**: research is a paid mechanic and is wired up, so "should the dormant bucket count" no longer stands as asked.
- **V2-017** (P1) — **R13**, ruled and repaired.

## 4. Repaired, pending closure — the row is stale, the work is in

- **V2-107** (P0) — repaired at `1855b25`. The cell itself explains the row still read "not repaired" only because the repair landed before the row reached the register.
- **V2-110** (P0) — cause repaired at `1b6ef85` (the customs trigger gated on the effective unlock round); severity answered by **R32**, evidence by **R34**, the team told by **R35**. What remains is one *rules* question: whether a team frozen out by its **own** compliance failure counts as not competing.
- **V2-101** (P1) — repaired. `anchor_source` is handled in `pages/marketingPricingRules.js:44`, with tests covering `previous_round`, `positioning_reference` and `none`. (An earlier check of mine reported this missing; it had been extracted into a rules module, and I was grepping the page.)
- **V2-102** (P1) — repaired. `MarketingPage.js:83-84` sends `retail_price: null` deliberately — "null, not 0: an absent price is a distinct state the server alerts on and fills at the band floor" — so a cleared price reaches the server instead of vanishing.
- **V2-103** (P1) — repaired. Both notices render on `ResultsPage.js:676,679` and `GameDashboard.js:1158,1162`.
- **V2-024** (P1) — mechanism addressed: the register's own later text records that the rule "now refuses equity-raise outright", and `advance_round.py:680-681` enforces `funding_need.violations` with `EquityExceedsFundingNeedError`. The opening "Open — stops the handoff" is stale.
- **V2-068** (P1) — **verified on this host 2026-09-17:** `globalstrat-narratives` is active and enabled.
- **V2-086** (P1) — the replay it wanted was run this session: byte-identical over a round where the guard fires, with three negative controls.
- **V2-100** (P1) — aide-checks re-vendored at `77b8ced`; the hook has run and passed on every commit today, so the bypassed-gate condition is gone.
- **V2-075, V2-079, V2-087, V2-109, V2-118, V2-121, V2-122** — repaired, pending closure.

## 5. Real remaining work, not yet started

| ID | Sev | What it is | What closes it |
|---|---|---|---|
| **V2-074** | P1 | The seven stale tests are repaired at `b562c63`, but **no full suite has been run green on a candidate** — the suite has never been green. | One full-suite run on the freeze candidate. This is the gate everything else waits behind. |
| **V2-104** | P1 | A wholly-refused team assignment returns HTTP 200 with an `errors` array; the surface is `pages/InstructorDashboard.js` and no error handling was found there. The cap itself holds — V2-042 is intact. | Surface the refusal, or change the status; the builder's own note says the success toast was read from source, never observed. |
| **V2-076** | P1 | `reset_simulation` survives as a CLI with unscoped `TRUNCATE`/`UPDATE` across every instance. Not routed, so it blocks nothing on its own. | An operational control: withhold it from the competition deployment (checklist gate added 2026-09-12). |
| **V2-094** | P1 | The analyst query is charged without its price being shown. | A catalogue endpoint, or fold the price into an existing payload. |
| **V2-112** | P1 | Two supported creation paths build **different games** from the same scenario (`initialize_game` ignores the authored `beta` block). | Make one path authoritative, or converge them; two heats must be comparable. |
| **V2-114** | P1 | Reference prices `250/420/700/1000` are shared across all three scenarios but fit only consumer electronics, so the price lever clamps in the other two. | Author per-scenario reference prices — the thing V2-023 established and this undid. |
| **V2-116** | P1 | `determinism_fixture.py` can no longer resolve a round at head; it seeds R10-retired rows. CRV2-01's evidence stands for its own commit but cannot be regenerated. | Repair the fixture against the rule in force; `v6_envelope_fixture.py` is a working pattern. |

---

## What this means for the freeze

**No P0 is genuinely unrepaired.** Every P0 is repaired-pending-closure, re-rated
by ruling, or reduced to a rules question.

The true blocker set is small and mostly *decision-shaped or verification-shaped*
rather than code-shaped:

1. **One ruling outstanding** — V2-088.
2. **One ruled item unbuilt** — V2-070 / R18, and it is a competitive rule, so it
   should land before evidence is bought.
3. **Three verified-open participant/operator defects** — V2-064 (the one that
   matters: a student's edit still lost silently), V2-105, V2-080.
4. **A tail of real work** — V2-104, V2-094, V2-112, V2-114, V2-116, plus the
   operational control for V2-076.
5. **Then the gate everything waits behind** — the first green full suite
   (V2-074), on the candidate.

**Recommended sequence:** settle V2-088; build R18 and the three verified-open
defects; run the full suite; freeze on the first green result; then buy the
expensive evidence — combined load, walkthroughs, the independent re-audit —
against that commit.

**A process finding, recorded because it caused this document.** The register's
status cells are append-only narrative, and a reader — human or script — can
reach opposite conclusions depending on which end they read. Several rows say
"Open" above a paragraph describing the repair. Before GSP-CRV2-09 runs, the
status cells of every open row should be reconciled so the first sentence states
the current state. An auditor working from this register today would report
blockers that do not exist, and might trust a row that is genuinely stale.
