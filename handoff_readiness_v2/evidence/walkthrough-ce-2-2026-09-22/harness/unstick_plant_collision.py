"""Disclosed intervention: remove the plant decision that makes round 2 unprocessable.

unstick_plant_collision.py <submission_id>

W-CE2-01: a team that builds a plant in a market AND completes an acquisition
whose target includes a plant in the SAME market has two `team_plant` rows
created for (team, market, round), and the competition manifest snapshot
refuses the round with

    SnapshotError: Natural key ('team_id','market_id','construction_started_round')
    is not unique in section "team_plant"

so post-round processing answers 500 and the round stays `closed /
processing_status FAILED`. Nothing on any screen can undo either decision --
the Build Plant button only appends -- so the walkthrough cannot go on without
touching the database. This script deletes the one `decision_plant` row (the
acquisition is left alone), prints what it removed, and is disclosed in the
record. It is an auditor's intervention in a disposable database, not a repair.
"""
import os
import pathlib
import sys

SCRATCH = pathlib.Path(__file__).resolve().parent
WT = SCRATCH.parents[3]

for line in (SCRATCH / 'dbenv').read_text().splitlines():
    if line.startswith('export '):
        key, _, value = line[len('export '):].partition('=')
        os.environ[key] = value

sys.path.insert(0, str(WT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')

import django                                                     # noqa: E402
django.setup()

from django.db import connection                                  # noqa: E402


def main():
    submission_id = int(sys.argv[1])
    with connection.cursor() as cur:
        cur.execute("SELECT id, action, market_id FROM decision_plant "
                    "WHERE submission_id = %s", [submission_id])
        rows = cur.fetchall()
        print('plant decisions on submission %d: %s' % (submission_id, rows))
        cur.execute("DELETE FROM decision_plant WHERE submission_id = %s", [submission_id])
        print('deleted %d row(s)' % cur.rowcount)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
