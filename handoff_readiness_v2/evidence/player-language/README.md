# CRV2-12 Stage 1 — language inventory method

This evidence covers the player-facing language sweep's Stage 1 only. It is
intentionally separate from the implementation work that routes messages
through the bilingual catalogue.

Regenerate both checked-in reports from the repository root:

```sh
python3 handoff_readiness_v2/evidence/player-language/generate_inventory.py
python3 handoff_readiness_v2/evidence/player-language/generate_inventory.py --check
```

The first command writes `STATIC_STRING_INVENTORY.json` for filtering and
audit, plus the reviewable `STATIC_STRING_INVENTORY.md`. The second is suitable
for a release gate: it fails when source wording changed without refreshing the
evidence. It uses Python's standard library only and intentionally scans the
tracked source tree, never a production database or a model response.

## Boundary and classification

- **participant-facing**: text in a player API/serializer, player generated
  content, or a non-`t()` participant React literal. It needs English and
  Simplified Chinese wording unless the reviewer records a reachability
  exemption.
- **instructor-facing**: instructor/course/round-control surfaces and
  instructor alerts. It belongs in the bilingual review too; teaching notes
  need instructional-design review rather than a mechanical translation.
- **operator-or-log-only**: service candidates with no static route proof.
  They are deliberately kept in the report so an internal error is not silently
  misclassified as a player message. An exemption must state the route/log
  boundary; otherwise promote it to one of the two user-facing classes.

The scanner deliberately reports candidates rather than claiming perfect
runtime reachability. Python source is parsed with `ast`; JSX/JavaScript is
scanned lexically to avoid a node_modules-only dependency. It excludes values
inside `t()` and obvious configuration/class strings, but a reviewer should
expect a small number of false positives. That is safer than hiding an English
literal from a bilingual competition release.

## Implementation sequence

1. Triage participant-facing backend refusals in `views/decisions.py` and
   decision serializers first; these block a team's round submission.
2. Apply the shared business-language catalogue to the remaining player API
   errors and templated events/persona content.
3. Move participant React literals into `locales/en.json` and
   `locales/zh-CN.json`, then treat instructor React literals and alerts as the
   final bilingual teaching-language pass.
4. Record reviewed exemptions in the final before/after inventory, then run
   the two EN/ZH walkthroughs required by CRV2-12.

The source handoff also requires a later prevention check for new untranslated
participant strings. This Stage 1 `--check` is an inventory-freshness control,
not that final enforcement control.
