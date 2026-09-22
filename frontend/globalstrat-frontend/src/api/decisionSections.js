/**
 * The section names `PATCH .../decisions/round/N/<section>/` accepts.
 *
 * This is a copy of the keys of `_TYPE_MAP` in `backend/core/views/decisions.py`
 * and exists so the two can be held together by tests. For as long as there
 * was no such list, two pages saved to `talent_allocations` and
 * `compliance_investments` -- names the server had never heard of -- and every
 * one of those saves was refused (2026-09-21).
 *
 *   - `pages/sectionPayloads.test.js` fails when a page names a section that
 *     is not in this list;
 *   - `core/tests/test_silent_section_saves.py` fails when this list and
 *     `_TYPE_MAP` differ.
 */
export const DECISION_SECTIONS = [
  'budget',
  'rd',
  'platforms',
  'products',
  'product-retires',
  'marketing',
  'market-entry',
  'financing',
  'plants',
  'partnerships',
  'acquisitions',
  'esg',
  'event-responses',
  'talent',
  'talent-allocations',
  'compliance-investments',
];
