# Phase 2 fix log

Implementation date: 2026-08-27 UTC. Migration `0059_competition_audit` was applied successfully and the local Gunicorn workers were reloaded.

| Register ID | Status | Repair and verification |
|---|---|---|
| CR-001 | Closed | Added real `Round.decisions_locked`/`lock_reason` fields and made `IsRoundOpen` reject the flag. Regression test covers an open-but-instructor-locked round. |
| CR-002 | Closed | `close_round` and `_run_phase_1` are atomic and acquire row locks on Game/Round. A second resolver waits, then observes `processed` and cannot run the pipeline again. |
| CR-003 | Closed | Added append-only `DecisionAuditEvent` records containing canonical payload, SHA-256, actor, timestamp, endpoint and request ID for generic, supply-chain, communication, org and tax writes and lock/default events. |
| CR-004 | Closed | `locked_by` now references the authenticated custom user and is populated at lock. Audit failure is fail-closed on prize-critical writes. |
| CR-005 | Closed | Resolution now runs `pg_dump --format=custom` before engine mutation, verifies a non-empty dump, writes SHA-256, and stores its path in the manifest. Test databases use transactional isolation instead. |
| CR-006 | Closed | Added scoped DRF rate limiting (`decision_write`, default 120/min, environment configurable) and fixed JWT identity compatibility with DRF throttles. Live probe observed 429 enforcement. |
| CR-007 | Closed | Generic partial decision replacement is now `transaction.atomic`; SC replacements were already atomic. |
| CR-008 | Closed | Added `ResolutionManifest`: stored seed, canonical input event manifest/hash, code revision slot, backup path, canonical result output/hash and completion timestamp. |
| CR-009 | Closed | Added append-only `OperatorAuditEvent` for close, reopen, process, advance, deadline, legacy lock/unlock/extend and submission-correction unlock. Records actor, reason, before/after and request ID. |
| CR-010 | Closed | Added the guarded `recover_competition_round` operator workflow. It requires maintenance-mode enablement, instructor/admin identity, a substantive reason, exact game/round confirmation, manifest/path/checksum validation, and durable pre-restore plus database post-restore audit records. Dry-run and restore-only modes are available; the default restores and re-runs. |
| CR-011 | Closed | FX hedges now charge a configurable premium (default 25 bps of protected notional), booked in hedge P&L in the opening round. Full hedging is no longer free. |
| CR-012 | Closed | Missing submissions are still defaulted uniformly, but now receive the explicit immutable action `missing_submission_defaulted`; recommended rules publish the fallback. |
| CR-013 | Closed | Every deterministic Phase 1 stage now fails closed. Supply chain, compliance, FX, organisational structure, alliances, tax structure, strategic impacts, derived features, capital markets, agent orchestration, alerts and resilience scoring all propagate errors through the outer atomic transaction, preventing partial publication. |
| CR-014 | Closed | Extracted the remaining student-facing supply-chain and shared navigation/status copy into matched EN/ZH keys: Sourcing, Logistics, Trade Finance, Inventory, the supply-chain dashboard, round status, and shallow-route recovery. Protocol names and brands (for example Incoterms, GS, GlobalStrat) remain intentionally invariant. |
| CR-015 | Accepted operational constraint | The supported competition URL is the public GlobalStrat endpoint; port 8081 belongs to code-server and is excluded from the runbook. |
| CR-016 | Closed | Root cause was the full-screen authentication gate: direct navigation waited for `/auth/me/` behind an unlabeled standalone Ant Design spinner. The app now hydrates the last server-verified session immediately while revalidating it in the background, and all standalone loading states render explicit, accessible EN/ZH text. The post-deploy sweep captured 48/48 nonblank screens with no console or API errors. |
| CR-017 | Closed | Added `useUnsavedChangesGuard`, wired into all five student decision pages that track a dirty draft (Marketing, Sourcing, Logistics, Trade Finance, Inventory). While a page has unsaved edits it warns before the route is left: a `beforeunload` prompt on tab close / full navigation, an intercepted `confirm` on same-origin link clicks, and a history-sentinel `confirm` on browser Back (BrowserRouter exposes no data-router blocker, so the guard keeps a same-URL sentinel entry while dirty). The prompt text is a new EN/ZH locale key `common.unsaved_changes_prompt`. Re-verification: the original failing scenario now fires the discard dialog `"You have unsaved changes. Leave this page and discard them?"` instead of silently reverting. Evidence: `evidence/a1-lifecycle-20260827/back-mid-decision-targeted.json` (`leave_dialog` populated, `warning_visible: true`, `pass: true`), `cr017-regression-sweep.json`, and `frontend/globalstrat-frontend/src/hooks/useUnsavedChangesGuard.test.js` (3/3). |

## Additional server-side hardening

- All student decision write families now enter the shared game deadline lock
  before DRF permission evaluation and serialize same-team mutations. Generic,
  partial, lock, sourcing, logistics, trade-finance, inventory, communication,
  organisational and tax writes therefore re-read a close that committed while
  they waited and reject uniformly.
- Leaderboard ties now implement the published order: cumulative operating cash
  flow, cumulative revenue, then current/final-round resilience. Resilience is
  scored before leaderboard creation in the same atomic engine transaction.
- R&D submissions now enforce one investment per platform feature per round.
  Forward/reverse legal cohorts resolve identically; reversed duplicate-target
  payloads are uniformly rejected before replacement.
- Communication, organisational-structure and tax-structure writes now enforce team membership, current-round state/deadline/instructor lock, throttling and audit logging.
- Communication history/assignment reads enforce team membership; instructor communication monitoring is instructor-only.
- Tax endpoints now require the requested team to belong to the requested game.

## Verification

- CR-014 locale verification: EN/ZH each contain **1,982 leaf keys** with zero key mismatches; the targeted hard-coded scan is clean apart from intentional brand/protocol terms.
- Post-deploy locale audit: all four Chinese supply-chain routes rendered completed content (238–736 characters), with zero page errors and none of the tracked English operational phrases. The complete browser sweep captured **48/48** screens with zero failures.
- CR-014 frontend deployed as `main.8d2222cf.js` with rollback backup `/var/www/globalstrat-backup-20260827-132836`.
- Recovery/fail-closed completion suite: **252 tests passed** in 79.643 seconds; Django system check clean.
- Guarded recovery dry-run test verified the manifest path, SHA-256 sidecar, confirmation/identity/reason gates, and durable JSONL intent audit without mutating the database.
- Backend Gunicorn workers reloaded at 2026-08-27 12:46 UTC; the public API returned the expected authenticated-endpoint 403 response rather than a server error.
- Full backend suite: **249 tests passed** in 85.244 seconds after the core changes.
- Final targeted hardening/lifecycle rerun after the last permission changes: **6 tests passed**; Django system check clean.
- Frontend production build: **success**, warnings only (pre-existing lint/bundle warnings).
- Migration: `core.0059_competition_audit` applied successfully.
- Runtime authentication after worker reload: student login succeeds.
- Frontend deployed successfully for CR-016 with backup `/var/www/globalstrat-backup-20260827-123540`; public HTML references `main.47ffc992.js`. Cloudflare purge was unavailable, so normal cache expiry/client refresh may be required.
- Post-deploy browser sweep: 48 captures completed; all 48 had visible body content with no console or API errors. The only short sample was the valid instructor shell and labeled loading state (73 characters), not a blank document.
- Focused CR-016 timing probe: the first post-navigation sample rendered the student application shell (489 characters) while APIs loaded, versus zero body text before the fix; the completed R&D screen rendered 2,287 characters.
- Post-status hardening suites: 78 deadline/write-path regressions passed, then
  81 leaderboard/compliance/engine/supply-chain regressions passed; Django
  system check remained clean.
- Parallel launch hardening added reversible, audited team participation
  control and fail-closed production release provenance plus guarded backup
  retention inspection/pruning. Primary-agent audit tightened lock ordering,
  active-team manifests, instructor visibility, explicit production revision,
  and zero-day retention validation. The clean convergence run passed **271
  tests in 89.173 seconds**; migration `core.0060_team_participation_status`
  applied successfully and Gunicorn was reloaded.
- Deployed release provenance verified at 2026-08-27T15:03:54Z: the restarted
  backend inherited `GIT_REVISION=86c2ad40fb300a666e154915aa392cb2e56f2ad6`,
  and the real manifest writer recorded that exact revision in a rollback-only
  production-settings transaction
  (`evidence/release-provenance-verification.json`).
- Backup evidence policy approved and applied: 90-day dump retention with
  dispute holds, 12-month manifest/audit retention, pruning disabled by default,
  backup storage tightened from `0775`/`0664` to `0700`/`0600`, and backend
  `UMask=0077`. The enabled daily systemd monitor verified all 12 backups,
  reported zero invalid/expired artifacts and confirmed 44% filesystem use
  (`BACKUP_RETENTION_POLICY.md`,
  `evidence/backup-retention-verification.json`).
- Final tagged-candidate consolidation reran 271 backend tests successfully,
  rebuilt a byte-identical public frontend artifact, and passed A2-A8. A1's
  deployed 48-screen sweep passes, but the strict six-round UI lifecycle and
  browser-state scenarios are not yet evidenced, so the consolidated gate
  remains open (`CONSOLIDATED_A1_A8_VERIFICATION.md`).
- The missing A1 rehearsal was executed in an isolated tagged stack. All six
  rounds, refresh, duplicate-tab, session-expiry, close/return and later-round
  URL scenarios passed. Back navigation exposed open CR-017: an unsaved
  Marketing edit is discarded without warning.

## CR-017 repair and re-verification (post-tag)

- Fix committed as `aa353c16e5fc1a139e9395e4c50e849e26e49fa1` on `main` (frontend-only: `useUnsavedChangesGuard`
  hook + wiring in the five dirty-tracking decision pages + one EN/ZH locale key).
  The backend is unchanged from tag `competition-rc-2026.08.27.1`.
- Frontend rebuilt from that commit: bundle `main.d8229d93.js`,
  sha256 `b83c99f639f1c99aec417bc370910f27b2d2153053e4c8cf49312ac16d0b98a1`.
- Unit test `useUnsavedChangesGuard.test.js`: **3/3 passed** (blocks a cancelled
  same-origin link, stays inert when clean, marks `beforeunload` prevented while dirty).
- EN/ZH locale parity re-checked: **1,983 leaf keys each, zero mismatch**
  (the new `common.unsaved_changes_prompt` key added to both).
- Targeted A1 re-verification against the fixed build served to the isolated
  backend: the original failing scenario (Marketing field `0`->`1`, browser Back)
  now raises `"You have unsaved changes. Leave this page and discard them?"`
  (`leave_dialog` populated, `warning_visible: true`, `pass: true`;
  `evidence/a1-lifecycle-20260827/back-mid-decision-targeted.json`).
- Five-page guard sweep: Marketing, Sourcing, Logistics, Trade Finance and
  Inventory each render nonblank with zero page errors and the guard stays inert
  on a clean back-navigation — no false prompts
  (`evidence/a1-lifecycle-20260827/cr017-regression-sweep.json`, `all_pass: true`).
- Deployed to the public endpoint via `frontend/deploy-frontend.sh --skip-build`:
  rsynced to `root@47.86.57.36:/var/www/globalstrat/build`, 37 files, verified
  `main.d8229d93.js` live at https://globalstrat.camdani.com. Rollback artifact:
  `/var/www/globalstrat-backup-20260827-171919`. Cloudflare purge skipped
  (no `CF_TOKEN`); the content-hashed bundle name makes the new asset cache-safe.

## Recovery drill: recover_competition_round hardening (RD-01/02/03)

The end-to-end recovery drill (previously only dry-run tested) exposed three
defects in the real restore + re-run path; all are fixed and re-verified green
(`RECOVERY_DRILL.md`, `evidence/recovery-drill-20260827/`).

| ID | Status | Repair |
|---|---|---|
| RD-01 | Closed | `restore_database` no longer passes `pg_restore --exit-on-error`, which turned a benign cross-version `SET transaction_timeout` (pg_dump 18 vs server 16) into a fatal restore failure. It now tolerates only benign version-skew SET errors (`_restore_stderr_is_benign`); any other pg_restore error is fatal. |
| RD-02 | Closed | `restore_database` restores onto a freshly recreated schema (`DROP SCHEMA public CASCADE; CREATE SCHEMA public;`) instead of `pg_restore --clean`, so FK-referenced objects (e.g. `users_pkey` ← `team`) no longer block the restore. |
| RD-03 | Closed | `recover_competition_round` compares `manifest.code_revision` to the running `resolve_code_revision()` and refuses on mismatch/empty unless `--allow-code-revision-mismatch`; both revisions are written to the durable intent audit. Prevents re-running resolution against a build whose schema differs from the backup. |

Verification: full backend suite **273 passed** (added a benign-error-classifier
test and a code-revision-mismatch test). Green end-to-end re-run on game 31
round 7 reproduced the pre-corruption `output_sha256`
`c172eb4d…159224d3` exactly, with `restore_round`/`rerun_round` operator audit
events and `restore/rerun` durable audit records. Two-operator sign-off for a
live recovery remains an outstanding human gate.

## V-1 fix: instructor can distinguish missing from deliberately-empty submissions

Found during the #2 instructor-visibility verification: after close, a
never-submitted team (audit action `missing_submission_defaulted`) and a
deliberately-empty locked submission (`deadline_lock`) both showed
`status=locked`, and no instructor endpoint surfaced the difference — it lived
only in `DecisionAuditEvent`, so answering "did this team actually submit?"
required direct database access. This is the operator-visibility half of CR-012.

- Fix (commit `93a09cc`): `classify_submission_origin()` derives an origin from
  the immutable close-round audit events — `no_submission` / `draft` /
  `student_locked` / `deadline_locked` / `defaulted_missing` (robust to a
  reopen+reclose cycle). It is surfaced as `submission_origin` (plus a human
  label) on the instructor team-decisions endpoint and per team on the
  instructor dashboard. The instructor UI shows an origin tag — a red
  "Never submitted" for a defaulted team.
- Verification: regression test over all five origin states; full backend suite
  **274 passed**; end-to-end on an isolated stack a genuinely-missing team
  reported `defaulted_missing` and a deliberately-empty one `deadline_locked`,
  distinguishable from the dashboard and detail endpoints with no database access
  (`evidence/instructor-visibility-20260827/visibility.json`).
- Deployed: frontend `main.3a59e7dc.js` to the public endpoint (rollback backup
  `/var/www/globalstrat-backup-20260827-183620`); backend gracefully reloaded so
  the API serves `submission_origin`. EN/ZH parity preserved (1,986 keys each).
