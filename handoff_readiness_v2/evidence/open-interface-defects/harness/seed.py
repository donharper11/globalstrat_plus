"""One active game with an open round 1, a student team, and an instructor.

Built for the three open interface defects:

  * V2-064 -- a student on a decision screen whose save can be refused while an
    exclusive operator lock is held. Needs an OPEN round and an unlocked team.
  * V2-105 -- an instructor dashboard with a named, ACTIVE game, so the Extend
    Deadline modal and the pause control are both reachable.
  * V2-080 -- the operator-actions panel on that same dashboard.

`initialize_game` already leaves the game `active` with round 1 `open`, so this
does not force either; it ASSERTS them instead, because a fixture that quietly
fails to create the condition under test would photograph a pass.

Reads ./dbenv, so it talks to the disposable container and never to the
production database.
"""
import json
import os
import pathlib
import sys

SCRATCH = pathlib.Path(__file__).resolve().parent
WT = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees'
                  '/agent-a32f4655be8cf1452')

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
from django.utils import timezone                                 # noqa: E402

from core.models import (                                         # noqa: E402
    DecisionSubmission, Enrollment, Game, Round, Scenario, Team, User)
from core.models.course import Course, Section, SimulationInstance  # noqa: E402
from core.utils.passwords import hash_password                    # noqa: E402

PASSWORD = 'defects-pass'
GAME_NAME = 'CRV2-13 Interface Defects Heat'
OUT = SCRATCH / 'fixture.json'


class SurfaceEmpty(RuntimeError):
    """A condition this fixture exists to create did not occur."""


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
        DjangoUser.objects.create_superuser('defectsadmin', 'a@e.invalid', 'x')

    scenario = Scenario.objects.order_by('id').first()
    call_command('initialize_game', scenario=scenario.id, teams=4,
                 name=GAME_NAME, verbosity=0)
    game = Game.objects.filter(name=GAME_NAME).order_by('-id').first()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    target = teams[0]

    hashed = hash_password(PASSWORD)
    instructor, _ = User.objects.get_or_create(
        username='defects_instructor',
        defaults={'role': 'instructor', 'email': 'i@example.invalid'})
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hashed, role='instructor')

    course = Course.objects.create(
        course_code='CRV213', course_name='Interface Defects Verification',
        instructor_id=instructor.user_id, academic_year='2026',
        semester='Verification', is_active=True, created_at=timezone.now())
    section = Section.objects.create(
        course=course, section_code='ID-01', section_name='Defects Section',
        max_teams=8, team_size_min=3, team_size_max=5, is_active=True,
        created_at=timezone.now())
    game.section_id = section.section_id
    game.save(update_fields=['section_id'])
    SimulationInstance.objects.create(
        section=section, game_id=game.id, current_round=game.current_round,
        total_rounds=scenario.num_rounds, status='active',
        started_at=timezone.now(), created_at=timezone.now())

    students = []
    for index, team in enumerate(teams, start=1):
        for member in range(1, 4):
            username = 'id_t%d_m%d' % (index, member)
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={'role': 'student',
                          'email': username + '@example.invalid'})
            User.objects.filter(pk=user.pk).update(
                password_hash=hashed, role='student', team_id=team.id)
            Enrollment.objects.update_or_create(
                user_id=user.user_id, section=section,
                defaults={'team_id': team.id, 'is_active': True,
                          'language': 'en', 'enrolled_at': timezone.now()})
            students.append({'username': username, 'team_id': team.id})

    round_one = Round.objects.get(game=game, round_number=1)
    DecisionSubmission.objects.get_or_create(
        team=target, round=round_one, defaults={'status': 'draft'})

    # --- assert the conditions this fixture exists to create ---------------
    game.refresh_from_db()
    if game.status != 'active':
        raise SurfaceEmpty(
            'Game is %r, not active; the instructor lifecycle controls '
            '(Extend Deadline, Pause) only render for an active game.'
            % game.status)
    round_one.refresh_from_db()
    if round_one.status != 'open':
        raise SurfaceEmpty(
            'Round 1 is %r, not open; a student write would be refused for '
            'the wrong reason and V2-064 would not be under test.'
            % round_one.status)
    submission = DecisionSubmission.objects.get(team=target, round=round_one)
    if submission.status == 'locked':
        raise SurfaceEmpty('The target team is locked; it could not edit.')

    fixture = {
        'game_id': game.id, 'game_name': game.name,
        'round_number': game.current_round,
        'password': PASSWORD,
        'team_id': target.id, 'team_name': target.name,
        'student': next(s['username'] for s in students
                        if s['team_id'] == target.id),
        'instructor': 'defects_instructor',
    }
    OUT.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(fixture, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
