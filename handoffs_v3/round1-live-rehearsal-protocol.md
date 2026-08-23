# GlobalStrat+ Round 1 Live-Rehearsal Protocol

Date: 2026-08-23  
Target: `https://globalstrat.camdani.com`  
Backend host: `ubuntu@192.168.50.5`  
Repository: `/home/ubuntu/projects/globalstrat+`

## Purpose and operating rule

This runbook covers a controlled one-to-four-round rehearsal. Use a newly created game; never reuse or reset a class game. Stop at every pause point. Only the named rehearsal operator may close, process, advance, reset, archive, or delete the game.

Round processing and round advancement are separate actions. Always inspect results after processing and before advancing.

## Roles, accounts, and timing

- Operator/instructor: `instructor`; set or confirm its password out of band.
- Synthetic students: `student1` through `student4`; reset passwords before the rehearsal and share them privately.
- Observer: watches service health, API failures, browser consoles, locks, processing duration, and result consistency; does not operate controls.
- Setup and account check: 20 minutes.
- Round 1 decisions: 35 minutes; lock grace: 10 minutes; processing and inspection: 15 minutes.
- Rounds 2-4, if authorized after each pause: 25 minutes decisions; 10 minutes lock grace; 15 minutes processing and inspection per round.
- Debrief: 20 minutes. Reserve 3.5 hours for four rounds including pauses.

## Preflight and game seeding

Run from the backend VM:

```bash
cd /home/ubuntu/projects/globalstrat+/backend
git status --short --branch
python3 manage.py check
python3 manage.py test core.tests.test_cc18_compliance.CC18ComplianceTest --verbosity=2 --keepdb
systemctl is-active globalstrat-backend globalstrat-frpc
curl -I https://globalstrat.camdani.com
python3 manage.py setup_test_game
```

Do not pass `--flush`. Record the emitted game ID, team IDs, profile assignments, and student-to-team mapping. Confirm all accounts resolve to that game by logging in once. `setup_test_game` updates the shared test users and enrollments, so do not run it during an unrelated test or class session.

For Round 1, every team selling in North America must save a North America customs-classification decision before locking. Confirm it in the UI under Trade Finance/Customs and with:

```bash
cd /home/ubuntu/projects/globalstrat+/backend
python3 manage.py shell <<'PY'
from core.models import Team, Round, CustomsClassificationDecision
GAME_ID = 19  # replace with the recorded rehearsal game
rnd = Round.objects.get(game_id=GAME_ID, round_number=1)
for team in Team.objects.filter(game_id=GAME_ID).order_by('id'):
    rows = CustomsClassificationDecision.objects.filter(team=team, round=rnd)
    print(team.id, team.name, list(rows.values_list('destination_market__code', 'classification')))
PY
```

Pause point A — go/no-go before student play:

- Correct game ID and four team assignments are recorded.
- Round 1 is `open`; later rounds are `pending`.
- Frontend is HTTP 200; backend and FRP are active.
- Each account can log in and sees `R1 of 10`.
- Operator confirms no real class game is selected.

## Student workflow and lock gate

Each synthetic student completes Dashboard → R&D → Product Portfolio → Marketing Mix → Corporate Strategy → Finance → Trade Finance/Customs → Review & Submit. Require positive production and retail price for each marketed product. Reload each edited page once to prove persistence.

Before lock, the observer records the four team names, marketing product/market pairs, budget totals, and customs rows. Lock only through Review & Submit. Verify server state:

```bash
python3 manage.py shell <<'PY'
from core.models import Team, Round, DecisionSubmission
GAME_ID = 19
rnd = Round.objects.get(game_id=GAME_ID, round_number=1)
for team in Team.objects.filter(game_id=GAME_ID).order_by('id'):
    sub = DecisionSubmission.objects.filter(team=team, round=rnd).first()
    print(team.id, team.name, getattr(sub, 'status', None), getattr(sub, 'locked_at', None))
PY
```

Pause point B — do not process unless all four show `locked`, there are no validation errors, and the instructor page shows `4 of 4 teams have locked decisions`.

## Instructor API commands

Prefer the Game Control UI. The following API sequence is the operator fallback. Obtain the token without printing it:

```bash
read -s INSTRUCTOR_PASSWORD
export GSP_TOKEN="$(curl -fsS https://globalstrat.camdani.com/api/auth/login/ \
  -H 'Content-Type: application/json' \
  --data "{\"username\":\"instructor\",\"password\":\"${INSTRUCTOR_PASSWORD}\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access"])')"
export GSP_GAME_ID=19
curl -fsS "https://globalstrat.camdani.com/api/games/${GSP_GAME_ID}/round-control/" \
  -H "Authorization: Bearer ${GSP_TOKEN}"
```

If all teams are locked, close and process separately:

```bash
curl -fsS -X POST "https://globalstrat.camdani.com/api/games/${GSP_GAME_ID}/round-control/close/" \
  -H "Authorization: Bearer ${GSP_TOKEN}" -H 'Content-Type: application/json' --data '{}'
curl -fsS -X POST "https://globalstrat.camdani.com/api/games/${GSP_GAME_ID}/round-control/process/" \
  -H "Authorization: Bearer ${GSP_TOKEN}" -H 'Content-Type: application/json' --data '{}'
```

`{"force":true}` is reserved for an operator-approved exception; it closes an open round before processing. Never use it merely to bypass missing locks.

## Post-processing safety gate

Inspect the current round before advancing:

```bash
python3 manage.py shell <<'PY'
from core.models import (Team, Round, RoundResultProductMarket,
    RoundResultFinancials, RoundResultPerformanceIndex, LeaderboardEntry)
GAME_ID = 19
rnd = Round.objects.get(game_id=GAME_ID, round_number=1)
print('round', rnd.status, rnd.processing_status, 'game current', rnd.game.current_round)
for entry in LeaderboardEntry.objects.filter(game_id=GAME_ID, round_number=1).select_related('team').order_by('rank'):
    team = entry.team
    fin = RoundResultFinancials.objects.get(team=team, round_number=1)
    pi = RoundResultPerformanceIndex.objects.get(team=team, round_number=1)
    rows = RoundResultProductMarket.objects.filter(team=team, round_number=1).count()
    print(entry.rank, team.name, 'rows', rows, 'revenue', fin.total_revenue,
          'net_income', fin.net_income, 'PI', pi.index_value)
PY
```

Pause point C — results review:

- Round is `processed` / results available and game remains on the processed round.
- Four leaderboard entries and four PI/financial rows exist.
- Every actively marketed team has product-market rows and revenue consistent with units sold.
- A zero-revenue or frozen team cannot rank above materially successful teams without a documented component-level reason.
- All student dashboards, leaderboard pages, and financial reports render `RESULTS AVAILABLE` with no spinner, exception, or 5xx.
- Instructor Game Control shows the game ID, latest processed round, processed status, and 4/4 locks.

Only after instructor and observer sign this gate may the operator advance:

```bash
curl -fsS -X POST "https://globalstrat.camdani.com/api/games/${GSP_GAME_ID}/round-control/advance/" \
  -H "Authorization: Bearer ${GSP_TOKEN}" -H 'Content-Type: application/json' --data '{}'
```

Repeat the student workflow and pause points for rounds 2-4. Stop after any failed gate; do not advance to make a failure disappear.

## Monitoring checklist

Keep these open during each lock/process window:

```bash
systemctl --no-pager --full status globalstrat-backend globalstrat-frpc
journalctl -u globalstrat-backend -f
curl -I https://globalstrat.camdani.com
```

Monitor:

- Browser console: no unhandled exceptions; record URL and timestamp for any error.
- Network: no API 5xx; record response body for any 4xx/5xx.
- Round control: lock count, status, processing status, phase-1 duration, and current round.
- Database: result counts, compliance events/freezes, product-market rows, revenue, net income, and PI.
- UX: no shell-only page, indefinite loading indicator, wrong-round banner, or hidden results.

## Incident, rollback, and recovery

1. Stop student activity and capture the game ID, round, timestamp, screenshots, failing API response, and backend logs.
2. If the round is closed but not processed, reopen it with a future deadline:

```bash
curl -fsS -X POST "https://globalstrat.camdani.com/api/games/${GSP_GAME_ID}/round-control/reopen/" \
  -H "Authorization: Bearer ${GSP_TOKEN}" -H 'Content-Type: application/json' \
  --data '{"deadline":"2026-08-23T12:00:00+08:00"}'
```

3. A processed round cannot be reopened. Do not manually delete result rows and do not use reset as a data rollback: the reset endpoint changes lifecycle state but does not remove processed results. Preserve the failed game as evidence, archive it if necessary, create a new rehearsal game without `--flush`, and replay from the last signed pause point.
4. If service recovery is needed, the platform owner may restart only the affected unit after logs are captured:

```bash
sudo systemctl restart globalstrat-backend
sudo systemctl restart globalstrat-frpc
systemctl is-active globalstrat-backend globalstrat-frpc
```

5. Never run `setup_test_game --flush`, delete a game, modify production rows in a shell, or restart PostgreSQL during a rehearsal without explicit platform-owner approval and a verified backup.

## Rehearsal record and approval

Record participant names, game ID, team mapping, timestamps for each pause point, processing durations, result table, errors, recovery actions, and the final go/no-go decision. Platform-owner approval remains a manual acceptance item; this document is operationally ready but is not self-approving.
