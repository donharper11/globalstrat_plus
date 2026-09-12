# GSP-CRV2-12 — player-facing language sweep: completion

**Branch:** `crv2-12-language-completion`, cut detached from
`crv2-release-integration` at `46b4bbe`.
**Date:** 2026-09-12.
**Scope of this pass:** closing V2-069's four residual defects, Stage 3
bilingual parity, Stage 5's prevention control, and sweeping the strings the
previous day added.

**No gate is claimed closed.** Stage 4 (the two walkthroughs) was not
performed here and is not claimed. The integrated suite belongs to
GSP-CRV2-09 and was not run.

Evidence: `evidence/player-language/CRV2-12_BEFORE_AFTER.md` (before/after and
the check's failing and passing cases), `evidence/player-language/
AUTHORING_STANDARD.md` (the Stage 2 standard, written down once),
`evidence/player-language/STATIC_STRING_INVENTORY.md` (Stage 1, regenerated).

---

## 1. The four V2-069 defects

### (1) `round_not_accepting` interpolated the raw English status

**Needed:** a translated status label. `Round.STATUS_CHOICES` stores English
tokens (`pending|open|closed|processed`) and the token was dropped straight
into the Chinese sentence, so a zh-CN participant read
第 3 回合状态为“closed”.

**Done:** `ROUND_STATUS_LABELS` and `round_status_label()` in
`core/utils/participant_messages.py`, applied at the one interpolation site
(`views/decisions.py`, `IsRoundOpen`). Wording only; the condition, threshold
and control flow are untouched.

**Proven by:** `test_chinese_refusal_carries_no_english_status_token` asserts
the rendered zh-CN refusal contains no run of three or more Latin characters
for each non-open status — the defect verbatim, not a proxy.
`test_english_refusal_is_unchanged` pins the English sentence that CRV2-12
already shipped. `test_every_authored_round_status_has_a_participant_label`
reads `STATUS_CHOICES` from the model, so a fifth status fails the suite.
Assertion **A5** of the static check fails the build on the same condition.

### (2) `IsTeamMember` named the wrong action on seven read-only routes

**Needed:** a read-flavoured refusal. Eleven view classes carry
`IsTeamMember`; seven expose only `get` (`DecisionSummaryView`,
`RDContextView`, `ProductContextView`, `MarketingContextView`,
`StrategyContextView`, `FinanceContextView`, `TalentContextView`). All eleven
said "You do not have permission to change this team's decisions."

**Done:** the guard picks `permission_denied_read` for
`permissions.SAFE_METHODS` and `permission_denied` otherwise. One added
catalogue key; the guard's return values are unchanged.

**Proven by:** `test_a_refused_read_names_viewing` (GET/HEAD/OPTIONS),
`test_a_refused_write_still_names_changing` (POST/PUT/PATCH/DELETE),
`test_a_refused_read_is_localised` (zh-CN), and
`test_the_seven_read_only_routes_are_still_seven`, which re-derives the count
by walking `permission_classes` across every class in the module — so adding a
write handler to one of those seven fails the suite rather than silently
invalidating the wording decision.

The seven were enumerated from the view classes' declared
`permission_classes`, not from grepping for the new helper.

### (3) The Summary view returned storage names

**Needed:** business wording, localised. `SummaryPage.js` renders
`lock_blockers` and each category's warnings verbatim — there is no `t()`
around them — so `rd_budget is 0.` and `Budget allocation required.` reached
the participant exactly as emitted.

**Done:** twelve strings replaced by catalogue calls. Four of them
(`budget_required`, `product_portfolio_required`, `marketing_mix_required`,
`strategy_mix_required`) now reuse the keys the **lock refusal** already used
rather than new sentences, and the projected-cash blocker reuses
`cash_negative` at the lock path's `,.2f` format. Before this pass the Summary
and the lock stated that one rule with two different sentences and two
different money formats.

Full before/after table: `CRV2-12_BEFORE_AFTER.md` §1(3).

**Proven by:** `test_summary_returns_no_storage_name_in_either_language`
sweeps every blocker, warning and error in the response for six storage names
in both languages; `test_zero_budget_warning_names_the_business_object` and
`..._is_localised` pin the replacement for the finding's own example;
`test_lock_blockers_are_localised_not_english_only` asserts every blocker a
zh-CN participant receives contains Han characters.

### (4) `get_user_language` queried `Enrollment` on every permission check

This is a performance defect, not a language one, so it was **measured
first**.

**Measurement.** A GET of the Decision Summary with no `Accept-Language`
header, counting statements that read `"enrollment"."language"`:

| | language-resolution queries |
|---|---:|
| helper as it read before CRV2-12 | **2** |
| after memoisation | **1** |

Two is what this single endpoint costs — the permission check and the view
body each resolved the language. `views/decisions.py` calls the resolver from
twenty-four places, so a request crossing more of them paid more.

My first metric counted every statement containing "enrollment" and gave
4 → 3, which measures nothing: `IsTeamMember`'s own membership check reads the
same table and the supply-chain categories touch `sc_sinosure_enrollment`. I
dumped the SQL rather than guess a discriminator.

**Decision: fixed, because it was cheap.** A per-request memo on the request
object — the same shape `core/utils/auth_context` already uses for the decoded
JWT. The resolved value cannot change within a request, so it changes no
answer, only how often the answer is computed. `setattr` failure is caught, so
a request-like object that refuses attributes still gets the right answer
without the saving. The pre-existing bare `except:` was preserved rather than
narrowed, to keep the change to caching alone.

**Proven by:** `test_language_is_resolved_once_per_request`, which runs the
same request twice — once with `core.views.decisions.get_user_language`
patched to the pre-CRV2-12 body — and asserts 2 before and 1 after. The test
carries the measurement, so a regression re-opens the finding.

---

## 2. Stage 3 — bilingual parity, demonstrated

| catalogue | entries | language gaps | placeholder mismatches |
|---|---:|---:|---:|
| `participant_messages.MESSAGES` | 99 | 0 | 0 |
| `participant_messages.FIELD_LABELS` | 35 | 0 | — |
| `participant_messages.ROUND_STATUS_LABELS` | 4 | 0 | — |
| `cohort_messages.MESSAGES` | 6 | 0 | 0 |
| `locales/en.json` ↔ `zh-CN.json` | 2000 keys each | 0 | 0 |

`test_every_message_renders_in_both_languages_with_its_values` renders all 99
messages in **both** languages with a sentinel per placeholder and asserts
every sentinel survives — so parity is demonstrated by rendering, not asserted
by inspection. Rendered samples for the money/count/round cases are in
`CRV2-12_BEFORE_AFTER.md` §3.

The interpolation case worth naming: `rd_prereq_features_detail` renders
"2 of 4 features qualify" in English and 「4 项中已有 2 项符合」 in Chinese —
the two counts appear in the **opposite order**. That is exactly why parity is
asserted on the placeholder *set* and verified by rendering rather than by
comparing string shape, and why a positional format would have been wrong
here.

The only two locale values identical across languages are `login.title` and
`instructor.brand`, both `GLOBALSTRAT` — a brand name, correctly untranslated.

### A parity gap the sweep found, and repaired

`MarketDefinition`, `PlatformGenerationDefinition` and `FeatureDefinition`
each carry a `name_zh`, and `get_localized_field` reads it with an English
fallback. **Fourteen call sites passed `.name` instead**, so a Chinese refusal
carried an English market, platform or feature name. One Summary response
could name the same market two ways: the active-presence branch used
`presence.market.name` while the entering-market branch two blocks below
already used `get_localized_field`.

Repaired at all fourteen sites. `TeamProduct.name` is deliberately left raw —
a team names its own product during play and there is no translated
counterpart. Proven by
`test_a_market_name_reaches_a_chinese_participant_in_chinese` and
`test_the_same_market_still_reads_in_english_for_an_english_request`, and
prevented by assertion **A7**.

---

## 3. Stage 5 — the prevention control

`backend/scripts/check-participant-strings` (528 lines, standard library
only, reads the tracked source tree; never a database, a server or a model
response), configured by `backend/scripts/participant-strings.config.json`.

Seven assertions, each mapped to a defect this repository actually shipped:

| | assertion | defect |
|---|---|---|
| A1 | every catalogue entry carries every shipped language | V2-061 |
| A2 | an entry's placeholders are identical across languages | Stage 3 |
| A3 | no catalogue sentence contains a storage/model field name | F-PL-01 |
| A4 | no participant-facing literal bypasses the catalogue | V2-069.3 |
| A5 | every `Round.STATUS_CHOICES` value has a participant label | V2-069.1 |
| A6 | locale key and placeholder parity, both catalogues | Stage 3 |
| A7 | no raw scenario-authored name interpolated into a message | this pass |

Exit codes follow `checks/README.md`: `0` clean, `1` findings, `2` could not
run. Zero findings over zero examined units is exit 2, never a pass.

**It is not Stage 1's `--check`.** `generate_inventory.py --check` is an
inventory-freshness control: it fails when wording changed without refreshing
the evidence, and it passes happily on a brand-new English-only refusal as
long as the inventory lists it. This asserts the property instead. Both are
kept and both are green.

### Passing case and failing case

On the real tree, planting an untranslated message that also names a storage
field:

```
clean       → units=2154 findings=0   exit 0
with plant  → units=2155 findings=1   exit 1
             A1 …MESSAGES['crv212_plant_do_not_ship'] has no zh-CN wording.
plant removed → units=2154 findings=0 exit 0   (file restored byte-identical)
```

`backend/scripts/check-participant-strings-selftest` proves every assertion
can fail, building a disposable tree per case: **22 ok, 0 failed**, covering
A1, A2, A3, A4, A5, A6 (missing key), A6 (placeholder skew), A7, a stale
suppression, and two could-not-run cases (a suppression with no stated reason;
a scope entry naming a file that no longer exists). Each case also asserts the
clean tree passes first, so a checker that fails everything cannot score.

**Where it fails a build:** `backend/core/tests/test_player_language_guard.py`
runs it inside the backend suite — the gate GSP-CRV2-09 runs — and
`.github/workflows/player-language.yml` runs the selftest and then the check
in CI.

It is deliberately **not** a vendored aide-checks check:
`checks/config/schema.json` sets `additionalProperties: false` on its check
set and `checks/.aide-checks-rev` pins the package, so adding one there means
forking a package whose entire design is that it is never forked.

### The check found a bug in itself on its first run

Its first real-tree run produced 20 findings. Six were **false positives in
A3**: it matched placeholder *names* (`{unlock_round}`, `{max_teams}`,
`{team_size_max}`) which are substituted before anyone reads the sentence. A3
now masks placeholders first. Four more were speculative `allow_literals`
entries I had written into the config in advance — and the staleness assertion
rejected every one, which is why the shipped allowlist is empty. Seven were
service-layer diagnostic records correctly naming a model for an engineer,
which is what `participant_payload_dicts` now separates. Three were genuine:
the duplicated permission sentences, repaired.

---

## 4. The strings the previous day added

Swept to the same standard rather than exempted.

**Price band (CRV2-10 Stage 5)** — `price_band_alert`, `price_blank_alert`,
`price_band_adjusted`, `price_not_offered`, `price_blank_applied`, and the
frontend `price_band_range` / `price_out_of_band` / `price_blank` /
`price_adjustments`. All pass A1/A2/A3/A6 unchanged: both languages, matching
placeholders, no storage names, money formatted by the caller via
`_fmt_money`. **One change:** their call site in
`serializers/decisions.py` passed `market_name=obj.market.name`, so the
Chinese alert carried an English market name; it now reads through
`get_localized_field`. The product name stays raw, deliberately.

**Cohort caps (CRV2-10 Stage 6)** — all six `cohort_messages` entries pass
unchanged. `section_full` was flagged by A3 for containing `max_teams` and
`team_size_max`; both are placeholder names, and the flag was the A3 bug
described above, not a defect in the message.

**Round zero and preferences (CRV2-11)** — the added locale keys
(`round_control_title`, `close_round_confirm`, `advance_round_confirm`,
`reopen_round_title`, …) pass A6: present in both catalogues with identical
`{{…}}` placeholders. No change needed.

---

## 5. Every command run

All Django tests ran through `backend/scripts/test-postgres <labels>` under
`flock -w 1800 /tmp/globalstrat-backend-test.lock`. That script starts its own
disposable PostgreSQL container per invocation and removes it on exit; it
never reads a systemd environment file and never touches the production
database at 192.168.50.38. No full suite was run — CRV2-09 owns it.

| # | command | result | test time | wall |
|---|---|---|---:|---:|
| 1 | `test-postgres test_participant_messages test_decision_limits test_cohort_caps test_price_band` (baseline, before any edit) | **97 OK** | 2.273s | 14.689s |
| 2 | as above + `test_rd_costs`, after the catalogue and Summary edits | **113 OK** | 2.470s | 13.394s |
| 3 | same five, after the R&D prerequisite edits | **113 OK** | 2.524s | 31.581s |
| 4 | same five, after the permission-message edits | **113 OK** | 2.480s | 13.159s |
| 5 | `test-postgres test_crv2_12_language test_player_language_guard` (first run) | 20 ran, **1 failed** — the query metric, see §1(4) | 0.284s | — |
| 6 | SQL dump probe, then the five-module regression | dump failed by design; **113 OK** | 2.584s | — |
| 7 | new tests, then six-module regression | **20 OK** / **122 OK** | 0.289s / 2.696s | 25.335s |
| 8 | final: new tests, then six-module regression | **22 OK** / **122 OK** | 0.366s / 2.617s | 25.329s |

Non-database commands:

| command | result |
|---|---|
| `backend/scripts/check-participant-strings --repo .` | units=2154 findings=0 suppressions=0, **exit 0** |
| `backend/scripts/check-participant-strings-selftest` | **22 ok, 0 failed**, exit 0 |
| real-tree plant → check → remove → check | exit **0 → 1 → 0**, file restored byte-identical |
| `generate_inventory.py` then `--check` | wrote 2152 candidate rows, **exit 0** |
| `checks/bin/run-checks --fast --repo=.` (direct) | ran 2, 0 blocking failures, **exit 0** |
| the same runner, invoked by `.husky/pre-commit` | **exit 2**, revision mismatch — see below |
| `git diff --check` | clean |

### On the commit policy

The handoff anticipated an aide-checks revision mismatch and sanctioned
`--no-verify`. **It was right, and my first reading of it was wrong.** The
commits were made with `--no-verify`, as `.husky/pre-commit`'s own header
sanctions ("Bypassable with `--no-verify`; the deploy gate is the layer that
is not"). The deploy gate is untouched and still blocking.

The correction is worth recording because it is a trap for the next builder.
Run directly, the assertion **passes**:

```
$ checks/bin/run-checks --fast --repo=.
aide-checks: revision e710f26 matches …/checks/.aide-checks-rev
aide-checks: ran 2, skipped 1, blocking failures 0, could-not-run 0   → exit 0
$ checks/bin/run-checks --print-revision
e710f26
```

Run by the hook during `git commit`, the same runner refuses:

```
run-checks: ERROR revision mismatch — could not run.
run-checks: runner built from : 46b4bbe
run-checks: repo vendored at  : e710f26
                                                                     → exit 2
```

`46b4bbe` is this repository's HEAD, not an aide-checks revision.
`_rev_running()` in `checks/bin/run-checks` reports `git rev-parse --short
HEAD` whenever it decides it is running from the package's own checkout —
the case the README describes as "Run from the package's own git checkout,
HEAD is the authority instead" — and otherwise falls back to the stamped
`AIDE_CHECKS_BUILT_FROM`. Under the hook's environment that branch is taken
even though `checks/` is a vendored subdirectory of this repo and not an
aide-checks checkout, so the runner reports this repo's HEAD as its own
revision and then finds it disagrees with the vendored marker.

I did not fully isolate the trigger. It reproduces only under the hook; a
direct invocation with the hook's exact argument form does not reproduce it,
and forcing `GIT_DIR=.git` (a relative path, which in a linked worktree is a
file rather than a directory) does not either. What is certain is the
observable: **every `git commit` in this repository is refused by the hook
with exit 2**, for a reason unrelated to the commit's contents, and the
condition is a property of the vendored integration rather than of this
branch — nothing in this branch touches `checks/`. Recorded as V2-079.

The consequence for an auditor: the hook was **not** a gate that passed on
this work. The real checks were run directly and are reported above and in
§3 — `run-checks --fast` clean at exit 0, the participant-string check clean,
its selftest 22/22.

---

## 6. Findings

Register entries are supplied separately in the register's format; the
register itself was not edited. Proposed IDs continue from V2-074.

- **V2-075 — scenario-authored names interpolated raw (repaired here).**
  Fourteen sites passed `.name` into a localised message.
- **V2-076 — `SummaryPage.js` carries untranslated English literals (open).**
  `statusLabel` ("Complete", "Needs review", "Blocked", "Not started"), the
  four supply-chain category labels ("Sourcing", "Logistics", "Trade Finance",
  "Inventory"), the `guidanceFor` fallbacks, and `Fix in {label}`. Not
  repaired: the frontend is owned by the concurrent browser-verification
  builder this session, and editing it would collide.
- **V2-077 — price-band adjustment notices render names from the stored audit
  payload (open).** `price_band.audit_payload` captures `market_name` at close
  and `results_api.py` renders the notice from the record. A zh-CN participant
  sees the English market name on the results surface. **Not repaired here:**
  changing what is recorded is engine behaviour, which this handoff must not
  change.
- **V2-078 — `IsTeamMember` runs its membership query twice per request
  (observation).** Two identical `SELECT 1 AS "a" FROM "enrollment"` statements
  appear in the captured SQL. Not a language defect; not repaired.
- **V2-079 — the aide-checks pre-commit hook refuses every commit in this
  repository (open).** Under the hook the runner reports this repo's HEAD as
  its own revision and fails the assertion against the vendored `e710f26`;
  run directly it reports `e710f26` and passes. Unrelated to any commit's
  contents and to this branch, which does not touch `checks/`. The effect is
  that the pre-commit layer is permanently bypassed here, so it protects
  nothing until it is re-vendored or the resolution is fixed.

---

## 7. What remains for the browser walkthrough to confirm

Stage 4's two walkthroughs were **not** performed here and nothing about them
is claimed. The browser pass should confirm, in both languages:

1. A **refusal at submit** and a **lock refusal** — that the Summary's
   blockers render as the catalogue's sentences and name a decision area.
2. A **warning versus a refusal** — the price-band alert (accepted, saved)
   against the blank-price lock refusal (nothing saved), that they read
   differently on screen.
3. A **read-only refusal** — a context endpoint refused to a non-member now
   says "view", not "change".
4. The **R&D prerequisite rows** on the R&D page in zh-CN — these were English
   until this pass and render as `{requirement} — {detail}`.
5. **Market names inside Chinese sentences** — the Summary strategy warnings,
   with a scenario whose markets have `name_zh` populated. Where `name_zh` is
   blank the English name is the intended fallback, not a defect.
6. The untranslated `SummaryPage.js` literals in V2-076, which a zh-CN
   walkthrough will show beside now-Chinese backend text.

**Frontend verification I could not do:** `node_modules` is absent in this
worktree, so `npm ci`, `npm test`, `npm run build` and ESLint were not run. I
changed no frontend file. What that leaves unverified is only that the
unchanged frontend still builds — no claim of mine depends on it — but the
locale catalogues I asserted parity over (`en.json`, `zh-CN.json`) were
checked by parsing the JSON, not by loading them through i18next.

---

## 8. Auditor preflight checklist (EXECUTION_PROTOCOL)

**Did inventory start from registered routes/models/jobs, not only code using
the new abstraction?** Yes. The seven read-only routes came from an AST walk
of `permission_classes` over every view class in `views/decisions.py`; the
storage vocabulary for A3 from the Django model modules
(`x = models.Field(...)`, 927 distinct names); the round statuses from
`Round.STATUS_CHOICES`; the locale keys from both JSON catalogues. None of it
was derived by grepping for `participant_message`.

**Is there an active legacy or alternate entry point?** Yes, two, both
recorded rather than silently covered. `results_api.py` renders price-band
notices from the stored audit payload, whose names were captured at close
(V2-077). And the frontend renders its own literals outside the backend
catalogue (V2-076).

**Does a failure/refusal audit survive rollback?** Not applicable — no audit,
transaction or rollback behaviour was touched. The related risk was that
`funding_need.describe` is recorded by `advance_round`; its English rendering
is byte-identical to before and pinned by a test, so recorded refusals did not
move.

**Is each correlation ID generated once and identical in response/audit/log?**
Not applicable; no correlation IDs were touched.

**Is background/external work delayed until the outer transaction commits?**
Not applicable; no background or external work.

**Do claimed environment values describe the executing process?** Yes. Python
3.10.12, Django 5.2.4, branch `crv2-12-language-completion` from `46b4bbe`,
every test in a disposable container created by `test-postgres` under the host
lock. Durations in §5 are from `time` on the executing command.

**Does provenance identify runtime bytes, including required untracked
files?** Yes. Everything the control needs is tracked: the checker, its
selftest, its config, the two test modules and the workflow. No untracked file
is required at runtime. The check reads the tracked tree via `git ls-files`
semantics (explicit path scope) rather than the working directory at large.

**Do README commands run exactly as written against stored artifacts?** Yes,
verified for the commands this branch adds or touches:
`generate_inventory.py` and `--check`, `check-participant-strings`,
`check-participant-strings-selftest`, and `test-postgres <labels>`. The
CRV2-07 load and calibration harnesses were not run.

**Do P0/P1/P2 labels match their definitions?** The four proposed findings are
labelled in the register entries supplied with this report: V2-075 P2
(repaired), V2-076 P2, V2-077 P2, V2-078 P3/observation. None is a
correctness or scoring defect; all are language or efficiency.

**Does each negative test prove mutation/engine execution did not occur?**
The refusal tests assert on response content and do not claim mutation was
prevented — that is not what this handoff changed, and no test here should be
read as a mutation guard. The one assertion that does carry that weight is
`test_english_is_byte_identical_to_the_pre_crv2_12_sentence`, which proves the
engine-recorded sentence is unchanged. Engine behaviour was not modified: every
edit is wording, localisation, or the static check, and the 122-test focused
regression across the decision, pricing, cohort and R&D-cost modules is green.
