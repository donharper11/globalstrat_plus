# CC-01 Amendment A1 — Bootstrap Realities & Standing Discipline Updates

**Amends:** `specs/CC-01-scenario-schema.md`
**Observes:** `specs/STANDING-DISCIPLINE.md` (itself updated by this amendment)
**Status:** Ready for Claude Code execution
**Parallel-safe:** does not touch the CC-2 execution surface (no DB migrations, no model changes, no shared files beyond specs)

---

## 1. Purpose

This amendment captures three deviations surfaced during CC-1 execution, promotes the lessons into permanent discipline, and forward-references the work that will resolve the open items. The original `CC-01-scenario-schema.md` remains unchanged as the historical record of what was originally specified. This amendment is the authoritative source for what was actually executed and what follow-up work is committed.

Three deviations are addressed:

1. The fork's bootstrap schema was absent from source — 10 physically-provisioned unmanaged tables had to be reverse-engineered from prod via `pg_dump` and captured in-repo.
2. 40 of 50 models declared `managed: False` in `core/migrations/0001_initial.py` are ghost models — registered in Django but never physically provisioned.
3. The VM had `pg_dump` version 14 against a PostgreSQL 16 server; `postgresql-client-16` was installed as a precondition.

---

## 2. Deviation 1: Bootstrap Schema Capture

### What happened

The original CC-1 assumed `python manage.py migrate` against an empty `globalstrat_plus` database would produce a working schema. Migration 0016 broke this assumption by declaring a foreign key against `core.user` — a table declared with `managed: False` in 0001, never created by Django, and never captured in a bootstrap script committed to the repo. The original GlobalStrat database was provisioned via a hand-crafted SQL script that was lost to history.

### What was executed

Claude Code used `pg_dump --schema-only --no-owner --no-privileges` against the live GlobalStrat database at 192.168.50.38 to extract the physical schema of the 10 unmanaged tables that actually existed. The dump was committed to the repo at `scripts/bootstrap/unmanaged_tables_schema.sql` with a README explaining its purpose and provenance. Migrations then completed cleanly through 0039.

### Why this matters beyond CC-1

The lost-bootstrap-script failure is exactly the category of problem that destroys future forks. Anyone who later forks globalstrat+ or rebuilds it from scratch must find the bootstrap schema in-repo. The same pattern now applies to all downstream Camdani simulations that fork from a reference codebase: the bootstrap schema travels with the code.

### Forward commitment

Future simulation forks in the Camdani portfolio observe a "bootstrap in-repo" rule: any externally-provisioned schema required for the app to function at a fresh-DB starting point is captured via `pg_dump --schema-only` and committed to `scripts/bootstrap/` at fork time. This rule is encoded in STANDING-DISCIPLINE.md (see §4 of this amendment).

---

## 3. Deviation 2: Ghost Models

### What happened

`core/migrations/0001_initial.py` declares 50 models with `managed: False`. Only 10 were ever provisioned in GlobalStrat's live database. The remaining 40 exist only as Django model scaffolds — present in `_meta.get_fields()` and the app registry, absent from the database.

### Current status

Documented as known state. No resolution attempted in CC-1 or this amendment. The ghost models are a known hazard for any spec that naively references them.

### Why this matters beyond CC-1

Ghost models are dangerous because Django's introspection reports them as normal. Any code that does `from core.models import X` where X is a ghost succeeds; the failure only appears at query time. Without an explicit model-to-table cross-reference, a spec can reference a ghost model and pass every static review, only to fail in production.

CC-2's field inventory has already been hardened against this (per the CC-2 ghost-model edit). STANDING-DISCIPLINE.md §1.8, added in this amendment, makes the check permanent across all future specs.

### Forward commitment: CC-5 (fork audit)

Resolution is explicitly deferred to CC-5 (fork audit). CC-5's classification framework already contemplates KEEP / ADAPT / DISCARD / NEW against the existing codebase; ghost models fit naturally into that pass. CC-5 will triage the 40 ghosts into:

- **Prune** — scaffold was speculative, no globalstrat+ use, delete from `core/models.py`.
- **Promote** — globalstrat+ needs the table; generate a managed migration that creates it with matching schema.
- **Document as dormant** — retain as scaffold for a specifically-identified future feature, with explicit in-code comment warning against naive reference.

The default disposition is prune. Dormant scaffolds are explicitly discouraged because they invite the same failure mode that created this deviation. Any "document as dormant" classification requires a named future CC that will promote the model.

---

## 4. Deviation 3: pg_dump Version

### What happened

The server at 192.168.50.38 runs PostgreSQL 16. The VM from which Claude Code executed `pg_dump` had only `pg_dump` 14 installed. Older pg_dump clients against newer servers can silently produce broken dumps — missing new syntax, unsupported column types — with no error surface until restore time.

### What was executed

`postgresql-client-16` was installed on the VM before the bootstrap dump was taken. The dump was verified by inspection (expected CREATE TABLE count, no COPY statements, no DROP statements) before being applied to `globalstrat_plus`.

### Forward commitment

STANDING-DISCIPLINE.md §1.9, added in this amendment, requires a version-alignment preflight before any `pg_dump` invocation. The rule generalizes to any database client/server pair (psql, pg_restore, future pgbouncer operations) where version drift produces silent failures.

---

## 5. Forward Reference: Qdrant Content Migration

CC-1 created an empty `globalstrat_plus_articles` collection on Qdrant with vector config matching the live `globalstrat_articles` collection (size 384, cosine distance). No content was migrated.

Content migration is a two-part work stream that lives in its own dedicated spec, targeting **CC-11** following the original GlobalStrat sequencing pattern:

1. **Inheritance layer.** Snapshot `globalstrat_articles` and restore into `globalstrat_plus_articles`. Retroactively tag all inherited chunks with `payload.topic = "strategy"` to enable future filtering.
2. **SC expansion layer.** Ingest net-new supply-chain, international-trade, logistics, trade-finance, compliance, and resilience content tagged with appropriate `payload.topic` values (`supply_chain`, `trade_finance`, `compliance`, `logistics`, `resilience`, `chinese_institutional`).

RAG source curation happens in parallel as a human-driven research task, not a Claude Code task. Target: 80–120 net-new articles across the six SC content buckets, matching GlobalStrat's current 143-article depth for the strategy side. A separate RAG Source Curation Guide (drafted on request) supports this.

CC-11 will not execute until the curated corpus is assembled and reviewed.

---

## 6. STANDING-DISCIPLINE.md Updates

Two rules added to STANDING-DISCIPLINE.md Section 1:

- **§1.8 Model-to-table verification** — cross-reference Django's model registry against physical tables before any spec operation that references existing models. Ghost models are a MISMATCH halt condition.
- **§1.9 Database client version alignment** — preflight client/server version match before `pg_dump`, `pg_restore`, or any version-sensitive DB client operation.

The full updated STANDING-DISCIPLINE.md is provided alongside this amendment and replaces the existing file.

---

## 7. Execution Steps for Claude Code

This amendment is handled by a separate Claude Code session from the CC-2 work. The surface is non-overlapping.

### 7.1 Branch

```bash
cd /home/ubuntu/projects/globalstrat+/
git checkout main
git pull --ff-only    # ensure up to date
git checkout -b cc-01-amendment-a1
```

### 7.2 Files to place

1. This amendment file at `specs/CC-01-amendment-A1.md`
2. Updated `specs/STANDING-DISCIPLINE.md` (provided alongside this amendment; overwrites existing)
3. New formal deviations report at `specs/reports/CC-01-deviations.md` (provided alongside this amendment)

Create `specs/reports/` if it does not yet exist.

### 7.3 Verification

Before committing, verify:

- `specs/CC-01-scenario-schema.md` is **unchanged** — the original spec remains the historical record.
- `specs/STANDING-DISCIPLINE.md` now contains sections §1.8 and §1.9 (diff the old and new versions to confirm only the intended additions are present).
- `specs/reports/CC-01-deviations.md` exists and references each deviation by number matching this amendment.

### 7.4 Commit sequence

One commit per logical change keeps history readable:

```bash
git add specs/CC-01-amendment-A1.md
git commit -m "CC-1 Amendment A1: document bootstrap realities and forward commitments"

git add specs/STANDING-DISCIPLINE.md
git commit -m "Standing Discipline: add §1.8 model-to-table verification and §1.9 client version alignment"

git add specs/reports/CC-01-deviations.md
git commit -m "CC-1 deviations report: formalize three findings from CC-1 execution"
```

### 7.5 Merge

After verification:

```bash
git checkout main
git merge --no-ff cc-01-amendment-a1 -m "Merge CC-01 Amendment A1"
```

Keep the `cc-01-amendment-a1` branch — do not delete. Amendment history is preserved.

---

## 8. Acceptance Criteria

This amendment is complete when:

1. All three files exist in the repo at the paths specified in §7.2.
2. `specs/CC-01-scenario-schema.md` is byte-identical to its state before amendment execution (verify via `git diff main~1:specs/CC-01-scenario-schema.md specs/CC-01-scenario-schema.md` — expect no output).
3. `git log --oneline` shows three amendment commits plus the merge commit.
4. `python manage.py check` still passes with zero issues (sanity check that no accidental code changes occurred).
5. The `cc-01-amendment-a1` branch is retained post-merge.

**Report back with:** `git log --oneline -6`, diff summary confirming CC-01-scenario-schema.md was not modified, and directory listing of `specs/` and `specs/reports/`.

---

## 9. What This Amendment Does NOT Do

Explicit non-goals, to prevent scope creep in the parallel Claude Code session:

- No ghost model pruning, promotion, or deletion. That is CC-5's work.
- No Qdrant content migration. That is the future CC-11's work.
- No changes to Django models, migrations, or any code files outside the `specs/` tree.
- No re-execution of CC-1 acceptance criteria. CC-1 is closed; this amendment documents what happened and sets forward direction.
- No changes to CC-02-decision-taxonomy.md. That spec is being handled in parallel and must not be touched.
