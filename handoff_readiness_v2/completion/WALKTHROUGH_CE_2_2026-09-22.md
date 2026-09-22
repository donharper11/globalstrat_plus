# Second full walkthrough — Consumer Electronics 2026, on the repaired tree

**Branch:** `walkthrough-ce-2-2026-09-22`, cut from `crv2-release-integration`
(contains `b890976`, the merge of all four walkthrough repair branches, and
`completion/WALKTHROUGH_CE_2026-09-22.md`; both verified before anything ran).
**Date:** 2026-09-22. **Auditor role:** find defects; nothing in `backend/` or
`frontend/` was changed. The only edits are to the harness under
`handoff_readiness_v2/evidence/walkthrough-ce-2-2026-09-22/harness/`, listed in (a).
**Evidence root:** `handoff_readiness_v2/evidence/walkthrough-ce-2-2026-09-22/`
— `harness/` (every driver), `records/` (one JSON per driver run: steps, screens,
API calls, refusals, console, leak scans), `screenshots/` (JPEG), `exports/`.

> Sections: (a) stack and commands · (b) the W-CE verification table ·
> (c) the walkthrough log · (d) new defects · (e) what could not be driven ·
> (f) verdict.

---

## (a) The stack, and the exact commands

Disposable, on this host. **Never** the production database (192.168.50.38),
never `/etc/globalstrat-plus.env`; backups to a scratch directory inside the
evidence tree; every LLM endpoint pointed at an unreachable port, so Phase 2
uses the template fallback; `COMPETITION_REQUIRE_CLEAN_BUILD=false`. The
container and both ports are this pass's own
(`globalstrat-walkthrough-ce2-pg`, database `globalstrat_walk2`, ephemeral
host ports).

```
# from the worktree root
cd frontend/globalstrat-frontend && ln -s <main checkout>/frontend/globalstrat-frontend/node_modules node_modules
CI=false GENERATE_SOURCEMAP=false npx react-scripts build        # build/ for serve_app.py
H=handoff_readiness_v2/evidence/walkthrough-ce-2-2026-09-22/harness
$H/make_db.sh                    # postgres:16-alpine, random password, writes $H/dbenv (git-ignored)
python3 $H/seed.py               # migrate + legacy tables, load_scenario --preset electronics, superuser, ONE instructor
python3 $H/start_stack.py        # gunicorn (GLOBALSTRAT_ENV=production) + serve_app.py on one origin
```

`seed.py` again creates **nothing else**: the course, section, game, teams,
roster, passwords and schedule were all made from the console by the
instructor driver. The harness readiness window did not need lengthening on
this host: `make_db.sh`'s 40 × 1 s `pg_isready` loop and `start_stack.py`'s
180 s wait were enough on both runs (no `TEST_POSTGRES_READY_SECONDS` was set).

Drivers, in the order they were run:

| driver | what it does | run as |
|---|---|---|
| `instructor_setup.py` | Part 1 (EN): course → section → 8-team game → roster CSV → assignment incl. the refused 6th member → **team configuration with team 1's home market set by hand to Africa** → activate → schedule → deadline → extend → pause/resume → operator event → operator log → logins → team overview/drill → grading (rubric, calculate, **override**, 3 exports) → remaining panels | `python3 instructor_setup.py` |
| `instructor_bulk_reset.py` | Students & Logins → *Set all to student ID* | `python3 instructor_bulk_reset.py` |
| `instructor_tour.py` | read-only visit of every console tab and every confirmation/modal, in one language | `instructor_tour.py <lang> <tag>` |
| `instructor_round.py` | close → process → advance (or force / lifecycle modal), dashboards after, **operator-log wording and drill-down order checked** | `instructor_round.py <lang> <round> [console\|force\|lifecycle]` |
| `student_tour.py` | read-only visit of every student screen (+ results tabs after a round), **bell / in-game language switch / team-activity route checked** | `student_tour.py <lang> <team> <tag> [round]` |
| `student_play.py` | every decision screen, edits verified against the stored draft, lock | `student_play.py <lang> <team> <round> [probe\|plain]` |
| `lock_round.py` | **new**: completes the product-market rows a round's new product or new market leaves empty, then locks from the Summary; records the blockers and any lock refusal | `lock_round.py <lang> <team> <round>` |
| `verify_marketing_refusal.py` | **new**: drives W-CE-04's path — a row with promotion and no campaign focus — and reads the refusal | `verify_marketing_refusal.py <lang> <team> <round>` |
| `probe_dom.py` | **new**: read-only DOM probe (team-configuration table, the student decision screens, the marketing pane, the Round Results performance block) | `probe_dom.py <what> …` |
| `dbq.py` | **new**: read-only SQL against the disposable database (used for the enrolment-language evidence) | `dbq.py enrollments` |
| `check_round.py`, `apicall.py`, `hold_lock.py`, `mark_competition.py`, `instructor_endgame.py`, `leak_summary.py`, `records_summary.py` | as in the first walkthrough | — |

**Harness changes, all recorded (no runtime code was touched):**

1. `make_db.sh` — its own container and database name, so the first walkthrough's stack cannot be reused by accident.
2. `instructor_setup.py` — team 1's home market is now **chosen by hand (Africa)** in the Team Configuration table instead of only randomised (the W-CE-21 check needs a home market that is not the scenario default); the roster-upload outcome is read off the panel, not only from a toast/modal; the grading **override** control is driven; when a round-control action is refused for a stale round the driver reloads and repeats, so the record says whether the control works at all or only after a refresh.
3. `student_tour.py` — the bell check is inverted (its absence is the repair), the in-game language switch is exercised, the `team-activity` route is visited and the `…/changes/` call counted; any modal is dismissed before the top-bar checks.
4. `student_play.py` — the home-market tab is read from the strategy context instead of assuming tab 0 (this game's team 1 is Africa, the fourth tab); the loan, repayment and dividend boxes are typed key by key and read back; the R&D page is checked for the absence of *Invest next level*; the plant and partnership labels are captured; the W-CE-04 probe was moved out (see 5); products are retired through the row's *Retire product* button and the modal's *Retire End of Round*.
5. `verify_marketing_refusal.py`, `lock_round.py`, `probe_dom.py`, `dbq.py` — new, described above.
6. `instructor_tour.py` — the *Students & Logins* tab is found through `t('instructor.students_logins')`; the hard-coded English label no longer matches, which is itself W-CE-17 working.
7. `instructor_round.py` — the Operator Log rows and the drill-down modal are read and checked (W-CE-07, W-CE-20).

**Language** is set the product's own way (`localStorage.gs_language`, the key the switch writes) and, since the repair, is also recorded as the student's preference at sign-in. **No visual claim is made about Chinese glyphs**: this sandbox has no CJK font, so zh-CN screenshots show missing-glyph boxes; the standard is the rendered DOM text, recorded per screen.

**Leak scan** on every screen (`walk.scan`), same standard as the first pass.
Console errors and every API status ≥ 400 are captured per screen; the
harness's own aborted Google-Fonts requests (`net::ERR_FAILED`) are excluded
from the counts.

---

## (b) Verification of W-CE-01 … W-CE-26

_Filled in (c) and summarised here._

---

## (c) The walkthrough log

_See the records._

---

## (d) New defects

---

## (e) What could not be driven

---

## (f) Verdict
