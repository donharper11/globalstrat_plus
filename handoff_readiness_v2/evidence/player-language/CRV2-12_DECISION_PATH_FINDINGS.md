# CRV2-12 decision validation/submission findings

**Recorded before repair:** 2026-09-11

## F-PL-01 — decision refusals bypassed the bilingual catalogue

`backend/core/serializers/decisions.py` and `backend/core/views/decisions.py`
contained English-only validation/refusal strings on the main draft save,
per-decision PATCH, and lock paths. Several exposed storage identifiers such
as `channel_digital_pct`, `new_debt`, and `allocation_amount`. The partial
decision endpoint also constructed serializers without the request context, so
even catalogue-backed serializers could not honour `Accept-Language`.

**Risk:** A Simplified-Chinese participant could receive English-only or
technical validation text at the point where a decision must be corrected;
some messages did not explain the corrective action in business language.

**Repair boundary:** participant-facing decision serializers and the decision
submission, PATCH, lock and round-status refusals only. This record does not
claim that the broader Stage 1 inventory is complete.
