# CRV2-07 combined deadline, refresh and Phase-1 resolution inventory

**Phase:** development inventory, 2026-09-11.  This is not release evidence.

The outstanding CRV2-07 row is a single integrated traffic pattern.  The
registered product interfaces it must exercise are deliberately small and are
listed here before the driver implementation:

| actor | registered route | traffic / expected outcome |
|---|---|---|
| authenticated student | `GET /api/games/<game>/teams/<team>/decisions/round/<round>/summary/` | refresh throughout the open round and while Phase 1 runs |
| authenticated student | `PATCH /api/games/<game>/teams/<team>/decisions/round/<round>/budget/` | acknowledged writes before close; explained 4xx refusals after close |
| authenticated student | `POST /api/games/<game>/teams/<team>/decisions/round/<round>/lock/` | final-minute submission lock attempt racing close |
| owning instructor | `POST /api/games/<game>/round-control/process/` | `force=true` plus an audited reason: closes then runs synchronous Phase 1 |

The scenario seeds a complete `initialize_game --teams N` cohort, not bare
`Team` rows.  Resolution requires platform, product, market-presence and
round-zero state, so a team-only extension would not be a valid field
simulation.

The development smoke uses eight identities and short windows.  Release
profiles retain the fixed CRV2-07 sizes: field = 96 sessions / 24 firms and
margin = 288 sessions / 24 firms.  Release profiles may only write immutable
evidence from a clean frozen candidate; a smoke result is a harness proof,
not capacity evidence.
