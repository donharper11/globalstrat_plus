# Final consolidated A1-A8 verification

Verification date: 2026-08-27 UTC  
Candidate: `competition-rc-2026.08.27.1`  
Application commit: `86c2ad40fb300a666e154915aa392cb2e56f2ad6`  
Overall verdict: **FAIL — the completed A1 rehearsal found CR-017.**

The application source under `backend/` and `frontend/` matches the annotated
tag exactly. A fresh frontend production build emitted `main.8d2222cf.js` with
SHA-256 `34b64d2dcf724d55f40b2bf04a3e605c14b36b809aa28399be6b396abe6d4bbd`,
byte-identical to the public bundle. The deployed backend is running with the
tagged revision in its production environment.

| Area | Verdict | Consolidated evidence |
|---|---|---|
| A1 click-through | **Fail** | The isolated tagged rehearsal completed all six rounds and the required browser-state scenarios. Everything passed except back navigation during an unsaved Marketing edit: no warning appeared and the edit was silently lost (CR-017; `A1_BROWSER_STATE_LIFECYCLE_REHEARSAL.md`). |
| A2 lifecycle | **Pass** | 107 tagged focused A2/A3 tests; expected and 3x deadline evidence accounts for every write, late rejection and team lock; concurrent resolution has one winner. |
| A3 reconstruction | **Pass** | Zero hash mismatches across 1,035 live decision audit events and nine completed manifests; isolated replay input/output hashes are byte-identical; tagged provenance writer probe passed. Historical pre-tag manifests correctly remain unmodified and have empty revision fields. |
| A4 balance/exploits | **Pass** | Nine tagged tests; FX matrix has no dominant hedge ratio, legal R&D ordering is invariant, duplicate targets are rejected, and the six-round cohort rejects an unassailable early lead. |
| A5 concurrency/load | **Pass** | 73 tagged focused tests plus preserved production-shaped evidence: 96-request and 288-request cohorts have zero lost accepted writes, uniform in-flight late rejection, full locking, one resolution winner and deterministic replay. The socket load fixture was not destructively rerun. |
| A6 instructor controls | **Pass** | 50 focused control/security tests cover deadline lifecycle, correction guards, recovery validation/audit, reversible reasoned team removal and instructor authorization. The non-dry-run recovery exercise remains its separately tracked launch gate. |
| A7 isolation/integrity | **Pass** | Cross-team reads/writes, unenrolled users, spoofed identities and student operator actions are rejected; server-side state gates, throttling, immutable audits and fail-closed engine behavior pass. |
| A8 bilingual parity | **Pass** | EN/ZH each contain 1,982 scalar keys with zero mismatch; 48 deployed captures pass; focused Chinese supply-chain rendering has no tracked English leakage. Human semantic/viewport review remains appropriate in the volunteer rehearsal. |

## Fresh convergence results

- Backend: **271 tests passed in 85.190 seconds**; Django system check clean.
- Frontend: production build succeeded with existing lint and bundle-size
  warnings; emitted artifact matches the public JavaScript byte-for-byte.
- A6/A7 focused suite: **50 tests passed in 24.489 seconds**.
- Tagged isolated workstreams: A2/A3 **107 passed**, A4 **9 passed**, A5
  **73 passed**.

The consolidated launch gate remains unchecked until CR-017 is repaired and the
targeted back-navigation scenario plus affected A1 verification are rerun.
