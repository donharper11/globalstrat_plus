# GSP-CRV2-07 — Field load and recovery playthrough

**Gates:** V2-C, V2-D, V2-F  
**Owner:** reliability/performance engineer

## Objective

Show that the intended field deployment works at its named load, retains a
reasonable safety margin, and has usable recovery procedures. This is a bounded
release exercise, not an open-ended search for a theoretical maximum and not a
repeat of the CRV2-01/02/03 certification suites.

## Fixed profiles

- **Field:** 24 teams × 4 members = 96 authenticated sessions.
- **Margin:** 3× field = 288 sessions.
- Sessions use separate identities and realistic refresh, save, lock, and
  instructor-resolution traffic. Final-minute writes are included.

The builder runs a short smoke profile while developing. From the frozen
candidate, run field once and 3× once. Do not step upward indefinitely. If 3×
passes the predefined service thresholds, report the supported ceiling as
“at least 3× field”; capacity beyond that is not a launch requirement. If 3×
fails, run one diagnostic midpoint only when needed to identify a safe operating
limit. Fix code, freeze again, and repeat only the failed profile plus the final
field confirmation.

Before running, define acceptable p95 latency, error rate, database saturation,
and unexplained-write thresholds. Report throughput, p50/p95/max, status/error
distribution, DB pool/locks, CPU, memory, disk, and attempted/acknowledged/final
writes. Percentiles such as p99 are optional when the sample size makes them
meaningful; decorative metrics are not acceptance gates.

## One recovery walkthrough

Use one disposable integrated stack and one seeded multi-round game. Walk an
operator through normal resolution and recovery. Inject each distinct boundary
once:

1. database loss during resolution;
2. backend restart after a committed Phase 1;
3. disk-full/backup failure;
4. deadline partition or session expiry during submission;
5. one concurrent-operator conflict.

Reuse the already certified CRV2-02 locking and CRV2-03 narrative evidence.
Do not rerun their race matrix, provider matrix, or repeated SIGKILL drills.
LLM outage is covered by CRV2-03 unless this handoff changes that path. Clock
skew may be a focused automated check unless the deployed clock configuration
differs from the certified environment.

For every injected boundary record the user-visible symptom, committed state,
operator action, recovery result, and whether any acknowledged write was lost or
duplicated. A failure that cannot occur in the intended deployment need not be
manufactured; document the enforced control that makes it unreachable.

## Deploy/restore walkthrough

From the same frozen candidate, perform one fresh backup and restore/replay.
Confirm an incompatible old-revision dump is rejected and the deploy-freeze
procedure is executable as written. Use a simulated or test-only break-glass
check unless the implementation of that control changed.

## Acceptance and evidence budget

Store the harness, thresholds, environment capacity, raw field/3× results,
write reconciliation, and recovery transcript in `evidence/load-failure/`.

- One field run and one 3× run per successful freeze candidate.
- At most one extra capacity diagnostic after a 3× failure.
- One recovery walkthrough; one injection per distinct boundary.
- No earlier determinism, race, or narrative matrices.
- No separate full regression suite here if the same frozen candidate proceeds
  directly to CRV2-09; CRV2-09 owns the single integrated suite. Run only
  affected focused tests after any repair.

PASS means the actual product workflow functions at field load, 3× behavior is
known, acknowledged writes reconcile, and an operator can execute recovery.
