# Writing a message a participant reads

**Status:** the CRV2-12 Stage 2 standard. Binding on any new participant- or
instructor-facing string in this repository.
**Enforced by:** `backend/scripts/check-participant-strings`, which fails the
build. The rules below that a machine can check are checked; the rest are
review points, and the check's scope is declared in
`backend/scripts/participant-strings.config.json`.

The audience is an executive-education student under time pressure, playing in
English or in Simplified Chinese, who has just been stopped from doing
something. They need to learn what the rule is and what to do next. They must
not learn a column name.

---

## 1. Name the business object, never the column

`retail_price` is "unit price". `target_market_ids` is "target markets".
`rd_budget` is "R&D budget". The mapping lives in `FIELD_LABELS` in
`core/utils/participant_messages.py`; add to it rather than writing the label
inline, because the same field is refused from more than one surface.

**Enforced:** assertion A3 fails the build when a catalogue sentence contains a
name that the Django models declare as a field. Placeholder *names* are
excluded — `{unlock_round}` is substituted before anyone reads the sentence.

## 2. Never show an internal id

`market 7` is the market's name, resolved through
`get_localized_field(market, 'name', language)` so the name itself is also in
the reader's language. The same applies to product, platform, team and
submission ids.

## 3. Say what the rule is, and what to do next

> Marketing spend of $4,200,000 exceeds the marketing budget of $3,000,000.
> Reduce spending or increase the budget.

Two sentences: the rule, then the action. A message that states only the rule
leaves the reader to guess which of five screens to open.

## 4. A refusal at submit names the decision area

"Validation failed." is not a message. Name the area the team must navigate to
— "Open Marketing Mix to set unit price, production volume and promotion" —
because the refusal arrives on the Summary page, not on the page that can fix
it.

## 5. Warnings and refusals must read differently

A **warning** is advice about an action that was accepted: the value is saved,
and the sentence says so. A **refusal** means nothing was saved.

> warning — "Your entry has been saved. If it is still outside the range when
> the round closes, it will be adjusted to the nearest allowed price."
> refusal — "Set a unit price above zero for Atlas in Germany."

The price band (`core/services/price_band.py`) is the reference: the module
decides *which* state applies, and the catalogue holds the sentence for each,
so no surface can soften a refusal into a warning by picking a different
string.

## 6. The rule is worded in one place and imported

One sentence per rule, in `core/utils/participant_messages.py` (decisions) or
`core/utils/cohort_messages.py` (cohort administration). Import it; do not
restate it. Three surfaces describing one rule three ways is the defect this
exists to prevent — and it is not hypothetical: the Decision Summary and the
lock validator described the projected-cash rule with two different sentences
and two different money formats until CRV2-12.

This includes class attributes. `IsTeamMember.message` is
`participant_message('permission_denied')`, not a second copy of the sentence.

**Enforced:** assertion A4 fails the build on a hard-coded string in a
participant-facing route. A catalogue-backed message is a function call, so
only a literal is reported.

## 7. Both languages, with the same values in each

Every entry carries `en` and `zh-CN`. A message that interpolates a value must
interpolate the **same set** of values in both languages — this is where
translated strings break, because a translator reorders a sentence and drops a
placeholder, and the failure surfaces as a `KeyError` at the moment a team is
already being refused.

**Enforced:** A1 (both languages present), A2 (identical placeholder sets), A6
(the same, for the frontend `en.json` / `zh-CN.json` catalogues).

## 8. Money, percentages and rounds are formatted by the caller

The catalogue template holds `{spent}`, not `${spent:,.2f}`. The caller formats
and passes the finished string, so one rule cannot render its money two ways on
two screens. Match the existing format: `f'${value:,.2f}'` for cash,
`f'{value}%'` for percentages, plain integers for round numbers.

## 9. Structured data can still be copy

A dict is not automatically safe. The R&D platform-generation prerequisite rows
are `{'requirement': ..., 'detail': ...}`, and `RDPage.js` renders them as
`{requirement} — {detail}` with no `t()` — so they are participant copy and
reached Chinese teams in English for as long as they looked like data.

Ask what renders it, not what shape it has. Which modules build participant
payloads this way is declared in the check's `participant_payload_dicts`; a
service module's diagnostic record, which is *supposed* to name the model and
the row, is deliberately not in that list.

## 10. Operator and log strings stay technical

An engineer reading a log needs the field name. `decision_limits.
persisted_violations` names the model, the row and the field on purpose. The
boundary is the route: if a string can be rendered to a student or an
instructor, it follows this standard; if it can only reach a log or an
operator, it should stay precise and technical. Record which, per string —
`evidence/player-language/STATIC_STRING_INVENTORY.md` classifies every
candidate, and an `operator-or-log-only` classification needs a stated
route/log boundary, not silence.

---

## Adding a string

1. Add the key to `MESSAGES` with `en` and `zh-CN`.
2. Call `participant_message('key', language=language, **values)`.
   Resolve `language` with `get_user_language(request)` — once per request;
   it is memoised on the request object.
3. Run `backend/scripts/check-participant-strings`.

If the check flags something it should not, the fix is a reasoned entry in
`participant-strings.config.json` — every suppression carries a stated reason,
an entry without one is exit 2, and a suppression that no longer matches
anything is reported as stale rather than ignored.
