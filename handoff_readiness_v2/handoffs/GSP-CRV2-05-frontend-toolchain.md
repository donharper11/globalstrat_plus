# GSP-CRV2-05 — Supported frontend toolchain and green verification

**Finding:** V2-009 (P1)  
**Owner:** frontend/build engineer

## Objective

Make clean install, Jest and production build reproducible on one explicitly
supported Node/npm version without incidental lockfile churn.

## Work

Choose and document either Node >=20 for router v7 or a deliberate compatible
router version. Check application API compatibility before changing either.
Pin Node (`.nvmrc`, Volta or equivalent) and package-manager version; retain one
authoritative lock strategy. Recreate dependencies from a clean directory.

Add focused tests for the instructor audit-evidence table: historical round
selection, actor/time/request ID/hash/payload rendering, empty history, pagination
and failed API response. Address only security-relevant dependency findings in
this handoff; do not run an unreviewed force audit upgrade.

## Acceptance

- Clean `npm ci` (or documented equivalent) succeeds on the pinned runtime.
- All Jest suites pass with counts; production build passes.
- Browser smoke covers student login/navigation and instructor historical audit
  evidence with no console/network error.
- CI uses the same runtime and commands.
- Lockfiles have intentional reviewed diffs only.

Evidence: runtime versions, install/test/build transcripts and screenshots in
`evidence/frontend-toolchain/`.
