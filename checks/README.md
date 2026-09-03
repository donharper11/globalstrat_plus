# aide-checks

One canonical source of automated checks for the Camdani platform repos. Cloned
on each VM, vendored into each platform repo under `checks/`.

Built from `aide-forge/mine/full/` — 656 corrections, 179 rules, 7 repos. Every
check here exists because the corpus recorded the same defect in more than one
repo, and because the rule that should have caught it was prose.

## Phase 1 — what is here

| check | form | evidence |
|---|---|---|
| `no-committed-secrets` | gitleaks over the tracked working tree at HEAD | NEXUS-C116, NEXUS-C118, BECSR-C139, AP-C028, AC-C051, AP-C043 — four repos independently |
| `no-agent-worktrees-tracked` | fails when a harness worktree path is tracked by git | NEXUS-C119, BECSR-C136 |

Eight further checks are specified in the build spec §7 and are **not** built
here. Phase 1 exists to prove the package, the sync and the deploy gate on two
checks that cannot be argued with.

## Phase 2 — what was added

| check | form | evidence |
|---|---|---|
| revision assertion | `bin/run-checks` refuses to run when the runner and the repo's vendored revision disagree | the `.5`/`.220` drift of 2026-09-02, and `verification-false-pass` — 86 corrections, all seven repos |
| `rls-policy-present` | every table in the application schema has an RLS policy; every configured global vocabulary table has an explicit authenticated/global policy and no tenant column | `R-V8-07`, nexus `handoffs_v8/GOVERNANCE.md` — 11 corrections governed, 11 matched failures, 0 catches |

Six further rule-derived checks are specified in the phase 2 spec §7 and are
**not** built here. One check first, because phase 2 differs from phase 1 in a
way that matters: these can produce false positives, so the pattern is proved on
the strongest single case before six more are written.

### The revision assertion

Version drift must not be able to produce a silent pass. On 2026-09-02 `.5` ran
`aide-checks@6e0f6b2` while `.220` ran `d60d74b`; the older runner ignored valid
suppressions and **failed** a repo that should have passed. That was visible.
The same drift in reverse is not: an older runner missing a check entirely
reports PASS, and nothing distinguishes that from a genuine pass.

Before any check runs, `bin/run-checks` compares the revision it was built from
against `checks/.aide-checks-rev` in the repo. A mismatch is **exit 2** —
could-not-run, not a failure and never a pass — in `--fast`, `--full` **and**
`--report-only`. **There is no bypass flag**, and no environment variable turns
it off: a stale runner cannot report meaningfully on anything.

The revision is stamped in two places, and both are load-bearing.
`sync-into-repo` writes `checks/.aide-checks-rev` beside the code *and* rewrites
`AIDE_CHECKS_BUILT_FROM` inside the copied `bin/run-checks`. The sidecar alone
cannot catch the drift the assertion exists for — replace `checks/bin` from an
older clone and the sidecar still reads current. Run from the package's own git
checkout, `HEAD` is the authority instead.

`run-checks --print-revision` prints what a runner thinks it is. It suppresses
nothing.

The one case where the assertion does not apply is the package running on its
own repo, where the runner and the repo are the same tree and there is no
vendored copy to drift from. That is printed, not skipped silently.

### `rls-policy-present`

Makes `R-V8-07` executable. The prose rule is **not** modified and is not
replaced: `handoffs_v8/GOVERNANCE.md` stays exactly as written.

Two assertions, one per clause:

1. every table in the configured application schema has at least one RLS policy;
2. every configured global vocabulary table carries an explicit
   authenticated/global policy **and** no tenant-scoped column.

Which tables count as global vocabulary **is not derivable from the schema**. It
is a judgment the rule assumes and does not define, and it is not inferable from
naming conventions: 53 of nexus's 197 public tables carry no tenant column, and
most of those are child tables scoped through a parent. The set lives in
`checks.config.json` with a stated reason per table — the same shape as
`allow_fields_reasons` — plus a `global_vocabulary_source` recording how it was
determined. An entry without a reason is exit 2, never a silent inclusion. The
application schemas, the tenant column names and the context-function pattern
are config for the same reason.

The connection is read from the environment named in `connection_env`, with **no
fallback literal**: a connection string baked into a check is a credential in a
repo. No connection, or an unreachable database, is exit 2 — never a pass.

Its selftest starts a postgres of its own and drops it again. It **must not
touch a live database**: accounting's production database was destroyed on
2026-08-24 by a committed test running `DROP SCHEMA public CASCADE`.

## Usage

```
bin/run-checks --fast          # pre-commit subset
bin/run-checks --full          # deploy and CI
bin/run-checks --report-only   # run everything, print findings, exit 0
```

Optional: `--repo=<path>` and `--config=<path>`. By default the repo root is the
parent of `checks/` and the config is `<repo>/checks.config.json`.

Exit codes: `0` pass · `1` a blocking check failed · `2` a check could not run.
**Exit 2 is a failure.** A scanner that is absent has not passed, and neither
has a stale runner.

`--print-revision` prints the revision the runner was built from and stops.

## The standard this package holds itself to

`AP-R10`, aide-platform's own rule, in force 2026-08-18, form `check`:

> a check counts only when the packet proves it can fail.

Every check ships with a selftest that builds a disposable repo, asserts the
check passes clean, **plants a violation, asserts a non-zero exit**, and removes
the plant. `selftest/run` must be green before `bin/sync-into-repo` will vendor
the package anywhere.

The selftests also assert the false-positive cases, because a check that cries
wolf gets the layer disabled: an untracked `.env`, and a worktree that exists on
disk but is not tracked, must both pass.

## Per-repo configuration

`checks.config.json` at each platform repo's root. The package is never forked
per repo; every difference lives in that file. `config/schema.json` is its shape.

Exclusions are per-repo and evidenced: each one carries a reason in
`exclusion_reasons`. Excluding a path because it is noisy is not a reason.

## Enforcement layers

| layer | bypassable | mode |
|---|---|---|
| `.husky/pre-commit` | yes, `--no-verify` | `--fast` |
| deploy script gate | no | `--full` |
| GitHub Actions | advisory on the current plan | `--full` |
| `accounting` build gate | yes, `AIDE_CHECKS_SKIP=1` | `--full` |

The deploy gate is the enforcement layer. The builder does not invoke the deploy
script.

## Phase 1 install — where it stands

| repo | VM | secrets | mode | worktrees | deploy gate |
|---|---|---:|---|---:|---|
| nexus | .220 | 10 | report-only | 0 | `scripts/deploy-public.sh` |
| accounting | .220 | 0 | blocking | 0 | `scripts/build-images.sh` (phase 2 §3, resolution (a)) |
| worklab | .220 | 31 | report-only | 0 | `deploy.sh` |
| prism-nexus | .220 | 1 | report-only | 0 | `frontend/deploy-frontend.sh` |
| aide-platform | .220 | 7114 | report-only | 0 | `frontend/deploy-frontend.sh` |
| BECSR | .5 | 0 | blocking | 0 | `deploy-becsr.sh` |
| globalstrat+ | .5 | 4 | report-only | 0 | `frontend/deploy-frontend.sh` |

Both zeros were probed before being accepted (build spec §9.8): a planted
private-key block was detected in each, and the zero returned when it was
removed.

`report-only` is the build spec §5 instruction for a repo whose first scan would
fail its first deploy — the count stays visible and the gate stays installed
rather than being removed. No path is excluded anywhere; the counts are reported
as they stand.

## Known limitations

- **`generic-api-key` is the noisy rule.** 7,155 of the 7,160 secret findings
  across all seven repos are that one rule firing on JSON identifier fields whose
  names end in `_key` — `component_key`, `artifact_key`, `outcome_key`,
  `idempotency_key`. It was left untuned: narrowing it risks blinding the check to
  the class it exists for (NEXUS-C116 was a demo password in a doc), and that
  trade is the owner's to make, not the installer's.
- **`.5` pulls from GitHub directly over SSH.** An earlier note here claimed the
  host had no credential. That was wrong: this package's clone on `.5` had an
  HTTPS origin and no credential helper, while every other repo there already
  used SSH and authenticated fine. Corrected 2026-09-03 — the origin is now
  `git@github.com:donharper11/aide-checks.git`. `bin/push-to-vm5` is retained
  only as an offline fallback for when GitHub is unreachable from `.5`.
- **gitleaks is a host dependency**, installed to `~/bin` on both VMs. The check
  exits 2 rather than 0 when it is absent, so a missing scanner refuses a deploy
  instead of passing one.
- **CI is advisory.** GitHub Free does not enforce rulesets on private repos.
- **`accounting` is gated at build, not at the entrypoint.** `docker compose
  build` run by hand does not pass through `scripts/build-images.sh` and is not
  gated, in the same way `--no-verify` bypasses the pre-commit hook. Gating
  `backend/docker-entrypoint.sh` instead would need gitleaks inside the runtime
  image (phase 2 spec §3, resolution (b)); without it the check exits 2 and the
  container refuses to start, which is an outage rather than a gate. That was
  tried once and correctly reverted.
- **`rls-policy-present` needs a reachable database, and exit 2 blocks.**
  `run-checks` treats exit 2 as blocking regardless of a check's configured
  mode, so a database that cannot be reached refuses a deploy even while the
  check is in its report-only window. That is spec §4.1's "never pass" applied
  literally; it is worth knowing before the check is enabled anywhere that
  deploys from a host without database reachability.
