# V2-052 reason controls

Both run at runtime `5873695`, each revert restored immediately afterwards.

## Control A — the canonical v2 file overwritten (V2-052 reproduced exactly)

`manifest_schema_v2.json` replaced with the `24687f0` state, which is what the
repository actually contained when the re-audit found this:

```text
AssertionError: 'aaa5e1f869ccc2b52bac118723f5aa9ed585bb3ef50e91cda44bc42a1ab1f9f6'
            != '41f1c510546f9c417dd01ac3f573a495345a7a2fc4ac18984ba6024d00169374'
Ran 4 tests ... FAILED (failures=1)
```

Restored: `Ran 4 tests ... OK`.

## Control B — a pinned historical definition edited

One `"scope"` value changed inside `manifest_schema_v2@61c43da.json`:

```text
AssertionError: ['v2 61c43da: manifest_schema_v2@61c43da.json changed'] is not false :
A schema definition that has already been in force was modified. Superseded
definitions are evidence, not working files:
v2 61c43da: manifest_schema_v2@61c43da.json changed
Ran 4 tests ... FAILED (failures=1)
```

Restored: `Ran 4 tests ... OK`.

### A note on how this control was nearly wrong

The first attempt at Control B edited the string `"scope": "game"` — with a
space. The on-disk inventory is minified, so nothing matched, the file was
unchanged, and the guard "passed". That pass looked like evidence and was not:
it demonstrated only that an unmodified file still matches its digest.

It was caught because the mutation step asserts that it changed something
before the test runs. Recorded because it is the same shape as V2-052 itself —
an artifact that appears to be doing its job while not being what it claims.
