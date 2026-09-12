# v6 manifest envelope — focused replay regression

**Development-grade focused evidence from a moving branch. NOT release
certification. No gate is closed by this directory.**

Subject: **game 1 ("V6-ENVELOPE-FIXTURE"), round 1**, resolved under manifest
schema version **6**. Finding **V2-086**.

This is the focused regression V2-086 records as outstanding: the paid-research
work moved the resolution manifest envelope from v5 to v6, which is a change
inside the CRV2-01 determinism boundary, and no replay was run against it. It is
**not** the four-environment matrix — GSP-CRV2-09 owns that.

## What this proves, and what it deliberately does not

It proves that a round resolved at this revision **replays byte-identically at
this revision**, with the sections new at v6 **non-empty**.

It does **not** compare against any older recorded manifest. The envelope moved,
so every historical hash differs by construction; V2-086 states this plainly
("a hash diff across this boundary is not evidence of an engine change"). Such a
comparison would prove nothing and none is presented here.

## The revision under test

| | |
|---|---|
| Commit | `e398fc652d01ed9b00a03a2784ad63b270a41c69` (`crv2-release-integration`) |
| Source tree digest | `cf82356adfdc3e69e3d553eed3784fab84792a4821b231115d0b02680a0ca154` (415 files under `backend/`) |
| Manifest schema version | **6** — `dump_manifest_schema --check`: *"Manifest schema inventory is current."* |
| Input hash | `ca459d0c77d6cf3aaeb2b331ff7b298ac72445745716dd966b6b490c13ebfa96` |
| Competitive hash | `94b6282aaa35e2ab8a17217d2ef2d9fe3e9d2861abea95596a13d5379833087b` |
| Narrative hash | `1a03448210276bac2c461e6853bd8c75a3215dde1ab903ac45d9924352906154` |
| Pre-resolution backup | `game-1-round-1-20260912T051923696041Z.dump`, sha256 `cedfd66a5e7f758bb74c415cdb3c88963f6efcadcf408083dee241d70625cfa5` |

Environment: Ubuntu 22.04.5 LTS, Python 3.10.12, Django 5.2.4, PostgreSQL
**16.13 in a disposable Docker container** with a generated credential, removed
afterwards. The production database at `192.168.50.38` was never contacted and
no systemd environment file was read.

## The envelope itself

Diffing the checked-in inventories `manifest_schema_v5.json` against
`manifest_schema_v6.json`:

| Envelope | v5 sections | v6 sections | New at v6 |
|---|---:|---:|---|
| input | 119 | **120** | `decision_research_purchase` |
| output (competitive) | 76 | **77** | `decision_research_purchase` |
| narrative | 3 | 3 | — |

`decision_research_purchase` is the **only** section added, in either envelope.
Natural key `(submission_id, report_type, scope_key)`.

The version docstring also names *"a `research_expense` line that is now
produced rather than always zero"*. That is **not** an envelope-shape change:
`research_expense` occurs in both the v5 and the v6 inventory (twice in each),
so the field was already hashed at v5 and only the value it carries changed.
Both halves are exercised below.

## Result

| | |
|---|---|
| Source identity | **verified** — `cf82356a…`, 415 files, no override |
| `--require-env` assertions | `tz_env=UTC`, `python=3.10.12` — both verified against this process |
| Input manifest | **verified** — `ca459d0c…` rebuilt == recorded, engine allowed to run |
| Competitive hash | **MATCH** — expected `94b6282a…` == actual `94b6282a…` |
| Narrative hash | match — `1a034482…` |
| Section diffs | **none** (`section_diffs` and `digest_diffs` absent from the report) |
| Exit code | **0** |

`replay_round` exit codes: **0** reproduced, **2** input manifest mismatch (the
engine is *not* run), **3** competitive hash mismatch.

## The round was built to exercise what changed

Seeded by `../../../v6_envelope_fixture.py`, which **asserts** each surface is
non-empty and exits non-zero naming the empty one rather than resolving a round
that would prove nothing.

| Required surface | How it was seeded | Proof it is non-empty |
|---|---|---|
| **`decision_research_purchase`** (the v6 section) | 3 of 4 teams buy through `research_catalogue.price_for`, at the price authored in `consumer_electronics_2026.yaml` (50,000 each). All three scope shapes: whole-game reports (`markets`, `products`; `scope_key` `''`), a market-scoped report (`segments`; `scope_key` `'NA'`) and analyst queries (`scope_key` `'1'`, `'2'`) | **11 rows** in both envelopes; output section digest `rows=11`, sha256 `73c299db…` |
| **Out-of-band price at the deadline** | One deliberate out-of-band price: Cipher Systems / *Nexus Lite* / NA, submitted **572.00** against a band of 154.00–286.00 anchored on the **`previous_round`** price 220.00 → moved to the nearer edge **286.00** | **10** `price_band_adjusted` audit events (see note below) |
| **Not-for-sale row** | Cipher Systems / *Nexus One* / **AFR** — a blank price on a product-market with no prior-round price. `blank_price(band)` asserted `None` before writing, so the row takes `RULE_NOT_OFFERED` and not the band floor | **1** `price_not_offered` event; `applied_price` null; the row is **not deleted**; 1 null-price row survives the close |
| **Ordinary decisions** | 4 teams on differentiated profiles: marketing/production for every product-market, market entry, contract plant, compliance investment, talent allocation across three pools, sourcing strategy and per-supplier allocation | 4 `decision_submission`, **18** `decision_marketing`, 22 `product_market` result rows |
| **`research_expense` produced** | Follows from the purchases above | round 0: `0,0,0,0`; round 1: **`150000, 250000, 150000, 0`** — produced, not hardcoded |

**Note on the 10 band adjustments.** Only one was deliberate. The fixture prices
every product-market uniformly at `500 x profile factor`, which also falls
outside the **positioning-reference** band for nine other product-markets, so
the deadline adjusted those too. The deliberate one is identifiable by its
`anchor_source: previous_round`; the incidental ones carry
`anchor_source: positioning_reference`. All ten are genuine applications of the
Stage 5 rule and all ten are in the envelope.

**Where the Stage 5 audit rows actually land — stated precisely.**
`decision_audit_event` is declared `in_output=False`, so the receipts are in the
**input** envelope (15 rows) and **not** in the competitive output hash; its
`payload` field is further excluded from hashing, with only `payload_sha256`
retained. What *does* reach the competitive envelope is the **effect**: the
adjusted number is written onto `decision_marketing.retail_price`, and the
not-for-sale row stays null there — and `decision_marketing` is a hashed output
section. So the adjustment is replay-protected through the decision row, while
the receipt is replay-protected through the input envelope by hash.

## Negative tests

Each restores the backup, verifies clean, changes **exactly one** stored value,
and re-verifies. All three fail **before the engine is called** (`--verify-only`
would stop there regardless; the point is that verification refuses).

| Corrupted | Clean control | Gate | Reported | Exit |
|---|---|---|---|---|
| A decision payload | exit 0 | input manifest | `decision_marketing … .retail_price: '525' -> '526'` | **2** |
| A carried-state value | exit 0 | input manifest | `team … .cash_on_hand: '50000000' -> '51000000'` | **2** |
| **A research-purchase price (the v6 section)** | exit 0 | input manifest | `decision_research_purchase … .price: '50000' -> '50001'` | **2** |

The third is the one this run adds. The first two would pass against the v2-era
envelope and so prove nothing about what changed; only a refusal naming
`decision_research_purchase` shows the new section is **inside the verified
envelope** rather than merely present in the database.

## Files

```
recorded/expected-manifest.json.gz          the manifest as resolution recorded it
run-a-same-revision/expected-manifest.json.gz   the copy the run verified against
run-a-same-revision/source-identity.json    source digest + --require-env assertions
run-a-same-revision/input-verification.json pre-mutation input check
run-a-same-revision/replay-report.json      hashes, environment, process result
run-a-same-revision/replayed-manifest.json.gz   the manifest the replay produced
negative/<kind>-clean/                      clean verification straight after restore
negative/<kind>/                            verification after one value was corrupted
MANIFEST.sha256                             sha256 of every file above
```

Manifest bodies are gzipped. `--expected-manifest` reads gzip directly and
resolves a `.json` path to the `.json.gz` beside it, so the commands below run
as written against the stored artifacts.

## Transcript

All commands ran from `backend/` against the **isolated** container database
(`globalstrat_v6replay`); `--restore` drops and rebuilds the target schema.
`DB_*` were exported from a scratchpad env file holding a generated credential.

```bash
EV=../handoff_readiness_v2/evidence/determinism/v6-envelope

# 0. Disposable stack (pattern from backend/scripts/test-postgres).
docker run -d --name gsp-v6replay-pg --env-file <generated> \
  -p 127.0.0.1::5432 postgres:16-alpine

python3 manage.py migrate --noinput                                  # 19.065s
python3 manage.py load_scenario --file scenarios/consumer_electronics_2026.yaml
                                                                     #  1.998s
python3 manage.py dump_manifest_schema --check   # "inventory is current."

# 1. Fixture: a game whose round 1 exercises every v6 surface, then resolve.
COMPETITION_REQUIRE_CLEAN_BUILD=true \
python3 ../handoff_readiness_v2/v6_envelope_fixture.py --teams 4 \
  --summary <scratchpad>/fixture_summary.json                        #  6.411s
#   -> game_id=1  schema_version=6
#      input_sha256=ca459d0c…  output_sha256=94b6282a…  backup=…dump

# 2. Export the recorded manifest before anything is restored over it.
python3 manage.py replay_round --game-id 1 --round 1 --export-only \
  --evidence-dir $EV/recorded                                        #  1s

# 3. Replay at the same revision.
COMPETITION_RECOVERY_ENABLED=true COMPETITION_REQUIRE_CLEAN_BUILD=true \
python3 manage.py replay_round --game-id 1 --round 1 \
  --restore --confirm REPLAY-GAME-1-ROUND-1 \
  --expected-manifest $EV/recorded/expected-manifest.json \
  --evidence-dir $EV/run-a-same-revision \
  --label 'A: v6 envelope, same revision, same host, isolated stack' \
  --require-env tz_env=UTC --require-env python=3.10.12 \
  --wait-narrative 0                                                 # 16s, exit 0

# 4. Negative tests — restore, corrupt one value, verify (engine must not run).
for KIND in decision carried; do
  python3 manage.py replay_round --game-id 1 --round 1 --restore \
    --confirm REPLAY-GAME-1-ROUND-1 --verify-only \
    --expected-manifest $EV/recorded/expected-manifest.json \
    --evidence-dir $EV/negative/$KIND-clean                          # exit 0
  python3 ../handoff_readiness_v2/corrupt_one_value.py $KIND 1
  python3 manage.py replay_round --game-id 1 --round 1 --verify-only \
    --expected-manifest $EV/recorded/expected-manifest.json \
    --evidence-dir $EV/negative/$KIND                                # exit 2
done

# 5. The negative test this run adds: the section that is new at v6.
python3 manage.py replay_round --game-id 1 --round 1 --restore \
  --confirm REPLAY-GAME-1-ROUND-1 --verify-only \
  --expected-manifest $EV/recorded/expected-manifest.json \
  --evidence-dir $EV/negative/research-purchase-clean                # exit 0
python3 ../handoff_readiness_v2/corrupt_research_purchase.py 1
python3 manage.py replay_round --game-id 1 --round 1 --verify-only \
  --expected-manifest $EV/recorded/expected-manifest.json \
  --evidence-dir $EV/negative/research-purchase                      # exit 2
```

## What this run does NOT establish

- **One environment only.** Same host, same OS, same Python, same timezone. The
  four-environment matrix (different base OS, Python, process timezone and
  locale) belongs to GSP-CRV2-09 and was not run.
- **No LLM-divergence run.** `--wait-narrative 0`, so there is no equivalent of
  CRV2-01's runs B/C/D (substitute endpoint, unreachable endpoint). The
  narrative hash matched, but this run does not demonstrate that a changed model
  moves the prose and not the result.
- **One round, one scenario, four teams.** Consumer Electronics 2026, round 1.
- **Many sections are empty**, so replay is untested over them: `decision_rd`
  and `decision_platform` (feature-level R&D is retired by R10 — see below),
  acquisitions, alliances, hedges, and every `sc_*` decision table beyond
  sourcing.
- **No comparison across the v5/v6 boundary**, by design.
- The `decision_audit_event` **payload content** is outside the hash by design
  (only `payload_sha256` is hashed).

## A drift finding raised by this work

`determinism_fixture.py` — the CRV2-01 fixture — **can no longer resolve a
round at this revision**. It seeds feature-level `DecisionRDInvestment` rows,
and ruling **R10** retired feature-level R&D: `_run_phase_1` now refuses with
*"stored R&D investment(s) remain, and feature-level R&D investment is
retired"*. The first attempt here failed exactly that way. `v6_envelope_fixture.py`
therefore seeds no R&D rows, and `decision_rd` is empty **by design rather than
by oversight**. The stale fixture is reported, not repaired — repairing it is
not in this task's scope.
