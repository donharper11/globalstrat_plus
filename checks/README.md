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

## Usage

```
bin/run-checks --fast          # pre-commit subset
bin/run-checks --full          # deploy and CI
bin/run-checks --report-only   # run everything, print findings, exit 0
```

Optional: `--repo=<path>` and `--config=<path>`. By default the repo root is the
parent of `checks/` and the config is `<repo>/checks.config.json`.

Exit codes: `0` pass · `1` a blocking check failed · `2` a check could not run.
**Exit 2 is a failure.** A scanner that is absent has not passed.

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

The deploy gate is the enforcement layer. The builder does not invoke the deploy
script.
