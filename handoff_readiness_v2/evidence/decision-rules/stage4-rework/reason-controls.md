# Stage 4 rework — reason controls

Each repair was reverted in isolation at runtime `eae18e5` and the new tests
re-run, to show they fail for the intended cause rather than passing because
they never looked. Every revert was restored immediately afterwards and the
suite re-run to `OK`.

## V2-051 — hierarchy binding

Reverted: `_get_team` back to a global primary-key lookup, and the target
platform back to a global lookup.

```text
AssertionError: unexpectedly None            <- no refusal event recorded
AssertionError: 200 not found in (403, 404)  <- the instructor case
AssertionError: 400 not found in (403, 404)  <- the student case
Ran 6 tests ... FAILED (failures=3)
```

The instructor case reproduces the audit's finding exactly: **HTTP 200** on a
cross-game write. The student case returned **400**, not the 200 the audit
recorded — in this fixture it stopped on an incidental platform mismatch rather
than on any scope check, so the route still failed to refuse it for the right
reason. Restored: `Ran 6 tests ... OK`.

## V2-050 — brand awareness after a switch

Reverted: the historical marketing filter back to
`team_product__team_platform=resolved_platform(product, current_round)`.

```text
AssertionError: 0.0 != 0.2591817793182821
AssertionError: 0.2591817793182821 != 0.0
Ran 3 tests ... FAILED (failures=2)
```

Same shape as the audit's `0.9516258196404048 -> 0`: a past round's awareness
collapses to zero after a later switch. The absolute value differs because this
fixture authors a different half-life; what matters is non-zero becoming zero.

The third test in that class — an *unswitched* product — passed under the
revert too. That is expected and worth stating: it is the negative control, and
a control that failed alongside the others would mean the test was measuring
the switch rather than the defect.

Restored: `Ran 3 tests ... OK`.

## V2-049 — write-off accounting

Reverted: `platform_switch_write_off` removed from `total_opex`.

```text
AssertionError: Decimal('-500000.00') not less than Decimal('-500000.00')
AssertionError: Decimal('-500000.00') not less than Decimal('-500000.00')
AssertionError: Decimal('0.00') != Decimal('750.00')
Ran 8 tests ... FAILED (failures=3)
```

Operating income stays at `-500000.00` — the audit's figure — instead of
falling by the $750 the history row and `context.opex` both already recorded.
Restored: `Ran 8 tests ... OK`.

## Ordering guard (carried from the first Stage 4 submission)

Reverted: the `.order_by('id')` on `missing_platform_resolutions`.

```text
product_platform.py:140 list(TeamProduct.objects.filter(team__game=game,
    status='active').select_related('team', 'team_platform'))
FAILED (failures=1)
```

Restored: `OK`.
