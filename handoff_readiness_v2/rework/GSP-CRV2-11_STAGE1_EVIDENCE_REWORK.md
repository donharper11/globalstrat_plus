# GSP-CRV2-11 Stage 1 runtime evidence audit — REWORK

Audited revisions: published runtime `3cb5f54`; local-only Stage 1 evidence
`80818a2..6348505`.

## Decision

**REWORK — evidence wording only. Do not change runtime code or begin Stage 2.**

The disposable Consumer Electronics replay is credible. A fresh independent
audit replay against the current checkout produced the same 250
segment-market-round allocations (the only replay-export difference was the
randomly generated team names), and the independent Bass calculation again
matched the engine within the persisted two-decimal precision:

- maximum absolute divergence: `0.005` units;
- maximum relative divergence: `0.000054290%`;
- every published pool balances as human + AI + unserved.

`core.tests.test_calibration` also passed independently: 9 tests, 0 failures.
The audit database was disposable and dropped by the runner.

## Required correction

The Stage 1 artifacts contradict the runtime they evidence. `b9510dc` changed
`events.py` to compound population growth, and the current replay demonstrably
uses that code. Yet the submitted artifacts still say the opposite in several
current-tense labels:

- `independent_bass.py` says flat growth is what `events.py` “computes today”
  and labels its output `flat (today)`;
- `STAGE1_MEASUREMENTS.md` says “The flat column is what ships today.”

Change these to identify flat growth as the **pre-CRV2-11 / historical
comparison** and compounding as the **current shipped runtime**. Preserve the
three-regime comparison and its numbers; the issue is provenance wording, not
the measurement. Ensure the closing “no tuning” language does not imply the
already-landed compounding repair is merely a reference proposal.

## Rework scope and verification

1. Edit only `STAGE1_MEASUREMENTS.md` and `independent_bass.py` (plus this
   report if you choose to commit it with the correction).
2. Do not alter runtime code, YAML parameters, migrations, saved replay JSON,
   or the baseline field.
3. Run the standalone `independent_bass.py --rounds 10` output and confirm its
   labels now distinguish historical flat from current compounding.
4. Run `git diff --check`, commit the documentation-only correction, and return
   the exact revision and output excerpt for re-audit.

## Not a closure

This audit does **not** certify the competent-field or archetype-parity work
required by CRV2-11 Stage 2. Nor does it remove CRV2-08's completion-report
input required before final CRV2-12 certification. Those are separate,
remaining programme dependencies.
