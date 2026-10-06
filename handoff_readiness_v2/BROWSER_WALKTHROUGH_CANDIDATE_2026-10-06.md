# Gate 1 browser acceptance on the candidate — interim, rounds 1–3

**Candidate:** `a0631e5d` on `crv2-release-integration`, clean tree.
**Stack:** disposable PostgreSQL in Docker, the candidate's own built frontend
(asset hashes byte-identical to the Gate 1 build), gunicorn with
`GLOBALSTRAT_ENV=production`, every LLM URL pointed at an unreachable port so
Phase 2 uses the template fallback. Nothing touched production.

**Evidence:** `evidence/gate1-browser-2026-10-06-candidate/` — 53 record
files, 595 screens, 4,712 API calls. `runtime/`, the generated database
credential and screenshots are excluded by the harness's own `.gitignore`;
the generated password was checked for and appears nowhere in what is
committed.

**Status: INTERIM. Rounds 1–3 of 10 ran. This is not a completed Gate 1
browser pass and not the Gate 4 rehearsal** — Gate 4 is on the serving host
and is still outstanding.

## What round 1 establishes

Round 1 is the only round in this run whose deadline had not already passed
(see the finding below), so it is the only round whose numbers mean what the
harness intended.

* **Four teams played every decision screen, one of them (team 3) entirely in
  Simplified Chinese: 27 / 24 / 27 / 27 steps passed, 0 failed.**
* Six teams locked; teams 7 and 8 never submitted, which is the absentee path
  the deadline has to handle.
* The equity preflight found nothing to resize.
* **The instructor resolved the round from the console on the first attempt,
  with no operator intervention and no database edit** — 9 passed / 0 failed,
  13 screens, 0 leaks, 0 refused calls. Round closed, processed,
  `FULLY_COMPLETE`, Phase 1 in 4.6 s, advance offered, round 2 opened, and the
  operator log stated before → after in words.
* **Every financial identity held at $0.00 residual for all eight teams:**
  opening cash equals the previous round's closing cash; opening + OCF + ICF +
  FCF equals closing; gross profit equals revenue − COGS; operating income
  equals gross profit − the opex lines shown; the printed income statement
  adds up with $0.00 in no served field; and net income equals operating
  income − interest − tax.

That is the W-CE4 auditor's verdict reversed for round 1: *"a full game cannot
be played start to finish with no intervention"* was true of walkthrough 4,
where four of ten rounds refused to score. Round 1 here needed nothing. Rounds
2 and 3 also resolved on the first attempt, round 2 with the **instructor
console in zh-CN** — the instructor Chinese path the recovery checkpoint named
as an open gap.

## Finding — the fixture opens rounds whose deadline has already passed

**This is a harness/fixture defect and the product behaved correctly, but it
invalidates the rounds-2+ measurements in this run.**

| round | opened at | deadline | past when opened |
|---|---|---|---|
| 1 | 2026-10-06 11:56 | 2026-10-07 11:56 | no |
| 2 | 2026-10-06 14:04 | **2026-09-26** 18:00 | **yes** |
| 3 | 2026-10-06 14:55 | **2026-09-28** 18:00 | **yes** |
| 4 | 2026-10-06 15:16 | **2026-09-30** 18:00 | **yes** |

The seeded schedule carries fixed late-September dates. Every round after the
first therefore opened already closed, and the product refused every write
with the correct sentence — *"Your last change was not saved. The deadline for
this round has passed. Your decisions are locked."* — in both languages.

That accounts for essentially all of the 183 failed steps in rounds 2–3:
budget allocation not saved, loan not stored, product not created, market
entry/partnership/compliance not saved, lock refused for *"Set the budget
allocation before locking"*. **None of these is evidence of a product defect**
and none should be read as one. Round 1, with a future deadline, failed
nothing.

**What the next run must do:** set each round's deadline relative to the
moment it opens — through the console's own Extend Deadline control, so the
path is exercised rather than bypassed — before the teams play. Until that is
done, rounds 2+ measure the deadline refusal and nothing else.

## Bilingual result, adjudicated rather than counted

The leak scanner reports 166 screens with leaks, 34–36 of them per Chinese
driver. **Every distinct English run it flagged on a Chinese screen is a
proper noun**, and the complete list across all 53 records is: `Prism Tech`
(127), `Jonas Berg` (123), `Nova Prism` (18), `Walkthrough Instructor` (14),
`Aurora Devices` (7), and one hit each for the other six company names, plus
`Board of Directors` (3). These are the student's own name, their company, a
product name, the instructor's display name, competitor company names and a
scenario institution — none of them translatable UI.

**No raw i18n key, no storage field name, no `undefined` / `NaN` /
`[object Object]`, and no exception text appeared on any screen in either
language.** The 30 `None` hits are the English word in prose — *"Tax benefit:
None"*, *"IP Exposure: None"* — and the decisive check is that `None` was
never flagged on a Chinese screen, so it is localized copy and not a
serialized Python sentinel.

The scanner should be given the roster and team names as an allow-list so a
real leak is not buried under ~290 proper-noun hits. Not done in this run, so
that the adjudication above rests on the raw output.

## Two harness defects repaired in `instructor_setup.py`

* **The bulk password assertion read a transient toast** and so failed twice
  on a control that had worked — once in the 2026-10-06 rerun and again here.
  Independently verified on the candidate: the database shows 27 of 27 student
  accounts carrying a PBKDF2 hash and **0 without a password**, and the
  product's own `GET /api/instructor/student-accounts/` returns 27 rows with
  `needs_password` false on every one. The step now asserts that route's
  answer instead of the toast.
* **`GET /api/grades/?instance_id=` is not a route.** The harness guessed the
  URL, took a 404 from Django's own handler on every run, left
  `grades_after_override` null, and put a harness mistake in the record's
  refusal list. It now reads the registered `team-grades` route. The frontend
  never called the bad URL; no product defect.

Console errors are 10 × `ERR_FAILED` per driver from the font CDN this sandbox
cannot reach, plus the one 404 above. No product console error was seen.

## Outstanding for this gate

* Re-run rounds 2–10 with deadlines set relative to the open.
* Post-resolution results and leaderboard screens in zh-CN for a *student*
  (round 2's Chinese coverage is the instructor console).
* A dispute lookup through the supported path.
* Gate 4: the same thing on the serving host, isolated, with its own
  instructor account per the V2-140 checklist line.
