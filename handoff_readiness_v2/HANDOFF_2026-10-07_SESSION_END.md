# Handoff — 2026-10-07

Picks up from `HANDOFF_2026-10-06_SESSION_END.md` and
`RECOVERY_CHECKPOINT_2026-10-06.md`. Read
`BROWSER_ACCEPTANCE_TENROUND_2026-10-06.md` for what the pass established and
`MERGED_CANDIDATE_GATE_2026-10-07.md` for the state of the merged candidate.

## What happened

**Gate 1's browser half is done.** A full ten-round bilingual game was played
and finished from the console with no operator reopening a round and no
database edit — nine rounds first-attempt on their chosen path, round 10 ended
with *Finish game*, zero processing refusals, zero reopens, 84 of 84
cross-checks in every round and a worst financial-identity residual of $0.00
across the whole game.

**Eight findings, V2-141 through V2-148.** Six are repaired, one was corrected
from a bug into an existing owner question, and one class is measured but
deliberately not inventoried. The register has each with its cause and its
repair.

## The candidate

| | |
|---|---|
| Certified by the browser pass | **`a0631e5d`** — frontend `main.81b42bcc.js` |
| Merged tip after the repairs | **`ed6d8776`** — frontend `main.3ba3e3e1.js` |
| Production serves | **`f62fc720`** from `globalstrat-plus-candidate-f62f` — **cut over 2026-10-07 05:48 UTC**, backend only |

**The backend cutover is done and verified**; see
`evidence/cutover-2026-10-07/README.md`, which also records the systemd trap that
made the first attempt look successful while it was not. **The frontend was not
deployed**, so the ECS still serves the pre-repair bundle and the bilingual
repairs are not yet in front of a student.

The automated half of Gate 1 was re-run on the merged tip: backend **1,912
tests OK**, Jest **56 suites / 531 tests**, production build compiles with
warnings, `check-participant-strings` PASS at 6,039 units.

## The one claim that does not transfer

**The browser evidence belongs to `a0631e5d`.** The repairs change frontend
files, so the merged tip builds to a different asset hash and **the repaired
screens have not been driven in a browser.** They are covered by the suites,
the catalogue check, and tests that assert the serving path in both languages,
and the government-prose repair was additionally verified against the 166
`GovernmentAction` rows the pass itself wrote — all six shapes render with no
Latin words left and the market code `AFR` resolves to 非洲.

**What is owed is one targeted re-drive**: a stack built from the merged tip, a
database seeded from the new scenario YAML, and one Chinese student through the
alliance, communications, financial-reports, tax and government-relations
screens. The measurement to watch already exists from this pass: on an English
reader's 75 post-game screens the leak scanner flagged **4**; on a Chinese
reader's 75 it flagged **74**. That number is the test of whether V2-145 to
V2-148 actually landed.

## Where the gates stand

| gate | state |
|---|---|
| 1 — automated | **Closed** at the candidate and re-run green on the merged tip |
| 1 — browser | **Closed** for `a0631e5d` by this pass; the re-drive above is owed for the merged tip |
| 2 | **Re-run on `f62f` after the cutover and clean**: release identity verified, no unapplied migrations, all append-only guards enabled, chain ok at 1,179 entries with the anchor matching. Zero manifests were written during the eight-minute window when code and revision disagreed |
| 3 | Field-size combined load **closed**; 3× is recorded inadmissible and needs a generator host separate from the stack. Remaining drills and alert delivery open. New data: PBKDF2 costs **0.378 s per authentication** on this host, so a 96-student sign-in storm is ≈36 s of CPU |
| 4 | **Not started.** The isolated rehearsal on the serving deployment, with its own instructor account per the V2-140 checklist line |
| 5 | Not started |

## Open, and whose

**The owner's, and only these:**
* **whether to deploy the frontend to the ECS** (`47.86.57.36`) — the backend is
  cut over, so until this happens the two halves are from different commits;
* Gate 4 on the serving deployment;
* the VM sudo credential rotation — **parked until after MVP by decision, 2026-10-07**;
* whether to take `fix/extend-deadline-reason` (`d5f855b5`), which is **not
  merged**: it adds the reason box the closed-round extend refuses for lack of,
  and it is verified only by a parse and the catalogue check. It wants Jest, a
  build and a re-drive of `probe_extend_closed_round.py`;
* **what language a team-wide artefact uses when a team's members differ.**
  Today's answer is the first-enrolled member's language, now pinned by tests.
  It does not block MVP.

**Mine, and not yet done:**
* the one targeted bilingual re-drive described above;
* the wider class behind V2-148: **204 English prose literals across
  `backend/core/engine`**, most of which are LLM prompts that are correctly
  English. Separating displayed text from model input, module by module, is the
  work. `events.py`, `alliance_engine.py` and the `reasoning_*` modules are the
  files the walkthrough implicates directly;
* the two other shipped scenarios, held to a stated ceiling of 135 untranslated
  strings each rather than completed — they are not what the competition runs;
* the dashboard's eight tabs, which the new every-tab sweep cannot open in
  either language. Not a modal; a tour-level selector problem on one page.

**Blocked on a second machine:** the 3× load profile.

## Live state on this host, as left

* **The ten-round walkthrough stack is still up** and is *not* production:
  a disposable PostgreSQL container `globalstrat-gate1-browser-20261006-tenround-pg`
  plus a gunicorn and a static server whose pids are in
  `evidence/gate1-browser-2026-10-06-tenround/harness/runtime/stack.pids`. The
  game is played out, finished and archived. Tear it down with those pids and
  `docker rm -f` when the re-drive no longer needs it — **it is the only stack
  whose database holds the pass's rows**, which is what the government-prose
  repair was verified against.
* Disposable Postgres containers from the test runs: `gsp-merged-pg`. Removable.
* Worktrees added this session: `globalstrat-plus-fix-request-id`,
  `-fix-team-language`, `-bilingual`, `-extend-reason`, `-govt-prose`. The first
  three are merged and can go; the last two carry unmerged branches.
* Production is untouched: `globalstrat-backend` and `globalstrat-narratives`
  active from the `f0cf` worktree, the deadline timer firing minutely and
  reporting no rounds due.

## If you read one thing from the pass

Round 9. The equity pre-flight found a team holding a raise $100,000 above the
shortfall it finances — the W-CE4-02 shape that used to make a fully-locked
round refuse to score with **nothing shown on the console**. This time the team
could not lock, and its own Decision Summary said why, with both figures. One
resize, lock, processed first attempt. That is the difference between the
previous walkthrough's verdict and this one.
