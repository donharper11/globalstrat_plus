# Third full walkthrough — Consumer Electronics 2026, on the repaired tree

**Branch:** `walkthrough-ce-3-2026-09-23`, cut from `crv2-release-integration`
at `3c0ccf2`. The base was checked before anything ran: `29da1c8` — the merge
of both walkthrough-2 repair branches (`walk-ce2-round-blockers` and
`walk-ce2-language`) — is an ancestor of HEAD.
**Date:** 2026-09-23. **Auditor role:** find defects; repair nothing.
`backend/`, `frontend/` and `specs/` have **zero diff** on this branch. The
only edits are to the harness under
`handoff_readiness_v2/evidence/walkthrough-ce-3-2026-09-23/harness/`, every
one of them listed in (a).
**Evidence root:** `handoff_readiness_v2/evidence/walkthrough-ce-3-2026-09-23/`
— `harness/` (every driver), `records/` (one JSON per driver run: steps,
screens, API calls, refusals, console, leak scans), `screenshots/` (JPEG),
`exports/`, `runtime/` (stack logs, git-ignored).

> Sections: (a) the stack and the commands · (b) the verification table ·
> (c) the game, round by round, with the money reconciliation ·
> (d) new defects · (e) what could not be driven · (f) the verdict.

---

## (a) The stack, and the exact commands

Disposable, on this host, and this pass's own. **Never** the production
database at 192.168.50.38, never `/etc/globalstrat-plus.env`. Backups go to a
scratch directory **inside the evidence tree**; every LLM endpoint points at
an unreachable port, so Phase 2 narratives and the memo evaluation use the
template/heuristic fallback; `COMPETITION_REQUIRE_CLEAN_BUILD=false`. The
container, the database and both ports are this pass's own
(`globalstrat-walkthrough-ce3-pg`, database `globalstrat_walk3`, ephemeral
host ports).

```
# from the worktree root
cd frontend/globalstrat-frontend && ln -s <main checkout>/frontend/globalstrat-frontend/node_modules node_modules
CI=false GENERATE_SOURCEMAP=false npx react-scripts build       # build/ for serve_app.py
H=handoff_readiness_v2/evidence/walkthrough-ce-3-2026-09-23/harness
$H/make_db.sh                # postgres:16-alpine, random password, writes $H/dbenv (git-ignored)
python3 $H/seed.py           # migrate + legacy tables, load_scenario --preset electronics,
                             # a superuser and ONE instructor -- nothing else
python3 $H/start_stack.py    # gunicorn (GLOBALSTRAT_ENV=production) + serve_app.py on one origin
```

`seed.py` creates **nothing else**: the course, the section, the game, the
teams, the roster, every password and the schedule were all made from the
console by the instructor driver.

**The database readiness wait, as the brief asks.** The host disk is known to
stall, so `make_db.sh`'s `pg_isready` loop was lengthened from 40 × 1 s to
**300 × 1 s**, and `start_stack.py`'s readiness wait from 180 s to **900 s**.
On this run neither was needed: `make_db.sh` returned in **2.0 s**,
`seed.py` (migrate + scenario load) in **18.3 s**, and `start_stack.py` in
**2.7 s**. The longer windows are recorded because they are what the harness
now allows, not because they were consumed.

Drivers, in the order they were first run:

| driver | what it does | run as |
|---|---|---|
| `instructor_setup.py` | Part 1 (EN): course → section → 8-team game → roster CSV → assignment incl. the refused 6th member → team configuration with team 1's home market set by hand to Africa → activate → **schedule and deadline with no page refresh (W-CE2-10)** → extend → pause/resume → operator event → operator log → logins → team overview/drill → grading (rubric, calculate, override, 3 exports) → remaining panels | `python3 instructor_setup.py` |
| `instructor_bulk_reset.py` | Students & Logins → *Set all to student ID* | `python3 instructor_bulk_reset.py` |
| `instructor_tour.py` | read-only visit of every console tab and every confirmation/modal, in one language | `instructor_tour.py <lang> <tag>` |
| `instructor_round.py` | close → process → advance (or force / lifecycle modal), dashboards after, operator-log wording and drill-down order checked | `instructor_round.py <lang> <round> [console\|force\|lifecycle]` |
| `student_tour.py` | read-only visit of every student screen (+ results tabs after a round) | `student_tour.py <lang> <team> <tag> [round]` |
| `student_play.py` | every decision screen, edits verified against the stored draft, lock | `student_play.py <lang> <team> <round> [probe\|plain]` |
| `lock_round.py` | completes the product-market rows a new product or market leaves empty, then locks from the Summary | `lock_round.py <lang> <team> <round>` |
| `check_round.py` | results/statement/leaderboard cross-check **and the money reconciliation**, all 8 teams | `check_round.py <round>` |
| `verify_plant_collision.py` | **new** — W-CE2-01 at the decision boundary, both orders, both languages | `verify_plant_collision.py <team> <round>` |
| `verify_plant_after_acquisition.py` | **new** — W-CE2-01 at the round: a plant built where a COMPLETED acquisition already brought one | `verify_plant_after_acquisition.py <team> <round> [after]` |
| `verify_withdraw.py` | **new** — W-CE2-02: withdrawing a queued plant, partnership and acquisition from the real pages | `verify_withdraw.py <lang> <team> <round>` |
| `probe_ma_card.py` | **new** — read-only: what the M&A card offers, and what it says when it does not | `probe_ma_card.py <lang> <team> <round>` |
| `verify_deadline_affordability.py` | **new** — W-CE2-03, W-CE-23, W-CE2-09, W-CE-18b on one screen and then on the statement | `verify_deadline_affordability.py <team> <round> [after]` |
| `verify_results_language.py` | **new** — W-CE-14, W-CE2-06, W-CE2-07 read by two members of one team, one English, one Chinese | `verify_results_language.py <round>` |
| `probe_scorecard.py` | **new** — the Strategic Scorecard read en → zh → en, to show a read does not mutate a hashed field | `probe_scorecard.py <round> [team-id…]` |
| `verify_coach_language.py` | **new** — W-CE2-08: the console's own switch, then the alerts it produces | `verify_coach_language.py set` / `read <round>` |
| `dbq.py`, `apicall.py`, `hold_lock.py`, `mark_competition.py`, `instructor_endgame.py`, `leak_summary.py`, `records_summary.py`, `shrink_screenshots.py`, `prune_screenshots.py` | as in walkthrough 2 | — |

**Harness changes, all recorded (no runtime code was touched):**

1. `make_db.sh` — its own container (`globalstrat-walkthrough-ce3-pg`) and
   database (`globalstrat_walk3`), and the readiness loop lengthened to 300 s.
2. `start_stack.py` — readiness wait 180 s → 900 s; its own dev secret key.
3. `check_round.py` — three changes. It now covers **all eight teams** rather
   than the first three. It adds the **money reconciliation** the brief asks
   for, per team per round, in two forms (below). And a revenue-equality check
   that read `num(...) or -1` treated a legitimate **$0.00** revenue as a
   mismatch, so every team that did nothing failed a check it should have
   passed; fixed.
4. `student_play.py` — two assertions re-specified against what the repaired
   pages actually render. (i) The M&A assertion failed because since W-CE2-02
   an *Acquire* button exists **only** for a target that is available; the
   driver now reads the target list and its `locked_reasons` and asserts that
   an unavailable target says why. (ii) The plant assertion required the
   stored `decision_plant.capacity_units` to be non-zero, but that field is an
   *addition* to the market's authored `plant_capacity_units`, which is what
   `engine/strategy_effects.py:288` builds with; a row of 0 is correct, and the
   walkthrough-2 version of this check was mis-specified (it failed there too).
5. `verify_results_language.py` — and this is a correction of method worth
   naming: **`Accept-Language` does not decide what a reader is told.** R43 and
   the W-CE2-05 repair make the platform answer in the language of the
   *reader's own stored enrolment*, which the sign-in and the in-game switch
   write. A first version of this driver sent the header and drew a wrong
   conclusion from it. The driver now reads the same round twice, as two
   different members of the same team, each having stated their language
   through `PUT /api/user/preferences/` — the route the switch itself calls.
6. `verify_plant_collision.py`, `verify_plant_after_acquisition.py`,
   `verify_withdraw.py`, `probe_ma_card.py`,
   `verify_deadline_affordability.py`, `probe_scorecard.py`,
   `verify_coach_language.py`, `readers.json` — new, described above.

**The money reconciliation** is recorded per team per round in
`records/check-round<N>.json` under `reconciliation`, in two forms:

* **the identity the platform publishes** — `cash_opening + operating_cash_flow
  + investing_cash_flow + financing_cash_flow == cash_closing`;
* **the plain form the brief asks for** — `opening cash + revenue − charges =
  closing cash`, where *charges* are the expense lines the statement carries,
  with the remainder named by the statement's own cash-flow lines; and, below
  that, the sum **a player can actually do with a finger on the Financial
  Reports screen**, using only the lines that page prints.

**Language** is set the product's own way — the in-game switch, or the
`PUT /api/user/preferences/` route it calls. **No visual claim is made about
Chinese glyphs**: this sandbox has no CJK font, so zh-CN screenshots show
missing-glyph boxes; the standard is the rendered DOM text, recorded per
screen.

**Leak scan** on every screen (`walk.scan`), the CRV2-13 standard. Console
errors and every API status ≥ 400 are captured per screen; the harness's own
aborted Google-Fonts requests (`net::ERR_FAILED`) are excluded from the
counts.

---

## (b) Verification of the walkthrough-2 defects

*(filled in below as the run proceeds)*

---

## (c) The game, round by round

*(filled in below as the run proceeds)*

---

## (d) New defects

*(filled in below as the run proceeds)*

---

## (e) What could not be driven

*(filled in below as the run proceeds)*

---

## (f) Verdict

*(filled in below as the run proceeds)*
