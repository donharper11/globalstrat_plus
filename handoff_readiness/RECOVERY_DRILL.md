# End-to-end recover_competition_round drill

Date: 2026-08-27 UTC
Verdict: **PASS after repair.** The first end-to-end run failed on three real
defects (never caught before, because only the `--dry-run` path had been
tested). All three are fixed; the drill now restores and re-runs a round to a
byte-identical result.

## Isolation

The drill ran against a disposable `postgres:16` container on loopback
(`127.0.0.1:15433`) seeded read-only from production (`192.168.50.38`) with a
single `pg_dump`. Every destructive operation (`pg_restore`, `DROP SCHEMA`,
result tampering, round re-run) was confined to the container. A canary asserted
`connection.settings_dict` pointed at `127.0.0.1:15433` before each destructive
step. No production database, service, or competition record was mutated. The
container was removed on completion.

## What the drill found (all fixed)

| ID | Sev | Defect | Fix |
|----|-----|--------|-----|
| RD-01 | P1 | `restore_database` ran `pg_restore --exit-on-error`. Host pg tools are 18.x, the server is 16.13, so every dump carries `SET transaction_timeout` (a 17+ GUC) that the 16 server rejects; `--exit-on-error` made that benign SET fatal and the restore never completed. | Drop `--exit-on-error`; tolerate only benign cross-version SET failures via `_restore_stderr_is_benign` (any other error is still fatal). |
| RD-02 | P1 | `pg_restore --clean` could not drop FK-referenced objects (`users_pkey` ← `team`), leaving a partly-dropped schema. | Restore onto a freshly recreated schema: `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` before `pg_restore` (no `--clean`), so no FK-referenced object survives to block object creation. |
| RD-03 | P1 | The re-run used current code against a pre-migration snapshot and failed (`column team.participation_status does not exist`). The manifests' `code_revision` was empty, so the skew was undetectable. | `recover_competition_round` now compares `manifest.code_revision` to the running `resolve_code_revision()` and refuses on mismatch/empty unless `--allow-code-revision-mismatch`; both revisions are recorded in the durable intent audit. |

## Green re-run (after fix)

A fresh same-revision pre-resolution backup was generated in-drill for
**game 31 ("CC-12 Integration Test"), round 7** (`code_revision=drillrev1`),
its scored result was tampered, then `recover_competition_round` restored and
re-ran the round.

- **Deterministic reproduction:** re-run `output_sha256`
  `c172eb4d2d4494c4aff11be6779b5f4cc2779de0100770acb0a10e7a159224d3` equals the
  pre-corruption baseline exactly.
- **Operator audit (immutable):** `restore_round` and `rerun_round` events, each
  with actor, reason and request id.
- **Durable audit (survives the restore):** `restore_round_intent`,
  `restore_round_complete`, `rerun_round_complete` in `recovery-audit.jsonl`.
- **Guards confirmed:** maintenance-mode gate, confirm-token
  (`RESTORE-GAME-<id>-ROUND-<n>`), ≥10-char reason, instructor/admin actor,
  backup SHA-256 verification, and the new code-revision guard.
- **Regression tests:** `core/tests/test_competition_hardening.py` — benign-error
  classifier and code-revision-mismatch guard added; full backend suite **273 passed**.

Evidence: `evidence/recovery-drill-20260827/` (`summary.json`, the two restore
stderr captures, and both `recovery-audit*.jsonl`).

## Still outstanding — human gate

**Two-operator sign-off.** The command records a single actor; a second operator
must counter-sign a live recovery per `OPERATOR_RUNBOOK.md`. This is a process
step, not a code change, and remains before live-competition approval.
