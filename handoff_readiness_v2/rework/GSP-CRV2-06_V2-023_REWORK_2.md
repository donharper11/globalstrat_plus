# GSP-CRV2-06 — V2-023 rework 2

## Decision

**FAIL / REWORK.** The runtime correction passes focused audit, but the submitted
evidence set does not verify.

## Blocking evidence defects

1. `characterisation.json` currently hashes to
   `b58fb4dfb003162124fd24cbffe5f6e9451ca7000bfcc5a483b9415cdf5782b3`, while
   `SHA256SUMS` records
   `b98e11b626a019ebd88a07abd14d4b29406d3bfd46bfab315a2d8eaee83ddb10`.
2. The new `v2-023-gate.json` is not listed in `SHA256SUMS` at all.

An evidence set whose changed artifact fails its checksum and whose principal
gate artifact is outside the inventory cannot certify the closure.

## Required rework

- Regenerate `SHA256SUMS` from the final, committed evidence artifacts.
- Include both `characterisation.json` and `v2-023-gate.json`.
- Verify the entire inventory with `sha256sum -c SHA256SUMS`.
- Commit the corrected inventory and report the revision and clean-tree state.

Do not rerun the gate, grid, focused tests, full suite, or any unrelated drill.
The auditor independently ran `core.tests.test_reference_price`: 28/28 passed.
This rework is checksum/provenance only.
