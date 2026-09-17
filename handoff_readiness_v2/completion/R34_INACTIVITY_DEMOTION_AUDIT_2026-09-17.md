# R34 — an inactivity demotion is recorded as an audit event

**Ruling:** R34, competition owner, 2026-09-17. **Finding:** V2-119, question 2
(question 1 was ruled by R32 and merged at `0ab1864`).

**Implemented at `a275010`** on `crv2-11-inactivity-demotion-audit`, branched
from `crv2-release-integration` at `bfc5a78`.

> **Development-grade focused evidence from a moving branch. NOT release
> certification.** One environment, one round, one scenario. **No gate is
> closed by this document** — the owner audits behind it. GSP-CRV2-09 owns the
> full suite and the four-environment matrix; neither was run.

---

## 1. What the ruling asked for, and what was built

Under R32 the standings place a commercially inactive firm below every firm
that competed, whatever its score, so a team can hold a **higher** performance
index than the team above it and still finish below it. That firing was written
only to `context.log`. Nothing in stored data explained the inversion.

R34: **the firing must be visible in stored data — recorded as an audit event,
not by adding a field to the hashed `performance` or `leaderboard` rows.**

### Where the event is written

`backend/core/engine/leaderboard.py::update_leaderboard`, at the point the
demotion is decided — the function already built the `demoted` list for its log
line. One `DecisionAuditEvent` per demoted team per round, written by the
module-level helper `_record_demotions`, which is called after the existing log
lines. **R32's log line is byte-identical**; nothing was reworded.

| | |
|---|---|
| `action` | `inactivity_rank_demotion` (`ACTION_INACTIVITY_DEMOTION`) |
| `endpoint` | `engine:update_leaderboard` (`AUDIT_ENDPOINT`) |
| `user` | `None` — actor **`system`**, exactly as the price-band receipts |
| `rule` in payload | `inactivity.ranked_below_every_active_firm` |

The action, endpoint and rule are module-level named constants rather than
literals at the call site, for the reason `price_band` states for its own: they
are what a dispute is answered with months later, so they are part of the
record's meaning and are not reworded casually.

### The exact payload

This is the real row from the replayed round (game 1, round 1), verbatim:

```json
{
  "rule": "inactivity.ranked_below_every_active_firm",
  "classification": "commercially_inactive",
  "round_number": 1,
  "team_id": 4,
  "team_name": "Cobalt Innovations",
  "rank": 4,
  "performance_index": "89.96",
  "lowest_active_performance_index": "52.05",
  "lowest_active_team_name": "Helix Digital",
  "lowest_active_rank": 3,
  "active_firm_count": 3,
  "inactive_firm_count": 1,
  "outscored_a_firm_ranked_above": true
}
```

`payload_sha256` `996dd975dcdab8fe60cc088e5b8fa3be631b5416c9cc1a8671e98a512533e784`.

That answers the question a disputing team actually asks — *why am I below a
team I outscored?* — with the firm's own carried index, the lowest index among
the firms that competed **and which firm held it**, the rank received, the
round, and the classification that caused it. Names as well as ids, following
`core/services/price_band.py::audit_payload`, which was built for the same
purpose and whose `_s` null-handling is reused (`str(None)` would store the
string `'None'`, which reads as a value in a dispute rather than the absence of
one).

Two payload fields are deliberate honesty rather than decoration:

- **`outscored_a_firm_ranked_above`** states the inversion instead of leaving it
  to be inferred. It is **false** when the firm would have finished last
  regardless: the guard still fired, and the record says so without claiming it
  cost a place.
- **`lowest_active_*` are null when no firm competed at all.** A field in which
  nobody competed has no comparison to make, and inventing one would be the
  dishonest half of this record.

---

## 2. The envelope did not move — this is the constraint that shaped the job

`Section('performance', …)` and `Section('leaderboard', …)` are hashed output
sections. A new field on either takes the manifest from **v6 to v7**, exactly as
the paid-research section did, and every hash comparison across that point
differs while no outcome has changed. The audit trail is deliberately outside
the hashed output (`decision_audit_event` is `in_output=False`), which is why
the explanation goes there.

| Check | Result |
|---|---|
| `MANIFEST_SCHEMA_VERSION` | **6** — unchanged |
| `dump_manifest_schema --check` | **"Manifest schema inventory is current."** (exit 0) |
| `decision_audit_event` in the **output** envelope | **absent** (`in_output=False`) |
| `performance` output fields | `game_id, index_change, index_value, round_number, satisfaction_score, team_id` — **no new field** |
| `leaderboard` output fields | `game_id, market_share_summary, net_income, performance_index, rank, round_number, shareholder_return, team_id, total_revenue` — **no new field** |

No migration was written, because no model changed.

---

## 3. The replay — proven over a round in which the guard actually fires

**This is the part that could not be assumed.** The price-band receipts are
written by `close_round`, *before* `prepare_manifest` snapshots the input
envelope, so they land **inside** the recorded input manifest. **R34's rows are
different**: they are written by engine step 15, *during* `_run_phase_1`, which
runs **after** `prepare_manifest`. The precedent therefore does not transfer by
assertion and had to be tested.

### Why that ordering makes replay safe

`process_round` runs `backup_before_resolution` → `prepare_manifest` →
`_run_phase_1` (step 15 writes the receipt) → `complete_manifest`. So:

- the receipt is **not** in the recorded input manifest;
- `--restore` restores the pre-resolution backup, which does not contain it
  either;
- the rebuilt input therefore matches the recorded input, and the engine is
  permitted to run;
- the engine writes the receipt again.

Verified directly rather than argued — the recorded input manifest holds **12**
`decision_audit_event` rows, `{'deadline_lock': 4, 'price_band_adjusted': 8}`,
and **no demotion row** (confirmed twice: by scanning the section, and by
`grep -c inactivity_rank_demotion` over the exported manifest → **0**, against
`price_band_adjusted` → present).

### The round was built to make the guard fire

The guard has **never fired in stored play** (448 index rows, worst
`index_change` −5.82), so a replay of any recorded round would reproduce the
*absence* of the firing and call it a pass. `handoff_readiness_v2/r34_inactivity_fixture.py`
constructs the firing and **asserts** it, exiting non-zero and naming what was
missing rather than resolving a round that proves nothing. It reuses
`v6_envelope_fixture.py::seed_round` verbatim for the competing teams, so the
field is realistic rather than a two-team toy.

One team is given a budget and a locked submission but **no marketing rows**,
which produces revenue of exactly zero — `bass_engine` builds its offer map from
`DecisionMarketing`, so a team with no rows takes no demand. Its carried index
is raised before the round so the demotion is a genuine **inversion** rather
than a firm that was last anyway.

**The resolved round (game 1, round 1):**

| Rank | Team | Index | Revenue |
|---:|---|---:|---:|
| 1 | Vertex Electronics | 53.24 | 1,440,000.00 |
| 2 | Cipher Systems | 52.29 | 792,000.00 |
| 3 | Helix Digital | 52.05 | 908,320.00 |
| **4** | **Cobalt Innovations** | **89.96** | **0.00** |

Cobalt outscored **all three** firms ranked above it, by roughly 37 index
points, and finished last. That is precisely the situation R34 exists to
explain, and it is now explained in stored data.

### Result

| | |
|---|---|
| Code revision | `a275010e714c0f7679768469d4a57c786962b70a` |
| Source tree digest | `d96a2c050789bd8825b839faeb8969cdcffe9a5fab9b4603e1d19842927155cf`, 427 files, `override: false` |
| `--require-env` | `python=3.10.12` — **verified** against this process |
| Backup restored | `game-1-round-1-20260917T093838185533Z.dump`, sha256 `ec69a715…` verified |
| **Input manifest** | **verified** — recorded `b596e06a…` == rebuilt `b596e06a…`. The engine was permitted to run |
| **Competitive hash** | **MATCH** — expected `767094f6854876fe08fb75b91d11a7d2b366cb176cabeab49c9f8df617425006` == actual |
| Narrative hash | **match** — `c7d9db88…` |
| Per-section diffs | **none** — `section_diffs` and `digest_diffs` absent from `replay-report.json`, which is how the command represents "nothing differed" |
| **Exit code** | **0** — *"Replay reproduced the round exactly."* |

**The receipt is reproduced, not merely ignored.** The exit code alone cannot
see this: the row is outside the competitive envelope, so a round whose
explanation went missing would still hash identically. Checked directly after
the replay — **1** demotion event, `user_id None`, endpoint
`engine:update_leaderboard`, payload identical to the original.

Evidence: `handoff_readiness_v2/evidence/determinism/r34-inactivity/`
(`recorded/`, `run-a-same-revision/`, `MANIFEST.sha256`).

---

## 4. Idempotency

**The property is skip-if-already-recorded, not overwrite**, and that is forced
rather than chosen: `DecisionAuditEvent.save` raises
`'DecisionAuditEvent records are immutable.'` on any row with a pk, and
`0070_audit_guards` installs database triggers that refuse `UPDATE` and
`DELETE` on `competition_decision_audit_event`. "Recompute and replace" is not
available and must not be attempted. A round recomputed after a correction, a
re-process or a reopen therefore keeps the receipt it already has — the honest
property for an append-only evidence table: the first recorded explanation of a
firing stands.

Implemented as one query before the writes — the set of `team_id`s that already
have an `inactivity_rank_demotion` row for that `(game, round)` — and a skip.

Proven four ways:

1. `test_ranking_the_same_round_twice_leaves_one_event` — stub context.
2. `test_a_correction_that_changes_the_field_still_leaves_one_event` — the field
   changes between passes and the count does not.
3. `test_a_team_demoted_in_two_different_rounds_leaves_one_event_each` —
   idempotency is **per round**, not per team; a firm that sits out twice is
   recorded twice.
4. **At production grain**, on the real resolved round after the replay:
   re-running `update_leaderboard` left **1** event with the **same row id**
   (`id: 13`) — printed `PASS`.

---

## 5. The dispute tooling needed no change — and here is the proof

CRV2-08's `InstructorTeamDecisionsView`
(`GET /api/games/{id}/instructor/teams/{team_id}/decisions/`) already returns
**every** `DecisionAuditEvent` for a `(game, team, round)` with no action
filter, and renders `event.user else 'system'`. The R34 row is therefore
surfaced with **no code change at all**.

Asserted end-to-end rather than assumed —
`TheDisputeToolingSurfacesItUnchanged` authenticates a real instructor, GETs the
endpoint, and asserts the demotion appears with `actor == 'system'`,
`endpoint == 'engine:update_leaderboard'` and
`payload.lowest_active_performance_index == '60.00'`. **No file outside
`leaderboard.py` was modified.**

**One honest limitation.** The *team-facing* `RoundResultsView` builds its
`price_adjustments` list with an explicit `action__in` filter over the three
price-band actions, so the demotion does **not** appear on the team's own
results screen. R34 asks for the firing to be visible in stored data and to land
where a dispute is answered, which the instructor drill-down satisfies. Whether
the team should also be told directly on its results screen is a **rules-owner
question I have not answered and did not implement** — it would need
participant-facing wording in both EN and zh-CN per GSP-CRV2-12.

---

## 6. What must not change, and did not

- **Ranking behaviour.** R32's enforcement stands exactly as merged. The
  published sort key, the shared-rank comparison and the classification are
  untouched; `_record_demotions` runs after the `LeaderboardEntry` rows are
  written and returns a count nothing reads.
- **R32's 14 tests pass unmodified.** No file under `core/tests/test_inactivity_rank_guard.py`
  was edited. They create no `Round` row, which is why the "no `Round` row
  records nothing and still ranks" branch exists — the same branch that
  protects the round-zero bootstrap, where R22 requires a shared opening rank.
- **The classification**, unchanged since before R32.
- **`test_scoring_dispositions`'s source-inspection guard** still passes:
  `update_leaderboard` still contains `commercially_inactive_team_ids` and still
  contains none of `material_revenue_floor(`, `is_commercially_inactive(`,
  `total_revenue(`, `revenue(`.

---

## 7. Commands, counts, durations

Focused tests via `backend/scripts/test-postgres`, each in its **own disposable
`postgres:16-alpine` container**, under `flock -w 1800 /tmp/globalstrat-backend-test.lock`.
The replay used a **separate** disposable container (`gsp-r34-pg`,
PostgreSQL 16, credential from `openssl rand -hex 32`, written only to a
session scratchpad file at mode 600, bound to `127.0.0.1` on an ephemeral port,
removed afterwards). The production database at `192.168.50.38` was **never
contacted** and **no systemd environment file was read**.

| # | Command | Result | Duration |
|---|---|---|---|
| 1 | `test-postgres core.tests.test_inactivity_demotion_audit --parallel 8` — **against the unmodified engine** | 18 tests, **6 failures + 7 errors** (intended red) | 18.98s wall |
| 2 | `test-postgres core.tests.test_inactivity_rank_guard --parallel 8` — pre-change baseline | 14 tests, **OK** | 14.86s wall |
| 3 | `test-postgres` × 8 labels `--parallel 8` (demotion_audit, rank_guard, scoring_dispositions, cc18_compliance, leaderboard_tiebreak, manifest_determinism, price_band, audit_integrity) | **226 tests, OK** | 43.6s wall / 17.98s tests |
| 4 | `dump_manifest_schema --check` | **"inventory is current."** | <1s |
| 5 | `./backend/scripts/check-participant-strings` | **PASS**, 2185 units, 0 findings, 0 suppressions | 0.12s |
| 6 | `git diff --check` | clean | — |
| 7 | `manage.py migrate --noinput` (replay stack) | OK | 18.84s |
| 8 | `manage.py load_scenario --file scenarios/consumer_electronics_2026.yaml` | scenario id 1 | 1.87s |
| 9 | `r34_inactivity_fixture.py --teams 4` (seed, close, resolve) | game 1, **guard fired**, schema_version 6 | 5.90s |
| 10 | `replay_round … --export-only` | exit 0 | 1.00s |
| 11 | `replay_round … --restore --confirm REPLAY-GAME-1-ROUND-1 --require-env python=3.10.12 --wait-narrative 0` | **exit 0 — reproduced exactly** | 15.38s |
| 12 | post-replay receipt + idempotency check | **PASS** (1 event, same row id) | <1s |

Baselines (1, 2) were taken **before** any edit, so every later result is
attributable. Run 3 was taken after the commit against a clean working tree, so
the green result anchors to the frozen commit rather than an uncommitted tree.

The pre-commit hook ran and passed: `aide-checks` revision **`77b8ced`**,
matching `checks/.aide-checks-rev`; 2 checks ran, **0 blocking failures**,
0 could-not-run. **No `--no-verify` was used and none was needed.**

Host: Ubuntu 22.04.5 LTS, Python 3.10.12, PostgreSQL 16 in Docker.

---

## 8. What I could NOT verify

- **No negative control names the demotion row inside the manifest envelope —
  and none can.** The row is written after the input snapshot, so it is
  correctly absent from both envelopes; there is nothing in the manifest to
  corrupt. Its integrity rests on the **audit chain** (`payload_sha256` plus the
  forward hash chain and the append-only triggers), not on the manifest. That is
  a different control, and I did not re-certify it — `test_audit_integrity`
  passed as part of run 3, which is not the same as proving the chain covers
  this new row end-to-end.
- **One environment, one round, one scenario, four teams, round 1.** Same host,
  OS, Python, timezone and locale. No cross-environment reproduction.
  **GSP-CRV2-09 owns the four-environment matrix; this is not a substitute.**
- **No full backend suite** — GSP-CRV2-09 owns it. Eight focused labels only.
- **No LLM-divergence runs** (`--wait-narrative 0`). The narrative hash matched,
  but this run does not re-establish that property.
- **A full reopen → re-close → re-process cycle was not exercised.** Idempotency
  is proven by re-running the ranking step over the resolved round and by the
  stub-context tests, not by driving the operator reopen path.
- **The constructed firing is not a natural one.** The carried index was set by
  the fixture to force the inversion. The mechanism and the recorded payload are
  real; the specific numbers are engineered.
- **Whether a demoted firm's `DecisionSubmission` always exists.** The drill-down
  returns early with `no_submission` when there is none, which would hide the
  receipt. `close_round` auto-creates an empty submission for every active team,
  so in the resolution path it exists — but I proved that only for the fixture's
  locked submission, not for every route into the view.

---

## 9. Proposed register wording for V2-119 — **not applied**

I did not edit `V2_FINDINGS_REGISTER.md`, `LAUNCH_CHECKLIST_V2.md` or any
`OWNER_RULINGS_*` file.

> **Question 2 ruled (R34, 2026-09-17) and implemented.** Both of V2-119's
> questions are now answered. A firing is visible in stored data as a
> `DecisionAuditEvent` — action `inactivity_rank_demotion`, endpoint
> `engine:update_leaderboard`, `user=None` so CRV2-08's instructor drill-down
> renders actor **`system`** — written in `leaderboard.py::update_leaderboard`
> where the demotion is decided, one row per demoted team per round. The payload
> answers the dispute directly: the firm's carried index, the lowest index among
> firms that competed and which firm held it, the rank received, the round, the
> classification, and an explicit `outscored_a_firm_ranked_above` flag that is
> **false** when the firm would have finished last regardless. Names as well as
> ids, per `price_band.audit_payload`. **The determinism envelope did not move:**
> no field was added to the hashed `performance` or `leaderboard` rows,
> `MANIFEST_SCHEMA_VERSION` is still **6** and `dump_manifest_schema --check` is
> clean, so no hash comparison shifts and no replay evidence needed re-running.
> **Replay proven, not assumed** — and it needed proving, because unlike the
> price-band receipts (written by `close_round`, *inside* the recorded input
> envelope) these rows are written by engine step 15, *after* `prepare_manifest`
> snapshots the input. A round in which the guard **actually fires** (constructed
> deterministically; the guard has never fired in 448 stored rounds) resolved and
> replayed byte-identically at `a275010`: input verified `b596e06a…`, competitive
> hash `767094f6…` reproduced, narrative hash matched, no section diffs, exit 0 —
> and the receipt was re-written by the replayed engine rather than merely
> ignored by the hash. **Idempotent by skipping, not overwriting**, which is
> forced by the immutable model and the `0070_audit_guards` append-only triggers:
> a recomputed round keeps the receipt it has (proven at production grain — same
> row id after a second ranking pass). **Ranking behaviour is unchanged**; R32's
> 14 tests pass unmodified. **The dispute tooling needed no change** and this was
> proven end-to-end against the instructor endpoint. Tests:
> `core/tests/test_inactivity_demotion_audit.py`, 18 tests, red against the
> unmodified engine (6 failures + 7 errors); merged regression 226 tests OK.
> Evidence: `completion/R34_INACTIVITY_DEMOTION_AUDIT_2026-09-17.md`,
> `evidence/determinism/r34-inactivity/`. **Open sub-question, not ruled and not
> implemented:** the *team-facing* results screen filters to price-band actions,
> so a demoted team is not told on its own screen; whether it should be is a
> rules-owner call needing bilingual wording per GSP-CRV2-12.
> **Development-grade, single-environment evidence. No gate closed.**
