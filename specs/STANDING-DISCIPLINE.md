# STANDING DISCIPLINE

**Scope:** Every CC spec in the globalstrat+ project observes this document.
**Status:** Binding. Deviations require explicit exception in the individual CC spec.

This document exists because prior builds have lost hours to preventable failures — made-up field names, assumed table names, stale model references, endpoint paths that didn't match the router. These are cheap to prevent and expensive to debug. Verification before wiring is the rule, not the exception.

Every CC spec begins with a header line that says "Observes: STANDING-DISCIPLINE.md" and Claude Code is expected to have read and internalized this file at the start of every bundle.

---

## 1. Verify Before Wire

Before writing any code that references an existing name — table, column, model field, endpoint path, settings key, Qdrant collection, environment variable, frontend route, CSS class — verify the name exists and matches exactly.

### 1.1 Database tables and columns

Before writing SQL, ORM queries, or migrations that reference an existing table:

```bash
# Inspect table structure directly
python manage.py dbshell
\d <table_name>

# Or via Django
python manage.py shell
>>> from app.models import ModelName
>>> [f.name for f in ModelName._meta.get_fields()]
```

If the field name or table name in the spec does not exactly match what the database shows, **halt and report** — do not assume, do not adapt silently, do not create a new field thinking the spec must be wrong.

### 1.2 Model definitions

Before extending or subclassing an existing model:

```bash
# Find the model file
grep -rn "class ModelName" --include="*.py"

# Confirm current field list
python manage.py shell
>>> from app.models import ModelName
>>> ModelName._meta.fields
```

Check the model file's current state on the working branch, not an assumed version.

### 1.3 Migration state

Before adding a migration:

```bash
python manage.py showmigrations
python manage.py makemigrations --dry-run
```

If the migration graph is not in the state the spec assumes (e.g., unapplied migrations from a prior branch, or migrations referencing deleted models), halt and report.

### 1.4 URL routes and endpoints

Before writing frontend code that calls an existing endpoint, or extending a backend router:

```bash
python manage.py show_urls          # if django-extensions installed
# Or inspect the urls.py files directly
grep -rn "path(" --include="urls.py"
```

Confirm the URL path, the view name, and the HTTP method.

### 1.5 Settings keys

Before referencing a settings value:

```bash
grep -n "SETTING_NAME" globalstrat/settings.py
grep -n "SETTING_NAME" globalstrat/settings/*.py
```

Confirm the key exists, what file it's in, and its current value. Environment-driven settings may have different values in dev/staging/prod — note this explicitly if it matters.

### 1.6 Qdrant collections

Before querying or writing to a Qdrant collection:

```python
from qdrant_client import QdrantClient
client = QdrantClient(host="192.168.50.186", port=6333)
client.get_collections()
client.get_collection("collection_name")
```

Confirm the collection exists and its vector configuration (size, distance metric) matches what the spec assumes.

### 1.7 Frontend component and route names

Before importing an existing React component or adding a route:

```bash
grep -rn "export default" frontend/src/components/ --include="*.jsx" --include="*.tsx"
grep -rn "path=" frontend/src/App.jsx frontend/src/routes/
```

Confirm component name, file location, and prop signature.

### 1.8 Model-to-table verification

Before any code or spec operation that references an existing Django model, confirm the model has a physical database table behind it. Django's model registry (`apps.get_models()`, `_meta.get_fields()`) reports every model declared in any `models.py`, including models declared with `managed: False` that were never physically created. Such **ghost models** are static-inspection-clean but runtime-broken: any query fails with `relation does not exist`.

```bash
# Enumerate Django-registered models
python manage.py shell <<'PY'
from django.apps import apps
for m in apps.get_models():
    print(f"{m._meta.label}\t{m._meta.db_table}\t{m._meta.managed}")
PY

# Enumerate physical tables
python manage.py dbshell -c "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"

# Compute the delta
# Ghost = registered in Django, absent from physical tables
```

A ghost model being the target of an operation — EXTEND, subclass, query, bulk import, migration dependency — is a MISMATCH halt condition per §3. Resolution belongs to the spec author (typically via a fork audit pass), not to Claude Code inline.

This rule was added after CC-01 Amendment A1 documented 40 ghost models in the forked GlobalStrat codebase. See `specs/reports/CC-01-deviations.md` D2 for full context.

### 1.9 Database client version alignment

Before any version-sensitive database client operation — `pg_dump`, `pg_restore`, major schema diff tools, point-in-time recovery utilities — verify client and server major versions match. Older clients against newer servers can produce silently incomplete or malformed output with no error at execution time; the failure only surfaces later at restore or replay.

```bash
# Server version
psql -h <host> -U <user> -d <db> -c "SELECT version();"

# Client version
pg_dump --version
pg_restore --version
```

If client major version is older than server major version, install a matching client before proceeding. Do not attempt the operation with mismatched versions, even if it appears to succeed — the output is not trustworthy. If the tool chain cannot be updated in the current environment, halt and escalate.

This rule was added after CC-01 Amendment A1 documented a pg_dump 14 vs. server 16 mismatch during CC-1 execution. See `specs/reports/CC-01-deviations.md` D3.

---

## 2. No Invented Names

If a spec instructs Claude Code to "update the X field on the Y model" and Y does not have field X, the correct action is:

1. Halt.
2. Report the mismatch with the actual field list.
3. Wait for clarification.

**Never** create a new field assuming the spec must have meant something close. **Never** rename an existing field to match what the spec said. **Never** add a new model because the expected one doesn't exist. These decisions belong to the human author, not to Claude Code.

---

## 3. Report Mismatches Explicitly

When a spec-described entity doesn't match the codebase, Claude Code reports in this format:

```
MISMATCH DETECTED
Spec reference: <what the spec said>
Actual state:   <what the codebase shows>
Location:       <file:line or db table>
Proposed action: <what Claude Code thinks should happen>
Halting for review.
```

Do not proceed past a mismatch without explicit instruction.

---

## 4. Migration Hygiene

- Every schema change has a migration generated via `python manage.py makemigrations`.
- Migrations are reviewed before `migrate` runs — read the generated file, confirm it does what you expect.
- Migrations must be reversible. If a migration requires irreversible data transformation, the spec must explicitly authorize it.
- No manual `ALTER TABLE` SQL outside the migration framework.
- After `migrate`, run `python manage.py check` and confirm it passes with zero issues before moving on.

---

## 5. Verification Checkpoints in Specs

Every CC spec includes verification checkpoints at phase boundaries. Typical checkpoints:

- **After model changes:** `python manage.py check` clean, `python manage.py showmigrations` matches expected state.
- **After API work:** hit every new/modified endpoint with curl or the Django test client; confirm response shape matches spec.
- **After frontend work:** explicit browser verification steps — click button, modal appears, submit form, data appears in table. Backend 200 responses are not sufficient evidence of frontend completion.
- **Before finalizing a CC bundle:** a short "what I verified" report listing each checkpoint and its result.

---

## 6. Git Hygiene

- CC work happens on a dedicated feature branch named `cc-NN-short-description`.
- Commits are atomic and descriptive (not "WIP" or "updates").
- No direct commits to `main` after the CC-1 initial commit.
- The CC bundle closes with a merge to `main` only after verification checkpoints pass.
- If a bundle is abandoned or reworked, the feature branch is kept (not force-deleted) so the history is preserved.

---

## 7. When in Doubt, Stop

The cost of a 10-minute clarification question is smaller than the cost of a 10-hour debugging session caused by a wrong assumption. If Claude Code is uncertain whether a field, table, endpoint, or behavior matches the spec, the correct action is to ask, not to guess.
