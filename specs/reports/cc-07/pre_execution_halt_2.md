# CC-7 Pre-execution Halt Report #2

**Spec:** CC-07-fork-and-clean.md
**Status:** On branch cc-07-fork-and-clean, pre §2.4 baseline capture.
**Observes:** STANDING-DISCIPLINE.md §3, §7

Preconditions §2.1-§2.3 now pass (CC-04 A1 merged to main, tree clean,
CC-5 reports complete, override models present, `manage.py check` clean).
Halting at §2.4 on two findings neither of which is self-healable.

---

## FINDING A — test discovery is silently amputated

```
MISMATCH DETECTED
Spec reference: CC-7 §2.4 `python manage.py test --verbosity=2`
                "Record the pass/fail count *before* any CC-7 changes."
Actual state:   Default Django discovery finds only 13 tests
                (all from core/engine/tests/*). The core/tests/ directory
                -- which holds test_cc04_a1_overrides.py (16 tests) and
                test_engine.py (67 test functions, 57 collected) --
                is invisible because core/tests/__init__.py does not
                exist. core/engine/tests/__init__.py does.

                True state, enumerated explicitly:
                  core.tests.test_cc04_a1_overrides           16 tests   pass
                  core.tests.test_engine                      57 tests   56 pass, 1 FAIL
                  core.engine.tests.test_determinism           6 tests   pass
                  core.engine.tests.test_rng                   7 tests   pass
                  Total                                       86 tests   85 pass, 1 FAIL

Location:       backend/core/tests/__init__.py  (missing)
                backend/core/engine/tests/__init__.py  (present, 0 bytes)
Proposed action: Spec author picks one:
                 (a1) Add an empty backend/core/tests/__init__.py as a
                      one-commit "test-infra prep" step at the HEAD of
                      cc-07-fork-and-clean, BEFORE Wave 1. Restores
                      Django's default discovery to the true 86-test
                      suite. Arguably belongs to CC-04 Amendment A1's
                      test-infra scope but was missed.
                 (a2) Record the baseline using explicit module paths
                      (what I used above to reach 86). Leave the
                      missing __init__.py alone -- the baseline and
                      every post-wave check must re-enumerate.
                 (a3) Accept the §2.4 command literally -- baseline is
                      13 tests. CC-7 is held to regressions in those 13
                      only. The invisible 73 tests are out of scope and
                      may silently break. NOT RECOMMENDED.
                 Default reading is (a1) -- it's a 0-byte file, purely
                 restorative, and makes every subsequent wave check
                 straightforward.
Halting for review.
```

## FINDING B — pre-existing failing test in test_engine.py

```
MISMATCH DETECTED
Spec reference: CC-7 §2.4 "any test that was passing before CC-7 must
                still pass after."
Actual state:   core.tests.test_engine.TestEngineIntegration
                .test_advance_round_unlocked_team fails on main BEFORE
                CC-7 begins. Assertion: `with self.assertRaises(ValueError)`
                -- ValueError not raised. Engine logs also show
                "Phase 2 failed: Game matching query does not exist."
                in the test output. Looks like test fixture drift
                between CC-3 engine state and CC-5 post-promotion
                schema. Pre-existing. Not caused by CC-7.
Location:       backend/core/tests/test_engine.py:242
Proposed action: (b1) Treat as baseline state: test was failing before
                      CC-7, so CC-7's obligation is "still failing in
                      the same way" rather than "passing." Record as
                      pre-existing and move on. No CC-7 action.
                 (b2) Investigate and fix. OUT OF SCOPE for CC-7 per
                      §6.2 (no logic changes). Deferred to a later CC.
                 (b3) Halt CC-7 entirely until the spec author fixes
                      test_engine in a separate spec.
                 Default reading is (b1) combined with (b2) recorded
                 in the execution_report.md "Deferred items" section.
Halting for review.
```

---

## What IS done

- Branch `cc-07-fork-and-clean` cut from main at 71f6e24.
- Preconditions §2.1, §2.2, §2.3 verified (see the first halt report
  for the resolution of MISMATCH 1-3).
- `python manage.py shell -c "from core.models import
  ClassProgressiveDisclosureOverride, ClassResilienceWeightOverride"`
  succeeds.
- `python manage.py check` reports 0 issues.

## What is NOT done

- §2.4 baseline file (`pre_execution_test_baseline.txt`) not yet
  written -- holding until FINDING A is resolved so the baseline
  captures the intended discovery surface.
- No wave commits, no deletions, no edits. Branch is at main's tip
  plus nothing.

## Recommended next input

One line from the spec author confirming (a1 or a2) + (b1).
Default is (a1) + (b1) + (b2 deferred).
