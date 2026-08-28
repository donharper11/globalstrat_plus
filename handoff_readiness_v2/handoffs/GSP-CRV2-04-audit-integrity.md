# GSP-CRV2-04 — Database-enforced audit integrity and read evidence

**Finding:** V2-007 (P1); supports V2-G dispute 3  
**Owner:** backend/database security engineer

## Objective

Make audit history tamper-evident below the Django model layer and make sensitive
decision reads attributable enough to investigate disclosure claims.

## Requirements

- Database privileges/triggers prevent application roles from UPDATE/DELETE on
  decision, operator, resolution and recovery audit records.
- Use a forward hash chain or signed/WORM export anchored outside the mutable
  database. Define key custody/rotation if signatures are used.
- Log authenticated actor, subject team/game/round, endpoint, request ID,
  outcome and server time for reads of raw team decisions and audit payloads.
- Do not log secrets/JWTs or duplicate sensitive payloads in access logs.
- Define retention, access control, export and integrity-verification commands.
- Migration/rollback must preserve existing audit rows and production startup.

## Acceptance

Prove model save, queryset update/delete, raw SQL as application role, admin UI
and API tampering are rejected or detected. Prove a privileged maintenance
change breaks the external integrity check. Exercise allowed/denied cross-team
reads and answer “who accessed Team X Round Y?” using operator tooling alone.

Evidence: migration SQL, privilege dumps, negative transcripts, chain/signature
verification and browser/API screenshots under `evidence/audit-integrity/`.
