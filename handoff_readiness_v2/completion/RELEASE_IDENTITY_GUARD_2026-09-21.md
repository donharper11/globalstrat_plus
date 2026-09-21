# Release identity guard, provenance completeness, and the latent model blend — 2026-09-21

**Branch:** `crv2-01-release-identity-guard`, cut from `crv2-release-integration` at `25ff947`.
**Commits:** `3d3a0a2` (R31 latent blend), `dd3b40c` (A-03 code half + A-04), plus the commit carrying this report.
**Claims no gate closed.** A-03 is *not* closed by this branch: the code half is done, the deployment half is an operator action described in §6 and has not been performed. Nothing here touched production, its database, its environment file or any systemd unit.

Findings addressed: **A-03**, **A-04** and the latent retrieval blend noted under **A-01**, all from `GSP-CRV2-09_GO_NO_GO_2026-09-16.md` (unmerged branch `crv2-09-go-no-go-2026-09-16`). Related register cells read to the end: V2-054, V2-120, V2-016; ruling R31.

---

## 1. State found at head (`25ff947`) — inventory before implementation

Nothing in scope was already done. Each item was confirmed in the code, then pinned by a test that fails on the unmodified tree (§4).

| Item | Found at head |
|---|---|
| A-03 guard | `resolution_manifest.resolve_code_revision()` returns a configured `GIT_REVISION` verbatim (only a character-class regex and a list of placeholder words). `build_identity.require_identified_build()` refuses only when `code_revision` ends in `-dirty`, a suffix produced solely by the non-production git-guess branch. A hand-set value never carries it, so with `COMPETITION_REQUIRE_CLEAN_BUILD=true` a wrong revision could not be refused. |
| A-03 detection | `check_release_identity` existed with its own private `_git()` helper and its own comparison: two implementations of one question, and only the unenforced one was right. It treated "git returned nothing" as "immutable build", so a missing git binary or an unreadable repository reported **success**. No tests. |
| A-03 digest timing | `source_tree_digest()` cached on first call. Nothing called it at start (`core/apps.py` had no `ready()`), so the recorded digest described the disk at the first resolution, not the code the process loaded. |
| RD-03 | `recover_competition_round` compares `manifest.code_revision` with `resolve_code_revision()` as strings. With a drifted `GIT_REVISION`, the running side of that comparison is false, so a drifted deployment would *match* manifests it wrote while drifted. |
| `resolve_stored_revision` | Present, correct as far as read, no tests. The committed map (`evidence/v2-048/commit-map-2026-09-04.txt`, 434 entries + header) carries all six pre-rewrite production revisions named in the re-audit. |
| A-04 | `SOURCE_SUFFIXES` = `.py .json .yaml .yml .cfg .toml .ini`; `requirements.txt` outside the digest. `settings.py` loads `backend/.env` and reads ~25 environment variables; none of the effective values was recorded anywhere. |
| Latent blend | `coherence.py::calculate_coherence(context, skip_rag=False)` — **the default was `False`** — called `_calculate_rag_coherence` and stored `0.6 × formula + 0.4 × model score` into `blended_score`, `rag_score` and `breakdown['rag_evaluation']`, all inside the hashed `coherence` section and read by `grading.py`. Sole production caller `advance_round.py:880` passes `skip_rag=True`. |
| Envelope | `MANIFEST_SCHEMA_VERSION = 6`. `ResolutionManifest.environment` is outside `input_sha256`, `output_sha256`, `narrative_sha256` **and** outside the audit chain's projection (`audit_chain.UNCHAINED_FIELDS`). |

I did **not** verify the live production state (`GIT_REVISION=0fd9a39` vs. disk) myself: doing so means reading `/etc/globalstrat-plus.env` or the service's process environment, both out of bounds. It is taken from the task statement.

## 2. Changes

### 2.1 A-03 — code half (`dd3b40c`)

`backend/core/services/build_identity.py`
- `release_identity(advertised=None, root=None)` — the **single** implementation. Statuses: `verified`, `immutable` (the only two that pass), `unset`, `invalid`, `dirty`, `drifted`, `unverifiable`. Every failing message ends with the same four-step operator procedure (`OPERATOR_PROCEDURE`).
- A revision must be a **full** commit hash (`^[0-9a-f]{40}$` or 64). Labels, tags and abbreviations are refused: they cannot be compared with HEAD and RD-03 compares whole strings.
- "Is this a checkout?" is decided by **finding `.git`** at or above the repository root (directory, or a worktree's pointer file), not by whether git answered. `.git` present + git unusable ⇒ `unverifiable` ⇒ refused. No `.git` ⇒ `immutable` ⇒ today's behaviour, as instructed.
- `require_identified_build()` with the flag on now refuses on: the existing `-dirty` suffix (message unchanged); any non-passing `release_identity` status; and `loaded_source_drift()` — the disk no longer matching the start-of-process digest. **With the flag off it returns before any of this and never runs git** (pinned by a test that makes `subprocess.run` raise).
- `prime_source_tree_digest()` called from the new `CoreConfig.ready()`. Measured cost: ~20 ms for 429 files. Idempotent; failures swallowed so it cannot stop a process starting.
- Why the drift check is needed and the HEAD check alone is not: git describes the *disk*. A hotfix committed and correctly advertised, with workers not restarted, passes every git test while old code resolves. Comparing the disk with the start digest is what ties "HEAD is clean" to "the loaded code is HEAD". (Gunicorn runs 32 sync workers without preload and recycles each after ~1000 requests, so workers of different ages are normal; each records its own start digest honestly.)

`backend/core/management/commands/check_release_identity.py` — now a thin wrapper over `release_identity()`. Exit codes unchanged (0/1); stderr is prefixed with the status in brackets. Behaviour changes: a non-hash label and an unreadable checkout now exit 1 (both previously could exit 0).

`backend/core/management/commands/recover_competition_round.py` — where the flag is on, the running revision is verified before it is used for the RD-03 comparison; refusal unless `--allow-code-revision-mismatch` (the existing override, kept so an incident restore stays possible). The status is written to the durable recovery audit as `running_release_identity`. Flag off: unchanged.

`backend/core/tests/test_manifest_determinism.py::test_clean_build_gate_accepts_a_named_revision` **asserted the defect** (the label `abc123` accepted under the flag). Rewritten: a full hash is accepted on an immutable build; the label is refused. This is the only pre-existing test changed.

**Recovery through the V2-048 commit map — considered, not implemented.** Translating a stored pre-rewrite revision before the RD-03 comparison is not "clearly safe", and has no practical value at head:
1. filter-repo *changed file contents* in the rewritten commits (it purged a credential). A translated commit is the same history, not provably the same runtime bytes; equating them in a guard whose purpose is "same build" would overstate what is known. `source_tree_sha256` is the honest comparator and only 5 of 15 stored manifests carry it.
2. For the comparison to pass, the *running* build would have to be the translated old commit — schema-version-2 code that predates this command. No build that contains the translation could ever be the build it translates to.
3. Those rounds are reachable today with `--allow-code-revision-mismatch --restore-only`, which is the correct posture for a round whose producing code cannot be re-run.
Remaining work, if wanted: have the *refusal message* name the translated commit (`resolve()` is importable) so the operator knows which commit to check out. Informational only; not done here.

### 2.2 A-04 (`dd3b40c`)

- `requirements.txt` joins the digest via `SOURCE_FILE_NAMES` (exact names, not a `.txt` suffix — `notes.txt` and `.env` stay out, pinned by test).
- New `backend/core/services/runtime_config.py`: an **explicit allow-list**, never a sweep of `settings`/`os.environ`. Recorded: `ENVIRONMENT`, `IS_PRODUCTION`, `DEBUG`, `TIME_ZONE`, `USE_TZ`, `LANGUAGE_CODE`, `COMPETITION_REQUIRE_CLEAN_BUILD`, `COMPETITION_RAG_AFFECTS_COHERENCE`, `COMPETITION_RECOVERY_ENABLED`, `SC_ENGINE_STRICT`, Qdrant host/port/collection, embedding model/dimension, textbook collection/model; plus derived entries — **effective** purpose→model routing (defaults with `LLM_PURPOSE_MODELS` applied, unknown override keys kept visible), the gateway endpoint reduced to `scheme://host:port/path` (userinfo, query and fragment dropped, because a URL can carry a password its variable name does not warn of), `llm_gateway_configured` as a boolean, LLM concurrency/timeout, DRF throttle rates.
- **Never recorded or hashed:** `SECRET_KEY`, `JWT_SECRET_KEY`, `LLM_GATEWAY_KEY`, `DATABASES` (any part). Tests: a secret-shaped name on the allow-list fails; planted secret values (including in the URL's userinfo, query and fragment) must not appear in the record; **rotating only the secrets leaves the digest unchanged**, so the digest cannot confirm a guessed credential.
- Stored in `ResolutionManifest.environment` as `runtime_config`, `runtime_config_sha256`, `requirements_sha256`, `installed_packages_sha256`, `installed_packages_count`.

**Envelope check (the instruction's STOP condition) — not triggered.** `environment` is outside all three hashed envelopes; no model field, no migration, no section change; `MANIFEST_SCHEMA_VERSION` is still 6. `test_a_resolved_round_records_it_and_hashes_none_of_it` resolves a real round and asserts the new keys appear in `environment`, appear in none of `input_manifest` / `output_manifest` / `narrative_manifest`, and that the stored hashes still equal the hash of those bodies.

**One consequence to know:** adding `requirements.txt` changes the value of `source_tree_sha256` for otherwise identical code. Digests were already per-commit (any commit changes them), and replay evidence is evidence for its own commit, so no stored evidence is invalidated that was not already bound to another commit. `replay_round` against a round resolved *before* this change, run *after* it, will report a source mismatch — as it would for any later commit.

### 2.3 Latent model blend (`3d3a0a2`)

`calculate_coherence`: the retrieval branch is **removed**; default is now `skip_rag=True`; `skip_rag=False` raises `RuntimeError('R31: …')` **before any write**. Refuse rather than ignore, because a caller that believes retrieval is graded when it is not is its own defect (the same reasoning V2-016's rework applied to the retired flag). The production path stores byte-for-byte what it stored before (`rag_score` NULL, `blended_score = formula_score`, same log line), so no hash moves. `rag_score` stays in the row because the column is part of the hashed section's shape. `update_coherence_with_rag` (Phase-2 instructor commentary, writes no competitive field) is untouched and pinned by a new test. `_calculate_rag_coherence` is now unreferenced outside `test_engine.py`; left in place — deleting it is cleanup, not this item.

`STATIC_STRING_INVENTORY.{json,md}` re-cut: `coherence.py` line numbers shifted and the log string lost its RAG suffix; 2,234 rows before and after; `generate_inventory.py --check` clean.

**`grading.py::communication_quality` — described, not touched.** `_extract_communication_quality` (`grading.py:222`) still averages the model's `overall_score` from `TeamCommunication.evaluation` and is registered in `COMPONENT_EXTRACTORS` (`:249`). It reaches a grade only if an instructor's `GradingRubric` selects that component; the existing test docstring records 0 rubric rows in the live database at the time it was written (not re-verified by me). It is pinned as-is by `GradingSurfaceTests`. Whether R31 extends to it is the owner's question.

## 3. New defects found (recorded before repair)

| # | Defect | Disposition |
|---|---|---|
| N-1 | `check_release_identity` reported success when git could not run inside a checkout (empty output read as "immutable build"). | In scope; repaired in `dd3b40c` (`unverifiable`). |
| N-2 | `calculate_coherence`'s **default** was the model path (`skip_rag=False`), so the latent blend needed only a forgotten argument, not a deliberate one. Worse than the re-audit described. | In scope; repaired in `3d3a0a2`. |
| N-3 | `llm_runner.py:41` comment still said `communication_eval` "feeds 10% of graded coherence" — false since R31. | Comment corrected in `3d3a0a2`. |
| N-4 | `test_clean_build_gate_accepts_a_named_revision` encoded the A-03 defect as expected behaviour. | Rewritten in `dd3b40c`. |
| N-5 | The production units' `WorkingDirectory` is `/home/ubuntu/projects/globalstrat+/backend` — the shared **development** checkout, whose branch the re-audit (A-09) saw move mid-run. Not a code defect; it is why A-03 recurs. | Out of scope (deployment). §6. |
| N-6 | `ResolutionManifest.environment` is outside the audit chain, so the new configuration record is not tamper-evident. `source_tree_sha256` and `code_revision` are chained. | Not repaired: chaining it means a projection change that alters how existing rows verify. Proposed as register text. |
| N-7 | Harnesses that run `GLOBALSTRAT_ENV=production` with `GIT_REVISION=$(git rev-parse HEAD)` and do **not** set `COMPETITION_REQUIRE_CLEAN_BUILD=false` (`post-close-disputes/harness/{start_stack,ownership_scan,build_completed_game}.py`, `decision-rules/harness/{stack,stage1_probes}.py`) previously resolved from a dirty tree, because a hand-passed HEAD never carried `-dirty`. They will now be refused on a dirty tree. That is the guard working, and those harnesses were claiming a clean build they did not check; but it is a behaviour change for anyone re-running them mid-edit. Harnesses that set the flag `false` or use a label with the flag `false` are unaffected. | Intended; not edited (frozen evidence harnesses). |

## 4. Red, then green

All via `cd backend && flock -w 1800 /tmp/globalstrat-backend-test.lock scripts/test-postgres <labels>` (disposable `postgres:16-alpine`; never the production database). Wall times include waiting for the shared lock.

**Red — new tests against unmodified production code** (tests and the then-unreferenced `runtime_config.py` only):
`… test_release_identity_guard test_resolve_stored_revision test_runtime_provenance test_r31_llm_not_in_grades` → `Ran 58 tests … FAILED (failures=18, errors=4)`, 18 s.

Failing, by item:
- A-03 guard: stale revision accepted; four labels accepted (`release-2026.09`, `abc123`, `HEAD`, uppercase hex); HEAD + modified tracked file accepted; unusable git accepted; code changed after start accepted; refusal message absent; `CoreConfig.ready()` did not take the digest.
- A-03 command: label accepted on an immutable build; unusable git exit 0; command and guard disagree.
- A-04: changed pin did not move the digest; real `requirements.txt` not in the digest; fingerprint lacks the config digest (×2, `KeyError`).
- R31: refusal absent and model called; default call consults the model and stores a blended score; source still routes to the model.
- Distinct tests red: 19 (15 failures, one of them with four sub-cases, and 4 errors). Two of the errors are on names that did not exist yet (`_find_git_marker`, `prime_source_tree_digest`): weak red, not counted as evidence; each has a behavioural sibling above that failed on an assertion. The other two errors are genuine `KeyError`s on the missing fingerprint keys.

**Red — recovery**, run separately because the test was written after the first red run: original `recover_competition_round.py` restored from `HEAD`, everything else modified → `RecoveryComparisonTests`: `Ran 3 … FAILED (failures=1, errors=1)`, 11 s. (The drifted build matched the manifest sharing its stale revision.) File then restored to the modified version; verified by grep.

**Green:**
| Command labels | Result | Wall |
|---|---|---|
| the four new/extended modules | `Ran 61 tests … OK` | 3m23s |
| those + `test_manifest_determinism test_release_provenance test_competition_hardening test_audit_integrity test_operator_concurrency test_rd_scoring_retired test_engine test_durable_narratives` | `Ran 339 tests in 205.5s … OK` | 3m58s |
| `test_narrative_llm_routing` (substring guards scan `core/**`) | `Ran 21 tests … OK` | 3m31s |
| `generate_inventory.py --check` | clean after re-cut | <1s |
| `git diff --check` | clean | |

Not green-tested tests that pass at head too (they are first-ever coverage, not red-then-green): all of `test_resolve_stored_revision` (14 tests) and the `verified / quiet / drift / dirty / unset / immutable` cases of the command. Stated so nobody reads them as falsified.

Manual, in this worktree, with `DB_HOST=127.0.0.1 DB_PORT=1` so no database could be reached: full HEAD hash → `Release identity verified … clean tree`, exit 0 (a git *worktree*, so the `.git`-pointer-file path is exercised for real); abbreviated hash → `[invalid]`, exit 1; wrong full hash → `[drifted]`, exit 1.

**Budget:** no full suite, no release-scale harness, no evidence directory written, no replay matrix.

## 5. Auditor preflight (applicable questions)

- *Legacy or alternate entry point?* `prepare_manifest` is the only caller of the guard and every resolution goes through it, including recovery's re-run. `build_identity()` is also used by `replay_round`, `audit_anchor` and the fingerprint — all record-only and unchanged in behaviour.
- *Do claimed environment values describe the executing process?* Better than before — the digest is per-process at start and resolution refuses on disk drift. Limits in §7.
- *Does provenance identify runtime bytes, including required untracked files?* The digest always covered untracked source files. `.env` is deliberately **not** hashed (it holds secrets); its non-secret *effects* are recorded instead. Installed packages are digested.
- *Does each negative test prove the engine did not run?* The R31 refusal asserts no coherence row exists afterwards. The guard raises inside `prepare_manifest`, before the input manifest is built.

## 6. OPERATOR procedure to close A-03 on the production host

**Read first:** once this branch is deployed, production resolution **will refuse** until `GIT_REVISION` is correct. Deploying the code and fixing the revision are one maintenance action, not two. Do it outside any open round.

1. **Stop serving from the development checkout.** Create a deployment checkout that nobody edits, at the freeze commit `<FREEZE>` (full 40-char hash):
   ```bash
   git -C /home/ubuntu/projects/globalstrat+ worktree add --detach /srv/globalstrat-plus/release-<short> <FREEZE>
   # or: git clone --no-checkout … && git -C … checkout --detach <FREEZE>
   ```
   A worktree or clone keeps `.git`, so the guard *verifies* HEAD. Alternatively an **immutable build**: `git archive <FREEZE> | tar -x -C /srv/globalstrat-plus/release-<short>` — no `.git`, status `immutable`, and the revision is then trusted rather than verified; the source digest is the only pin. Prefer the checkout.
   Carry over by hand what is untracked and required: `backend/.env` (mode 0600), and either point `COMPETITION_BACKUP_DIR` at the existing backup root or move it — **do not** leave backups under a release directory that will be replaced.
2. Confirm the tree: `git -C <release> status --porcelain --untracked-files=no` prints nothing; `git -C <release> rev-parse HEAD` prints `<FREEZE>`.
3. In `/etc/globalstrat-plus.env` set `GIT_REVISION=<FREEZE>` (full hash; an abbreviation is refused) and keep `COMPETITION_REQUIRE_CLEAN_BUILD` unset or `true`.
4. Point `WorkingDirectory=` of `globalstrat-backend`, `globalstrat-narratives`, `globalstrat-audit-anchor` and `globalstrat-backup-monitor` at `<release>/backend`; `systemctl daemon-reload`.
5. `systemctl restart globalstrat-backend globalstrat-narratives` — **both**. The worker loads the same code and stamps the same revision.
6. Verify, as the service user with the service environment:
   ```bash
   cd <release>/backend && sudo -u ubuntu env $(sudo grep -v '^#' /etc/globalstrat-plus.env | xargs) \
     GLOBALSTRAT_ENV=production python3 manage.py check_release_identity ; echo "exit=$?"
   ```
   Must print `Release identity verified: <FREEZE[:12]>, clean tree.` and `exit=0`. (Adapt the env-loading to local practice; `systemd-run -p EnvironmentFile=…` is cleaner.) Then resolve one round of a **non-competition** game and check `code_revision` and `environment.runtime_config_sha256` on its manifest.
7. **Make drift alert instead of log.** Today the anchor unit runs `ExecStartPost=-/usr/bin/python3 manage.py check_release_identity`; the `-` discards the failure, which is how the drift went unnoticed for days. Keep the `-` there — a drifted revision must not stop sealing — and give the check its **own** unit whose failure is visible:
   ```ini
   # globalstrat-release-identity.service
   [Unit]
   Description=GlobalStrat+ release identity check
   OnFailure=globalstrat-alert@%n.service
   [Service]
   Type=oneshot
   User=ubuntu
   WorkingDirectory=<release>/backend
   Environment=GLOBALSTRAT_ENV=production
   EnvironmentFile=-/etc/globalstrat-plus.env
   ExecStart=/usr/bin/python3 manage.py check_release_identity --quiet
   ```
   plus a 15-minute `.timer`, and an `OnFailure=` target that reaches a person (mail, webhook, or the channel `globalstrat-backup-monitor` already uses). At minimum the unit now shows as **failed** in `systemctl --failed`, which the `-` prefix prevented. Then remove the check line from the anchor unit. I did not edit any unit file, in the repository or on the host.
8. **Freeze rule:** any later code change is a new release directory and a repeat of 2–6. Never `git pull`/`checkout` inside `<release>`.

What the timer can and cannot see: a fresh `manage.py` process has just loaded the disk, so the timer detects *advertised ≠ disk*. It cannot detect *long-running worker older than the disk* — resolution itself refuses that (`changed since this process started`), with a message telling the operator to restart.

## 7. What I could not verify, and what a reviewer should distrust

- **Production state.** Not observed by me (§1). The guard is tested against throwaway repositories and this worktree only, never the production host, its git (ownership / `safe.directory` under `User=ubuntu`), or its service environment.
- **`loaded_source_drift` false positives.** It hashes everything the digest covers under `backend/`. Runtime writers go to `competition_backups/` (excluded by directory *name*). If an operator sets `COMPETITION_BACKUP_DIR` to a differently named directory **inside** `backend/`, or a tool drops a `.json`/`.yaml` there, every later resolution is refused until restart. Fail-closed and explained in the message, but it would hurt mid-competition. A separate release directory (§6) makes it unlikely; it is not impossible. Not load- or soak-tested.
- **Lazy imports.** A start-of-process digest describes the disk at start, not literally the bytes of every module imported later. The drift check at resolution closes most of that window (disk must still equal start), but a file changed and changed back between the two is invisible. "Prove an equivalent" was not attempted beyond this.
- **Untracked source files** are still invisible to the git half (`--untracked-files=no`, kept to match the instruction "clean tracked tree"). The digest records them; nothing *refuses* them.
- **The full-hash rule applies to immutable builds too.** I read "must be a valid commit identifier" as unconditional. A deployment that names builds by tag (`release-2026.09`) will now be refused under the flag. `test_release_provenance` still allows such labels through `resolve_code_revision()` itself, i.e. with the flag off. If the owner wants tags on immutable builds, that is a one-line relaxation in `release_identity`; say so rather than working around it.
- **The allow-list is a judgement.** I judged hostnames, a collection name and a model path non-secret. `QDRANT_HOST` and the gateway host are internal addresses; if those are considered sensitive, remove them. Conversely, anything not on the list is not recorded — `DECISION_WRITE_RATE` is, arbitrary future settings are not.
- **Not tamper-evident** (N-6).
- **No replay was run.** The claim that the production coherence path is byte-identical rests on reading the diff and on tests that resolve rounds and find `blended_score == formula_score`, not on a before/after `output_sha256` comparison. One same-host replay at the freeze commit would settle it and belongs to CRV2-09's integrated run.
- **Only focused modules were run** (339 + 21 tests). A test elsewhere that calls `calculate_coherence(context)` positionally with a falsy second argument, or that sets the clean-build flag with a label, would now fail; grep found none, the full suite was not run to confirm.
- The recovery change adds a refusal to a command used in incidents. The override is unchanged and tested, but nobody has rehearsed it on the host.

## 8. Proposed register text (not applied — the register is not mine to edit)

**A-03 (new cell, or appended to V2-054 / V2-120):**
> *2026-09-21, code half implemented at `dd3b40c` on `crv2-01-release-identity-guard`; **not closed**.* With `COMPETITION_REQUIRE_CLEAN_BUILD` on, resolution refuses unless the advertised revision is a full commit hash, equals HEAD with a clean tracked tree when running from a checkout (an unreadable checkout is refused, not treated as an immutable build), and the tree on disk still matches the digest taken at process start. `check_release_identity` and the guard share `build_identity.release_identity`. Recovery verifies the running revision before the RD-03 comparison. 21 tests red on the unmodified code then green (19 distinct in the first run, 2 of them red only on a missing name; 2 for recovery); first tests for `check_release_identity` and `resolve_stored_revision`. **Open until the operator procedure in `completion/RELEASE_IDENTITY_GUARD_2026-09-21.md` §6 is performed and `check_release_identity` is observed exiting 0 under the service environment**, and until drift alerts rather than logs (the anchor unit's `-` prefix). V2-120's statement that "no new manifest can join this set" was not true when written — the timer detected drift and nothing enforced it — and becomes true only once this is deployed.

**A-04:**
> *2026-09-21, implemented at `dd3b40c`; pending audit.* `requirements.txt` is inside `source_tree_sha256`. `ResolutionManifest.environment` records `runtime_config` / `runtime_config_sha256` (explicit allow-list of non-secret effective settings including per-purpose model routing; no credential recorded or hashed, proven by rotating secrets under test), `requirements_sha256` and `installed_packages_sha256`. Outside every hashed envelope; `MANIFEST_SCHEMA_VERSION` remains 6. **Residual:** the column is outside the audit chain, so the record is not tamper-evident; `.env` itself is deliberately unhashed.

**V2-016 / A-01 (latent path), append:**
> *2026-09-21, `3d3a0a2`.* The retrieval blend (`0.6 × formula + 0.4 × model`) that survived in `calculate_coherence` behind `skip_rag=False` — which was also the default argument — is removed; the function refuses the argument before any write. No stored round was affected. `grading.py::communication_quality` still reads a model score if a rubric selects it and remains an open owner question under R31.

**New, suggested P2:** N-5 (production served from the shared development checkout) and N-6 (`environment` unchained).
