"""Read-only look into the disposable walkthrough database.

dbq.py enrollments        -- team, student, enrolment language (R43 evidence)
dbq.py sql "<select ...>" -- any read-only statement, printed as rows

Never the production database: it reads ./dbenv, the container make_db.sh made.
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


def rows(sql):
    with connection.cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        return cols, cur.fetchall()


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else 'enrollments'
    if what == 'enrollments':
        sql = ("SELECT t.id AS team_id, t.name AS team_name, e.enrollment_id, u.username, e.language, "
               "e.is_active FROM enrollment e JOIN users u ON u.user_id = e.user_id "
               "LEFT JOIN team t ON t.id = e.team_id "
               "ORDER BY t.id NULLS FIRST, e.enrollment_id")
    else:
        sql = sys.argv[2]
        low = sql.strip().lower()
        if not (low.startswith('select') or low.startswith('with')):
            raise SystemExit('read-only: select statements only')
    cols, data = rows(sql)
    print('\t'.join(cols))
    for r in data:
        print('\t'.join('' if v is None else str(v) for v in r))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
