"""Schema + scenario + an instructor for the WALK-CE3 whole-game proof.

Reads ./dbenv so it talks only to this pass's disposable container and never
to the production database at 192.168.50.38.
"""
import json
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

from django.apps import apps                                      # noqa: E402
from django.contrib.auth.models import User as DjangoUser         # noqa: E402
from django.core.management import call_command                   # noqa: E402
from django.db import connection                                  # noqa: E402

from core.models import Scenario, User                            # noqa: E402
from core.utils.passwords import hash_password                    # noqa: E402

PASSWORD = 'walk-pass-2026'
OUT = SCRATCH / 'fixture.json'
PRODUCTION_DB_HOST = '192.168.50.38'


def _legacy_tables():
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
    from django.conf import settings
    host = settings.DATABASES['default'].get('HOST')
    if host == PRODUCTION_DB_HOST or getattr(settings, 'IS_PRODUCTION', False):
        raise SystemExit(f'Refusing to seed: {host!r} is production.')
    call_command('migrate', verbosity=0, interactive=False)
    _legacy_tables()
    if not Scenario.objects.exists():
        call_command('load_scenario', preset='electronics', verbosity=0)
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('walkce3admin', 'a@e.invalid', 'x')
    scenario = Scenario.objects.order_by('id').first()

    hashed = hash_password(PASSWORD)
    instructor, _ = User.objects.get_or_create(
        username='walkce3_instructor',
        defaults={'role': 'instructor', 'email': 'walk.ce3@example.invalid',
                  'display_name': 'WALK-CE3 Instructor'})
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hashed, role='instructor')

    fixture = {'scenario_id': scenario.id, 'scenario_name': scenario.name,
               'num_rounds': scenario.num_rounds, 'password': PASSWORD,
               'instructor': 'walkce3_instructor', 'worktree': str(WT)}
    OUT.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(fixture, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
