# CC-9 Acceptance Report — Supply Chain Decision API Hardening

**Spec:** `specs/CC-09-decision-api-hardening.md`
**Branch:** `cc-09-decision-api-hardening`
**Observes:** `STANDING-DISCIPLINE.md`
**Status:** Complete — all acceptance criteria met.

---

## 1. Verify-Before-Wire (STANDING-DISCIPLINE §1)

- `python3 manage.py check` → *System check identified no issues (0 silenced).*
- `showmigrations core | tail` → graph clean; latest `0051_instructor_overrides`.
- `grep "sc/round" core/urls.py` → 4 decision routes (sourcing, logistics, trade-finance, inventory) + scenario-content + state-retrieval + override routes confirmed.
- CC-8 seed rows present: `Supplier=25, ShippingLane=20` → CC-9's CC-8 dependency satisfied.
- Verified against the **actual** models/serializers (not the spec prose): field names, `unique_together` natural keys, decimal precisions, FK targets, permission classes (`IsTeamMember`, `IsRoundOpen` in `core/views/decisions.py`), and the progressive-disclosure helper (`core/utils/disclosure.get_effective_unlock_round`).

No MISMATCH halts. Three integration issues found and fixed (see §5).

---

## 2. What Was Hardened

**Root cause:** CC-4 built complete, correct write serializers, but the views bypassed them. Only `LogisticsDecisionWriteSerializer` (for logistics items) was actually invoked. Sourcing, incoterms, customs, trade-finance, sinosure, FX, inventory, and contingency all wrote via raw `request.data` `.get()`/`item[...]` access — no validation, `KeyError`→500 on missing fields, no cross-field checks.

**Fix:** every SC POST sub-collection now validates through its write serializer with `is_valid(raise_exception=True)` **before** any DB write (whole-submission atomicity via `@transaction.atomic`), then upserts on the model's natural key. Missing/invalid fields now yield `400` with structured serializer errors instead of `500`.

| Endpoint | Before | After |
|---|---|---|
| `SourcingView.post` | raw dict, dead serializer line, no validation | `SourcingDecisionWriteSerializer` (nested allocations), sum-to-100-per-category, disclosure |
| `LogisticsView.post` | logistics only validated; incoterms/customs raw | all three validated; modal-mix sum-100 + mode-availability |
| `TradeFinanceView.post` | all raw | trade-finance/sinosure/FX validated; instrument + currency-pair checks |
| `InventoryView.post` | all raw | inventory + contingency validated; disclosure |

**Response bodies (§3.6/§3.7):** every POST now returns the **same body shape as GET** (re-serialized current state), so edit forms rehydrate after submit. Previously POSTs returned `{'status': 'ok'}`.

**Server-side identity:** `team`/`round` are injected from the URL, never trusted from the payload. Only client-supplied keys are forwarded, so server defaults don't trip progressive-disclosure locks.

Mapping to spec §3 required fixes: 1 ✅ (all POSTs validated) · 2 ✅ (disclosure via `_reject_locked_fields`) · 3 ✅ (`IsRoundOpen` retained) · 4 ✅ (`IsTeamMember` retained) · 5 ✅ (400 + structured errors) · 6 ✅ (stable GET-shaped bodies) · 7 ✅ (GET returns full edit context) · 8 ✅ (atomic sourcing; sum-to-100 per category) · 9 ✅ (modal mix sum-100 per lane; unavailable modes rejected) · 10 ✅ (trade-finance instrument + FX currency-pair validation when scenario data present).

---

## 3. Endpoint Samples

**Read-only GET (live, against loaded `Consumer Electronics 2026`):**

```
GET /api/scenarios/5/suppliers/?specialization=semiconductor  -> 200
[
 {"id":27,"supplier_id":"tsmc_taiwan","name":"Taiwan Semiconductor Manufacturing Company",
  "country":"TW","tier":1,"base_unit_price_usd":"45.00","quality_rating":"0.960",
  "reliability_rating":"0.930","specialization":["semiconductor"], ...},
 ...
]
```

**Valid sourcing POST → 201 (round 5), body rehydrates GET shape:**

```
POST .../sc/round/5/sourcing/
{ "tier_2_3_visibility_investment":"comprehensive", "multi_sourcing_strategy":"dual_source",
  "allocations":[
    {"critical_input_category":"semiconductor","supplier":27,"allocation_pct":60,"payment_terms":"letter_of_credit"},
    {"critical_input_category":"semiconductor","supplier":28,"allocation_pct":40}]}
-> 201  { "decision": {...}, "allocations": [ {...}, {...} ] }
```

**Invalid payloads → 400 with structured errors:**

```
sourcing allocations sum 60 (not 100)  -> 400
  {"allocations":["Allocation percentages must sum to 100 per critical input category; got {'semiconductor': 60}."]}

logistics modal mix sum 60             -> 400  {"non_field_errors":["Modal mix must sum to 100; got 60"]}
logistics rail on rail-unavailable lane-> 400  {"non_field_errors":["Mode rail not available on lane cn_to_us"]}
locked field at early round            -> 400  {"non_field_errors":["sourcing.tier_2_3_visibility_investment not yet unlocked at round 1 ... (unlocks at round 5)."]}
unknown trade-finance instrument       -> 400  {"buyer_payment_instrument":["Unknown trade finance instrument 'bogus_instrument'. Allowed: [...]"]}
unknown FX currency pair               -> 400  {"currency_pair":["Unknown currency pair 'XXX_YYY'. Allowed: ['EUR_CNY','USD_CNY']"]}
write to non-open round                -> 403  (IsRoundOpen)
unresolved / missing auth header       -> 403  (IsTeamMember)
```

---

## 4. Tests

New module `core/tests/test_cc09_sc_api.py` — **19 tests, all passing.** Exercises the real views through `APIRequestFactory` with the production `X-User-Id` header auth path.

```
$ python3 manage.py test core.tests.test_cc09_sc_api --verbosity=1
...................
Ran 19 tests in 2.7s
OK
```

Coverage vs spec §5: sourcing GET-empty + POST/GET round-trip; invalid allocation total; locked field; **override unlocks** field; non-open-round write (403); unauthorized (403); logistics POST/GET round-trip; invalid modal mix; unavailable mode; available mode accepted; modal-mix locked pre-R3; trade-finance POST/GET round-trip; invalid instrument; FX valid + invalid currency pair; inventory POST/GET round-trip; contingency round-trip; contingency locked pre-R5.

**Full suite (spec §6.5):**

```
$ python3 manage.py test --verbosity=1
Ran 105 tests in 8.2s
FAILED (failures=1)
```

**Pre-existing failure (NOT introduced by CC-9, present at baseline before any CC-9 edit):**
`core.tests.test_engine.TestEngineIntegration.test_advance_round_unlocked_team` — asserts `advance_round` raises `ValueError` for an unlocked team; the Phase-2 background thread logs `Phase 2 failed: Game matching query does not exist.` This is an engine/round-advance concern unrelated to the SC API surface. Documented per §5, not fixed.

---

## 5. Issues Found & Fixed / Known Limitations

1. **Mode-availability bug (fixed).** `LogisticsDecisionWriteSerializer` rejected a mode unless `lane.modes[mode]['available'] is True`. But CC-8 stores `sea`/`air` with real parameters and **no** `available` key (only `rail`/`road` use `{'available': false}`). Every sea/air submission would have been wrongly rejected. Added `mode_is_available(lane, mode)`: a mode is available when its entry exists and is not explicitly `available: false`. Covered by `test_available_mode_accepted` and `test_unavailable_mode_rejected`.

2. **Missing sourcing sum-to-100 validation (added).** No layer enforced allocation percentages summing to 100 per critical input category (spec §3.8). Added to `SourcingDecisionWriteSerializer.validate` over the nested allocations; only categories present in the payload are checked.

3. **Required-field vs progressive-disclosure conflict (fixed).** `payment_terms` and `buyer_payment_instrument` are `NOT NULL` with no DB default but are disclosure-locked until rounds 4/4. Routing through serializers made them DRF-required, which would make an early-round submission impossible (catch-22). Declared them `required=False, allow_blank=True, default=''` in the write serializers (matching the old view's `.get(..., '')`).

4. **`enrollment` / `team_member` tables absent from the test migration graph (pre-existing infra limitation).** These legacy models are `managed=False` and, unlike `users` (bootstrapped by `0000_users_bootstrap`), have no bootstrap migration, so the student-enrollment branch of `IsTeamMember` cannot execute in-process during tests. The unauthorized-access test therefore exercises the rejection paths that do **not** touch those tables (unresolved user-id header, and no header) — both correctly 403. The instructor-role allow path and all round-trips are fully exercised. No production code depends on this; it is a test-harness gap only.

5. **Calibration/semantics note.** `_reject_locked_fields` treats any truthy value as "submitted", so submitting a locked field's *baseline* value (e.g. `tier_2_3_visibility_investment='none'`) before unlock is also rejected. This is the pre-existing CC-4 serializer semantics; left unchanged. Frontends should omit locked fields rather than send baseline values at early rounds.

---

## 6. Acceptance Criteria (spec §6)

1. ✅ All SC POST paths use validated write paths.
2. ✅ API tests cover every case in §5 (19 tests).
3. ✅ `python3 manage.py check` passes.
4. ✅ New focused API tests pass (19/19).
5. ✅ Full `manage.py test` run and reported (105 tests, 1 pre-existing failure documented).
6. ✅ This report records endpoint samples and test output.
7. ✅ No React frontend work included.
