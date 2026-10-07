# The automated gate on the merged candidate — 2026-10-07

The ten-round browser pass certified **`a0631e5d`**. Three repair branches then
landed on `crv2-release-integration`, two of which change product code and one
of which is tests only. Merging advances the candidate, so the automated half of
Gate 1 was re-run on the merged tip rather than inherited.

**Merged tip: `8d5a0c1a`.** All four merges were conflict-free. The first
three were measured at `1b3aeb3a`; the fourth landed after the ten-round pass's
last finding was repaired, and its own branch was based on `1b3aeb3a`, so the
tree the suite ran on is the tree the merge produced.

| | result |
|---|---|
| Backend suite | **Ran 1,936 tests, OK, 480.826 s** at the final tip — 1,873 at `a0631e5d` plus 63 added by the four branches. The three-branch tip measured 1,912 |
| Jest | **56 suites / 531 tests, all passing** — identical to the pre-merge baseline and to the 2026-10-05 Gate 1 evidence |
| Production build | **Compiles with warnings**, the project's normal state. Asset hash **`main.3ba3e3e1.js`** |
| `check-participant-strings` | **PASS**, 6,048 units, 0 findings |
| Scenario bilingual coverage | the competition scenario is down from **155** player-facing untranslated strings to **5**, and those five are the `interactions` authoring notes no screen renders, each named with its reason |

## What merged

| branch | product code? | what |
|---|---|---|
| `fix/government-narrative-language` | yes | government-agent prose, composed at resolution and stored, rebuilt for the reader at read time so nothing hashed moves (V2-148) |
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
