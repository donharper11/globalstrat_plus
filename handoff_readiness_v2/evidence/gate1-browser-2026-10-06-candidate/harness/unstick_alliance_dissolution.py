"""Disclosed intervention: get the game past the alliance-dissolution crash.

    unstick_alliance_dissolution.py [--apply]

W-CE4: from the round in which a partnership's satisfaction falls far enough
for the partner to walk away, Phase 1 raises

    TypeError: ActiveModifier() got unexpected keyword arguments:
               'team', 'modifier_key', 'source', 'round_applied'

at `core/engine/alliance_engine.py:392`, `process_round` answers **HTTP 500**,
and the round stays `closed / processing_status FAILED`. The console shows the
operator nothing. It recurs on every attempt, because the alliance row is
never saved, so the game cannot go past that round at all.

Nothing on any screen can avoid it: the partnership was established rounds
earlier and the dissolution is the engine's own decision about the partner's
satisfaction. So the walkthrough cannot go on without touching the database.
This marks the four alliance states DISSOLVED -- which is what the engine was
trying to do when it crashed -- and terminates the partnership rows behind
them, so `process_alliances` skips them.

**It changes the game.** The four teams lose their partnership benefits from
this round on, and the dissolution penalty the engine meant to apply is not
applied. Every figure after round 8 is on a game that was nudged, and the
report says so. This is an auditor's intervention in a disposable database,
not a repair.
"""
import os
import pathlib
import sys

SCRATCH = pathlib.Path(__file__).resolve().parent
WT = SCRATCH.parents[3]
APPLY = '--apply' in sys.argv

for line in (SCRATCH / 'dbenv').read_text().splitlines():
    if line.startswith('export '):
        key, _, value = line[len('export '):].partition('=')
        os.environ[key] = value

sys.path.insert(0, str(WT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')

import django                                                     # noqa: E402
django.setup()

from django.db import connection                                  # noqa: E402


def rows(sql, args=None):
    with connection.cursor() as cur:
        cur.execute(sql, args or [])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def main():
    states = rows("select id, team_id, market_id, status, satisfaction, "
                  "dissolved_round from team_alliance_state "
                  "where status <> 'DISSOLVED' order by id")
    print('alliance states the engine would process:')
    for s in states:
        print('   ', s)
    parts = rows("select id, team_id, market_id, status from team_partnership "
                 "where status = 'active' order by id")
    print('active partnerships behind them:')
    for p in parts:
        print('   ', p)
    if not APPLY:
        print('\nnothing changed; pass --apply to make the change')
        return 0
    with connection.cursor() as cur:
        cur.execute("update team_alliance_state set status = 'DISSOLVED' "
                    "where status <> 'DISSOLVED'")
        n_states = cur.rowcount
        cur.execute("update team_partnership set status = 'terminated' "
                    "where status = 'active'")
        n_parts = cur.rowcount
    print('\n%d alliance state(s) marked DISSOLVED, %d partnership(s) '
          'terminated. DISCLOSED INTERVENTION: the four teams lose their '
          'partnership benefits from this round on, and the dissolution '
          'penalty the engine meant to apply is not applied.'
          % (n_states, n_parts))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
