# v6 manifest envelope — focused replay regression

**Finding:** V2-086 (P1) — *"the resolution manifest envelope moved from v5 to
v6, and the replay regression that warrants was not run."*

**Status: the regression has now been run, and it passes.** I am not closing the
finding and I am not closing a launch-checklist gate; both are the owner's call.
Proposed wording for each is in §10.

> **Development-grade focused evidence from a moving branch. NOT release
> certification.** One environment, one round, one scenario. The
> four-environment matrix belongs to GSP-CRV2-09 and was not run.

---

## 1. What this run proves

A round resolved at `e398fc6` **replays byte-identically at `e398fc6`**, with
the section new at v6 **non-empty** (11 rows), and the input-verification gate
demonstrably able to fail — including on the new section itself.

**What it deliberately does not do:** compare against any pre-v6 recorded
manifest. The envelope gained a section, so every historical hash differs by
construction. V2-086 says so itself — *"a hash diff across this boundary is not
evidence of an engine change"* — and no such comparison is presented here as
evidence.

## 2. Isolation (EXECUTION_PROTOCOL Phase 0)

| | |
|---|---|
| Database | `globalstrat_v6replay` in a **disposable `postgres:16-alpine` container** (`gsp-v6replay-pg`), PostgreSQL 16.13 |
| Credential | generated with `openssl rand -hex 32`, written only to a session scratchpad file (mode 600), never to the repository |
| Port | bound to `127.0.0.1` on an ephemeral port |
| Production | `192.168.50.38` **never contacted**; no systemd environment file read. Every script hard-refuses if `DB_HOST` is the production host |
| Runner lock | **not taken, and not required** — `flock` is specified for Django *test suites* sharing the host database. This run used its own container and ran no test suite. Another builder's container (`gsp-crv213-pg`) was running concurrently and was untouched |
| Worktree | isolated worktree, detached from `crv2-release-integration`, then branch `crv2-01-v6-envelope-replay`. No other worktree or the main checkout was modified; nothing pushed |
| Cleanup | container removed at the end |

Host: Ubuntu 22.04.5 LTS, Python 3.10.12, Django 5.2.4, TZ `UTC`.

**A STANDING-DISCIPLINE §1.9 note.** The PostgreSQL client here is 18.3 against
a server of 16.13. §1.9 forbids an *older* client against a *newer* server; this
is the opposite direction, which is supported, and `competition_backup.py`
already carries `_restore_stderr_is_benign` precisely for the newer-client GUCs
(`transaction_timeout` and friends). Every restore in this run reported a
verified sha256 and no fatal error. CRV2-01's own run D used pg client 18.6, so
the combination is precedented rather than novel.

## 3. The envelope at v6

`dump_manifest_schema --check` → **"Manifest schema inventory is current."**
`MANIFEST_SCHEMA_VERSION = 6`.

Diffing the checked-in inventories:

| Envelope | v5 | v6 | New at v6 | Removed |
|---|---:|---:|---|---|
| input | 119 | **120** | `decision_research_purchase` | none |
| output (competitive) | 76 | **77** | `decision_research_purchase` | none |
| narrative | 3 | 3 | none | none |

`decision_research_purchase` is the **only** section added, natural key
`(submission_id, report_type, scope_key)`. The full 77-section output list is in
Appendix A.

**A correction worth recording.** The version docstring describes v6 as adding
the section *"and a `research_expense` line that is now produced rather than
always zero"*. The second half is **not** an envelope-shape change:
`research_expense` appears in both the v5 and the v6 inventory (twice in each),
so the field was already inside the hashed envelope at v5 and only the *value*
changed. The shape delta at v6 is exactly one section. Both halves are exercised
below regardless.

Provenance (`manifest_schema_history/PROVENANCE.json`) records v6 against
`c87395c`, 102,023 bytes, sha256 `61a7a504…` — consistent with V2-086.

## 4. The round was built to exercise what changed

Seeded by `handoff_readiness_v2/v6_envelope_fixture.py`. It **asserts** each
required surface is non-empty and exits non-zero naming the empty one, rather
than resolving a degenerate round and reporting a pass.

Game 1, `V6-ENVELOPE-FIXTURE`, scenario *Consumer Electronics 2026*, 4 teams,
round 1.

### 4.1 `decision_research_purchase` — the v6 section

Seeded by creating purchases through `research_catalogue.price_for()`, so each
row carries the price authored in `consumer_electronics_2026.yaml` (50,000)
rather than a number invented by the fixture. Three of four teams buy; the
fourth buys nothing, so the section's absence is represented too.

All three scope shapes are covered, because `scope_key` is half the natural key
and a single whole-game report would leave it constant:

| Team | Purchases |
|---|---|
| Cipher Systems | `markets` (`''`), `segments` (`'NA'`), `analyst_query` (`'1'`) |
| Nova Circuit | `markets` (`''`), `products` (`''`), `segments` (`'NA'`), `analyst_query` (`'1'`), `analyst_query` (`'2'`) |
| Prism Tech | `markets` (`''`), `segments` (`'NA'`), `analyst_query` (`'1'`) |

**Proof it is non-empty:** **11 rows** in the output envelope and 11 in the
input envelope; output section digest `rows=11`, sha256 `73c299db…`.

### 4.2 `research_expense` — the produced-value half of v6

| Round | research_expense per team |
|---|---|
| 0 | `0, 0, 0, 0` |
| 1 | **`150000, 250000, 150000, 0`** |

Produced, not hardcoded, and matching the purchases above (3 x 50,000,
5 x 50,000, 3 x 50,000, nothing).

### 4.3 Out-of-band price at the deadline

One deliberate out-of-band price on a genuinely banded row — "banded" being
load-bearing, since after the 2026-09-12 narrowing only a prior-round **result**
row is a `previous_round` anchor. The fixture selects from
`RoundResultProductMarket` at round 0 rather than assuming:

| | |
|---|---|
| Row | Cipher Systems / *Nexus Lite* / NA |
| Anchor | **220.00**, `anchor_source: previous_round`, round 0 |
| Band | 154.00 – 286.00 (`price_band_pct` 0.30) |
| Submitted | **572.00** |
| Applied at deadline | **286.00** — the nearer edge |
| Rule | `price_band.out_of_band_adjusted_to_nearer_edge` |

**Proof it is non-empty:** **10** `price_band_adjusted` audit events.

**Honest note on why 10 and not 1.** Only one was deliberate. The fixture prices
every product-market uniformly at `500 x profile factor`, which also falls
outside the **positioning-reference** band for nine other product-markets, so
the deadline adjusted those too. The deliberate one is identifiable by
`anchor_source: previous_round`; the incidental nine carry
`anchor_source: positioning_reference`. All ten are genuine applications of the
Stage 5 rule and all ten are in the envelope — but I did not engineer nine of
them and do not claim to have.

### 4.4 Not-for-sale row

| | |
|---|---|
| Row | Cipher Systems / *Nexus One* / **AFR** |
| Condition | blank price, no prior-round price for that (team, product, market) |
| Assertion before writing | `blank_price(band) is None` — so the row cannot silently take the band floor under `RULE_BLANK` instead |
| Rule | `price_band.unpriced_not_offered_for_sale` |
| Outcome | `applied_price` null, `submitted_price` null, row **not deleted**, 1 null-price row survives the close, and the round still resolved |

**Proof it is non-empty:** **1** `price_not_offered` event.

### 4.5 Ordinary decisions

Four teams on differentiated profiles (aggressive R&D / marketing-heavy /
balanced / conservative): marketing and production volume for every
product-market, market entry, contract manufacturing, compliance investment,
talent allocation across three pools, sourcing strategy and per-supplier
allocation. **4** `decision_submission`, **18** `decision_marketing`, **22**
`product_market` result rows, **8** `financials` rows.

### 4.6 Where the Stage 5 audit rows actually land

Stated precisely, because it is easy to overclaim. `decision_audit_event` is
declared `in_output=False`:

- the receipts are in the **input** envelope (**15 rows**) and **not** in the
  competitive output hash;
- its `payload` field is further **excluded from hashing**, with only
  `payload_sha256` retained.

What reaches the competitive envelope is the **effect**, not the receipt: the
adjusted number is written onto `decision_marketing.retail_price`, and the
not-for-sale row stays null there — and `decision_marketing` **is** a hashed
output section (18 rows). So the adjustment is replay-protected through the
decision row, and the receipt through the input envelope by hash.

## 5. Commands and durations

All from `backend/`, `DB_*` exported from the scratchpad env file.

| # | Command | Duration | Result |
|---|---|---:|---|
| 0 | `docker run -d --name gsp-v6replay-pg --env-file … -p 127.0.0.1::5432 postgres:16-alpine` | ~2s | PostgreSQL 16.13 |
| 1 | `manage.py migrate --noinput` | **19.065s** | OK |
| 2 | `manage.py load_scenario --file scenarios/consumer_electronics_2026.yaml` | **1.998s** | 2,140 records, scenario id 1 |
| 3 | `manage.py dump_manifest_schema --check` | <1s | **"inventory is current."** |
| 4 | `v6_envelope_fixture.py --teams 4` (seed, close, resolve) | **6.411s** | game 1, schema_version 6 |
| 5 | `replay_round … --export-only --evidence-dir $EV/recorded` | **1s** | exit 0 |
| 6 | `replay_round … --restore --confirm REPLAY-GAME-1-ROUND-1 --require-env tz_env=UTC --require-env python=3.10.12 --wait-narrative 0` | **16s** | **exit 0 — reproduced exactly** |
| 7 | negative `decision` — clean restore + verify | 12s | exit 0 |
| 8 | negative `decision` — tampered verify | 1s | **exit 2** |
| 9 | negative `carried` — clean restore + verify | 11s | exit 0 |
| 10 | negative `carried` — tampered verify | 2s | **exit 2** |
| 11 | negative `research-purchase` — clean restore + verify | 12s | exit 0 |
| 12 | negative `research-purchase` — tampered verify | 2s | **exit 2** |

One resolution and one replay: within EXECUTION_PROTOCOL's development budget
of *"1 local replay"* plus negative smoke. No full suite, no matrix.

The first fixture attempt failed (§9) and was re-run after the database was
dropped and rebuilt; that is the only repeated expensive command.

## 6. Input and output manifest results

| | |
|---|---|
| Source identity | **verified** — `cf82356adfdc3e69e3d553eed3784fab84792a4821b231115d0b02680a0ca154`, 415 files, `override: false` |
| `--require-env` | `tz_env=UTC` ✓, `python=3.10.12` ✓ — asserted against this process's own fingerprint, not labelled |
| Backup restored | `game-1-round-1-20260912T051923696041Z.dump`, sha256 `cedfd66a…` verified |
| **Input manifest** | **verified** — recorded `ca459d0c…` == rebuilt `ca459d0c…`. The engine was permitted to run |
| **Competitive hash** | **MATCH** — expected `94b6282aaa35e2ab8a17217d2ef2d9fe3e9d2861abea95596a13d5379833087b` == actual (identical) |
| Narrative hash | match — `1a034482…` |
| Code revision | `e398fc652d01ed9b00a03a2784ad63b270a41c69` → same |
| **Per-section diffs** | **none** — `section_diffs` and `digest_diffs` are absent from `replay-report.json`, which is how the command represents "nothing differed" |
| **Exit code** | **0** |

Exit-code meaning, from `replay_round`: **0** reproduced; **2**
`EXIT_INPUT_MISMATCH` — the rebuilt input did not match the recorded one and
**the engine was not called**; **3** `EXIT_OUTPUT_MISMATCH` — the engine ran and
the competitive hash differed.

There were no diffs to report. Had there been, they would be here and I would
have stopped rather than touched engine code.

## 7. Negative controls

Each restores the backup, verifies clean (the control for the control), changes
**exactly one** stored value, and re-verifies.

| Corrupted | Clean control | Refused on | Exit |
|---|---|---|---|
| A decision payload — `DecisionMarketing.retail_price` 525.00 → 526.00 | exit 0 | `section decision_marketing: 0 missing, 0 added, 1 changed` → `decision_marketing(decision_submission(team(game("V6-ENVELOPE-FIXTURE")｜"Cipher Systems")｜round(…｜"1"))｜team_product(…｜"Nexus One")｜market_definition(…｜"NA")).retail_price: '525' -> '526'` | **2** |
| A carried-state value — `Team.cash_on_hand` 50,000,000 → 51,000,000 | exit 0 | `section team: 0 missing, 0 added, 1 changed` → `team(game("V6-ENVELOPE-FIXTURE")｜"Cipher Systems").cash_on_hand: '50000000' -> '51000000'` | **2** |
| **A research-purchase price — the v6 section** — `DecisionResearchPurchase.price` 50,000 → 50,001 | exit 0 | `section decision_research_purchase: 0 missing, 0 added, 1 changed` → `decision_research_purchase(decision_submission(team(…｜"Cipher Systems")｜round(…｜"1"))｜"markets"｜"").price: '50000' -> '50001'` | **2** |

All three printed **"INPUT VERIFICATION FAILED — the engine was not run."**

**Why the third was added.** The task asked for two, and two is what CRV2-01's
pattern specifies. But a tampered marketing price and a tampered team cash
balance both sit in the *v2-era* envelope: they would refuse identically at v5
and prove nothing about what changed. Only a refusal naming
`decision_research_purchase` shows the **new** section is inside the verified
envelope rather than merely present in the database. It needed a new helper
(`corrupt_research_purchase.py`) because `corrupt_one_value.py` has no case for
it.

## 8. What remains unproven

- **One environment.** Same host, OS, Python, timezone and locale. No
  cross-environment reproduction. **GSP-CRV2-09 owns the four-environment
  matrix; this run is not a substitute for it.**
- **No LLM-divergence runs.** `--wait-narrative 0`, so there is no analogue of
  CRV2-01's runs B/C/D. The narrative hash matched, but this run does **not**
  demonstrate that a changed or unreachable model moves the prose and not the
  result. That property is inherited from CRV2-01, not re-established here.
- **One round, one scenario, four teams**, round 1 only. Nothing about
  multi-round carry-forward at v6.
- **Large parts of the envelope are empty and therefore untested by this
  replay:** `decision_rd` and `decision_platform` (see §9), acquisitions,
  alliances, partnerships, hedges, FX, and every `sc_*` decision table beyond
  sourcing. A replay reproduces an empty section trivially.
- **No comparison across the v5/v6 boundary** — by design, per V2-086.
- **`decision_audit_event` payload content is outside the hash** by design; only
  `payload_sha256` is covered.
- **Not certification.** Per EXECUTION_PROTOCOL, this is a focused Phase-2/3
  regression for the interface that changed, on a branch that is still moving.
  Earlier evidence remains evidence for its own commit, and this is evidence for
  `e398fc6` only.

## 9. A drift finding this work surfaced

**`determinism_fixture.py` can no longer resolve a round at this revision.** It
seeds feature-level `DecisionRDInvestment` rows; ruling **R10** retired
feature-level R&D, and `_run_phase_1` now refuses:

> `Round 1 cannot be scored: 16 stored R&D investment(s) remain, and
> feature-level R&D investment is retired (R10). Develop a new platform and
> re-base the product onto it.`

The first fixture attempt failed exactly this way, after `close_round` had
already succeeded. `v6_envelope_fixture.py` therefore seeds no R&D rows, and
`decision_rd` is empty **by design rather than by oversight**.

I have **not** repaired `determinism_fixture.py` — it is CRV2-01's artefact and
repairing it is outside this task. It is worth a register entry: the CRV2-01
evidence remains valid for its own commit, but the fixture that produced it is
no longer runnable at head, which matters to anyone who expects to regenerate
that evidence. Proposed wording in §10.

A second, smaller observation: migrations applied in the order `0084 → 0086 →
0085 → 0087_merge_20260912_0446`, i.e. the paid-research migration landed before
the price-band one under a merge migration. The graph is consistent and
`migrate` was clean; noted only because a merge migration in a competition
branch is worth an owner's eye.

## 10. Wording handed over (I did not edit the register or the checklist)

**Proposed V2-086 disposition update:**

> **Replay regression run 2026-09-12 and PASSED** — `completion/V6_ENVELOPE_REPLAY_2026-09-12.md`,
> evidence `evidence/determinism/v6-envelope/`. Game 1 round 1 resolved and
> replayed at `e398fc6` (source digest `cf82356a…`): input manifest verified
> `ca459d0c…`, competitive hash `94b6282a…` reproduced byte-identically, no
> section diffs, exit 0. The v6 section was non-empty at 11 rows across all
> three `scope_key` shapes, and `research_expense` was produced (150k/250k/150k)
> rather than zero. Three negative controls each refused before the engine
> (exit 2), including one on `decision_research_purchase.price` itself, which is
> what shows the new section is inside the verified envelope. **Development-grade,
> single-environment evidence; the four-environment matrix remains GSP-CRV2-09's.**
> Recommend P1 → closed **only if** the owner accepts single-environment focused
> evidence as discharging R18; otherwise hold open pending CRV2-09.

**Proposed new finding — stale CRV2-01 fixture:**

> **V2-0xx | Determinism evidence / fixture drift | P2** — `determinism_fixture.py`
> seeds feature-level `DecisionRDInvestment` rows, which R10 retired;
> `_run_phase_1` now refuses the round ("feature-level R&D investment is
> retired"). The CRV2-01 determinism evidence remains valid for its own commit,
> but the fixture that generated it is **not runnable at head**, so that evidence
> cannot be regenerated without repairing the fixture. Found while building the
> v6 replay fixture, which works around it by seeding no R&D.
> **P2:** no competition behaviour is wrong; the cost is to future evidence
> regeneration. Owner: CRV2-01 / GSP-CRV2-09.

**Proposed launch-checklist wording for the 2026-09-12 v6 gate:**

> **v6 manifest envelope replay** — focused regression run 2026-09-12 at
> `e398fc6`; round replays byte-identically with the new section populated and
> three negative controls refusing before the engine. **Single environment.**
> Gate remains **open** until GSP-CRV2-09 regenerates the integrated
> four-environment evidence against the release-candidate commit.

---

## Verdict

**The v5 → v6 envelope change preserves byte-identical replay.** At `e398fc6`, a
round carrying 11 `decision_research_purchase` rows, a deadline price-band
adjustment, a not-for-sale row and produced `research_expense` resolved and then
replayed to the identical input hash `ca459d0c…` and the identical competitive
hash `94b6282a…`, with no section differing. The verification gate is not
vacuous: three separate single-value tamperings each refused before the engine
ran, one of them on the new section itself.

That is the claim, and it is bounded: **one environment, one round, one
scenario, development-grade.** It discharges the "focused replay regression"
R18 asks for. It is **not** release certification and closes no gate.

---

## Appendix A — the v6 competitive output envelope (77 sections)

**New at v6:** `decision_research_purchase` (only).

- **Lifecycle and roster (3):** `game`, `round`, `team`
- **Accepted decisions (29):** `decision_submission`, `decision_budget`,
  `decision_rd`, `decision_platform`, `decision_product_create`,
  `decision_product_retire`, `decision_marketing`, `decision_market_entry`,
  `decision_financing`, `decision_plant`, `decision_partnership`,
  `decision_acquisition`, `decision_esg`, `decision_event_response`,
  `decision_research`, **`decision_research_purchase`**, `decision_talent`,
  `talent_allocation`, `compliance_investment`, `sc_sourcing`,
  `sc_sourcing_allocation`, `sc_logistics`, `sc_inventory`, `sc_incoterms`,
  `sc_customs`, `sc_trade_finance`, `sc_sinosure`, `sc_fx_hedge`,
  `sc_contingency`
- **World state (9):** `event_instance`, `active_modifier`, `sc_event_instance`,
  `supplier_state`, `lane_state`, `government_action`,
  `government_satisfaction`, `compliance_enforcement`, `ai_investor_holding`
- **Carried team state (19):** `team_platform`, `team_platform_feature_level`,
  `pending_feature_gain`, `team_product`, `team_product_platform_history`,
  `team_product_market`, `team_market_presence`, `team_market_modifier`,
  `team_strategy_feature_level`, `team_talent_state`, `team_plant`,
  `team_partnership`, `team_acquisition`, `team_alliance_state`,
  `team_governance_commitment`, `team_market_compliance`, `team_tax_structure`,
  `team_org_structure`, `hedge_position`
- **Published results (17):** `financials`, `market_revenue`, `product_market`,
  `adoption`, `product_demand`, `ai_adoption`, `demand_reconciliation`,
  `performance`, `coherence`, `resilience`, `share_price`, `leaderboard`,
  `esg_impact`, `talent_impact`, `partnership_impact`, `agent_cycle`,
  `instructor_alert`

**Input-only (3, not in the competitive hash):** `team_member`,
`decision_audit_event`, plus the 41 scenario/engine configuration sections
(input envelope: 120 sections total).

**Narrative (3, hashed separately):** `strategic_briefing`,
`market_intelligence`, `narrative_alert`.
