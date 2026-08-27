# Competition restore and re-run runbook

Use this workflow only for a confirmed scoring or resolution defect. It restores
the **entire database** to the snapshot taken immediately before the selected
round was resolved, so the application must be in maintenance mode first.

## Guardrails

- Stop all web workers, schedulers, and other database writers before execution.
- Identify the instructor/admin account that authorized recovery.
- Record a specific reason (minimum 10 characters).
- First run with `--dry-run`; it validates the manifest, path and SHA-256 without
  changing the database.
- The exact confirmation token is `RESTORE-GAME-<id>-ROUND-<number>`.
- Set `COMPETITION_RECOVERY_ENABLED=true` only for the maintenance window.
- Run operator commands with `umask 077`; handle and retain artifacts according
  to `BACKUP_RETENTION_POLICY.md` and do not export dumps to unmanaged systems.
- Recovery writes `recovery-audit.jsonl` beside the dumps before restoration,
  then append-only `OperatorAuditEvent` rows after restoration and re-run.

## Commands

```bash
cd /home/ubuntu/projects/globalstrat+/backend
umask 077
COMPETITION_RECOVERY_ENABLED=true python3 manage.py recover_competition_round \
  --game-id GAME_ID --round ROUND_NUMBER --actor INSTRUCTOR_USERNAME \
  --reason "SPECIFIC VERIFIED REASON" \
  --confirm RESTORE-GAME-GAME_ID-ROUND-ROUND_NUMBER --dry-run
```

After the dry run succeeds, stop application/database writers and repeat without
`--dry-run`. By default the command restores the snapshot and reprocesses the
round. Add `--restore-only` to restore without processing.

Restart workers only after the command reports `Competition recovery completed`,
then verify the round manifest output hash, results screens, and operator audit.

## Failure handling

`pg_restore` uses `--exit-on-error`; a failed restore never proceeds to re-run.
Keep maintenance mode active, preserve the durable JSONL audit, diagnose the
reported PostgreSQL error, and retry only from a newly verified recovery plan.
