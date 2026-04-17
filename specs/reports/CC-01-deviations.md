# CC-01 Deviations Report

**Project:** globalstrat+
**Spec executed:** `specs/CC-01-scenario-schema.md`
**Execution date:** CC-1 acceptance landed on main prior to Amendment A1
**Reference:** `specs/CC-01-amendment-A1.md` (detailed narrative and forward commitments)

This report formalizes the three deviations surfaced during CC-1 execution. Each entry captures the deviation, the executed resolution, the residual state (if any), and the forward reference that commits any remaining work to a named spec.

---

## Deviation D1 — Bootstrap schema absent from source repo

**Category:** Infrastructure gap.
**Discovered during:** Migration 0016 execution on fresh `globalstrat_plus` database.
**Symptom:** `relation "users" does not exist` — migration 0016 declared a foreign key against a table that `core/migrations/0001_initial.py` had marked `managed: False`, meaning Django did not create it.

**Root cause:** The original GlobalStrat database schema for unmanaged tables was provisioned via a hand-crafted SQL script that was never committed to the source repository. The script was effectively lost; only the live database retained the schema.

**Resolution executed:**
- `pg_dump --schema-only --no-owner --no-privileges` executed against live GlobalStrat for the 10 physically-provisioned unmanaged tables.
- Output committed at `scripts/bootstrap/unmanaged_tables_schema.sql` with accompanying README.
- Schema applied to `globalstrat_plus`; migrations 0016–0039 completed cleanly.

**Residual state:** None. Deviation is closed.

**Forward reference:** STANDING-DISCIPLINE.md §1 implicitly governs this pattern; future Camdani simulation forks observe a "bootstrap in-repo" rule — any externally-provisioned schema required for fresh-DB function travels with the source code.

---

## Deviation D2 — Ghost models in the fork

**Category:** Schema-reality drift.
**Discovered during:** Investigation of D1.
**Symptom:** `core/migrations/0001_initial.py` declares 50 models with `managed: False`. Only 10 were ever physically provisioned in GlobalStrat's live database. The remaining 40 exist only as Django model scaffolds.

**Root cause:** The original GlobalStrat build declared a superset of intended tables in the initial migration, either as speculative scaffolding or as placeholders for features never implemented. No migration or bootstrap script ever created the remaining 40. Over time, the divergence between the Django model layer (50 models) and the physical database (10 tables) was never reconciled.

**Resolution executed:** None in CC-1 or Amendment A1. Documented as known state.

**Residual state:** 40 ghost models remain in `core/models.py` — registered in Django's `_meta` registry, returned by `apps.get_models()`, queryable via the ORM at import time, but with no underlying database table. Any code that references them will pass static inspection and fail at query time.

**Protective measures in place:**
- CC-02-decision-taxonomy.md §2.1 now requires a two-section field inventory report (per-model inventory + ghost roster) before CC-2 can proceed. Ghost EXTEND targets are an explicit halt condition.
- STANDING-DISCIPLINE.md §1.8 (added via Amendment A1) requires model-to-table cross-reference for every spec that references existing models.

**Forward reference:** Full resolution in CC-5 (fork audit). CC-5 will classify each of the 40 ghosts as prune, promote, or document-as-dormant. Default disposition is prune. Dormant classification requires a named future CC that commits to promoting the model.

---

## Deviation D3 — pg_dump client version drift

**Category:** Tooling mismatch.
**Discovered during:** Resolution of D1.
**Symptom:** VM had `pg_dump` 14 installed; PostgreSQL server at 192.168.50.38 runs version 16. Older pg_dump against newer server can silently produce incomplete or incorrect schema dumps (missing new syntax, unsupported column types, partial coverage of newer features) without any error at dump time.

**Root cause:** The VM's base image included an outdated PostgreSQL client package. No preflight check existed to catch the mismatch.

**Resolution executed:**
- `postgresql-client-16` installed on the VM as a prerequisite to the D1 dump.
- D1 dump taken with pg_dump 16; inspected for expected shape (CREATE TABLE count, absence of COPY / DROP) before applying.

**Residual state:** None. Deviation is closed; the VM now has matching client tooling.

**Forward reference:** STANDING-DISCIPLINE.md §1.9 (added via Amendment A1) requires client/server version alignment preflight before any `pg_dump`, `pg_restore`, or version-sensitive DB operation. The rule generalizes to any future simulation in the Camdani portfolio.

---

## Summary

| Deviation | Category | State | Forward spec |
|---|---|---|---|
| D1 — Bootstrap schema absent | Infrastructure gap | Closed | — |
| D2 — 40 ghost models | Schema-reality drift | Open (documented) | **CC-5** |
| D3 — pg_dump version drift | Tooling mismatch | Closed | — |

Two of three deviations are fully resolved. The remaining one (D2) has protective measures in place (CC-2 §2.1 field inventory, STANDING-DISCIPLINE.md §1.8) and a committed resolution pathway in CC-5.
