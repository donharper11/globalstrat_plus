# V2-048 controls — credential removal and detection

Runtime `b309de0`. Each revert restored immediately afterwards.

## Detection fires on the shape that hid the P0

`settings.py` returned to the defect's *shape* — an environment lookup with a
literal fallback — using a dummy value, never the real one:

```text
AssertionError: ['backend/globalstrat/settings.py:163 DB_PASSWORD has a literal default']
A credential must not have a literal fallback in tracked source.
Ran 4 tests ... FAILED (failures=1)
```

Restored: `Ran 4 tests ... OK`.

This is the case `no-committed-secrets` still passes over. Run against the same
tree, gitleaks reports `PASS 0 findings`.

## The application fails closed with no password

```text
django.core.exceptions.ImproperlyConfigured: DB_PASSWORD is not set. It has no
default: the previous default was a live credential committed to this
repository. Set it in the deployment secret configuration ...
```

## Removal is complete in the working tree, not in history

`git grep` for the literal returns nothing across tracked files. It remains in
**14 commits of history**, including this session's, and the repository has a
GitHub remote. Removing it from `HEAD` was never the thing that reduces the
exposure; rotation is.
