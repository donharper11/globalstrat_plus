# The automated gate on the merged candidate — 2026-10-07

The ten-round browser pass certified **`a0631e5d`**. Three repair branches then
landed on `crv2-release-integration`, two of which change product code and one
of which is tests only. Merging advances the candidate, so the automated half of
Gate 1 was re-run on the merged tip rather than inherited.

**Merged tip: `1b3aeb3a`.** All three merges were conflict-free.

| | result |
|---|---|
| Backend suite | **Ran 1,912 tests, OK, 475.458 s** — 1,873 at `a0631e5d` plus 39 added by the branches |
| Jest | **56 suites / 531 tests, all passing** — identical to the pre-merge baseline and to the 2026-10-05 Gate 1 evidence |
| Production build | **Compiles with warnings**, the project's normal state. Asset hash **`main.3ba3e3e1.js`** |
| `check-participant-strings` | **PASS**, 6,039 units, 0 findings |
| Scenario bilingual coverage | the competition scenario is down from **155** player-facing untranslated strings to **5**, and those five are the `interactions` authoring notes no screen renders, each named with its reason |

## What merged

| branch | product code? | what |
|---|---|---|
| `fix/decision-audit-request-id` | yes, one line | every decision audit row now carries a server-minted request id (V2-141) |
| `fix/team-language-ordering` | **no** | characterisation tests for which member decides a team's language, and why it is not the bug it first looked like (V2-147) |
| `fix/bilingual-coverage` | yes | 150 scenario translations, three views that served JSON blobs raw, two entirely-English panels, the fallback-feedback re-render, and a database column that was being printed on a chart (V2-145, V2-146) |

## The one thing this does not carry over, stated plainly

**The browser evidence belongs to `a0631e5d`, whose frontend built to
`main.81b42bcc.js`.** The merged tip builds to `main.3ba3e3e1.js`, because the
repairs change six frontend files. Nothing in the ten-round pass is invalidated
— it measured what it measured — but **the repaired screens have not been driven
in a browser.** They are covered by the backend suite, the catalogue check, Jest
and the build, and by tests that assert the serving path in both languages. What
is still owed is a targeted re-drive: a stack built from the merged tip, a
database seeded from the new scenario YAML, and one Chinese student through the
alliance, communications, financial-reports and tax screens. The measurement to
watch is the one this pass produced: on an English reader's 75 post-game screens
the leak scanner flagged **4**, on a Chinese reader's **74**.

`fix/extend-deadline-reason` (`d5f855b5`) is **not merged**: it is verified only
by a parse and the catalogue check, and it wants Jest, a build and a browser
re-drive of `probe_extend_closed_round.py` first.
