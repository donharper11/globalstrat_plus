"""Seed ONLY what the console cannot create: schema, scenario, an instructor.

The walkthrough's point is that the instructor builds the course, section,
game, teams and roster through the console; nothing here pre-creates them.
Reads ./dbenv so it talks to the disposable container and never to the
production database.
"""
import json
import os
import pathlib
import sys

SCRATCH = pathlib.Path(__file__).resolve().parent
WT = SCRATCH.parents[3]            # .../agent-<id>  (harness -> evidence dir -> evidence -> handoff_readiness_v2 -> WT)

for line in (SCRATCH / 'dbenv').read_text().splitlines():
    if line.startswith('export '):
        key, _, value = line[len('export '):].partition('=')
        os.environ[key] = value

sys.path.insert(0, str(WT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')

import django                                                     # noqa: E402
django.setup()

from django.apps import apps                                      # noqa: E402
from django.contrib.auth.models import User as DjangoUser         # noqa: E402
from django.core.management import call_command                   # noqa: E402
from django.db import connection                                  # noqa: E402

from core.models import Scenario, User                            # noqa: E402
from core.utils.passwords import hash_password                    # noqa: E402

PASSWORD = 'walk-pass-2026'
OUT = SCRATCH / 'fixture.json'


def _legacy_tables():
    """`migrate` does not create tables for models marked managed=False."""
    existing = set(connection.introspection.table_names())
    unmanaged = [m for m in apps.get_models() if not m._meta.managed]
    for m in unmanaged:
        m._meta.managed = True
    with connection.schema_editor() as editor:
        for m in unmanaged:
            if m._meta.db_table not in existing:
                editor.create_model(m)
    for m in unmanaged:
        m._meta.managed = False


def main():
    call_command('migrate', verbosity=0, interactive=False)
    _legacy_tables()
    if not Scenario.objects.exists():
        call_command('load_scenario', preset='electronics', verbosity=0)
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('walkadmin', 'a@e.invalid', 'x')
    scenario = Scenario.objects.order_by('id').first()

    hashed = hash_password(PASSWORD)
    instructor, _ = User.objects.get_or_create(
        username='walk_instructor',
        defaults={'role': 'instructor', 'email': 'walk.i@example.invalid',
                  'display_name': 'Walkthrough Instructor'})
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hashed, role='instructor')

    fixture = {
        'scenario_id': scenario.id, 'scenario_name': scenario.name,
        'num_rounds': scenario.num_rounds,
        'password': PASSWORD, 'instructor': 'walk_instructor',
        'worktree': str(WT),
    }
    OUT.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(fixture, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
