"""Seed a game whose round 1 makes the R32 inactivity guard FIRE, with logins.

The guard has never fired in stored play, so the firing is constructed and then
ASSERTED, exactly as `handoff_readiness_v2/r34_inactivity_fixture.py` does: a
browser pass over a round where nothing fired would photograph the absence of
the notice and call it a pass.

Adds what the R34 fixture did not need: a course, a section, and real student
logins enrolled against each team — including the demoted one — because the
thing under test here is a SCREEN, reached by signing in as that team.
"""
import json
import os
import pathlib
import sys
from decimal import Decimal as D

import django

WT = pathlib.Path('/home/ubuntu/projects/globalstrat+/.claude/worktrees'
                  '/agent-ad31a78c64885fc47')
sys.path.insert(0, str(WT / 'backend'))
sys.path.insert(0, str(WT / 'handoff_readiness_v2'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
django.setup()

from django.apps import apps                                    # noqa: E402
from django.contrib.auth.models import User as DjangoUser       # noqa: E402
from django.core.management import call_command                 # noqa: E402
from django.db import connection                                # noqa: E402
from django.utils import timezone                               # noqa: E402

from core.models import (                                       # noqa: E402
    DecisionAuditEvent, Enrollment, Game, Round, Scenario, Team, User)
from core.models.course import Course, Section, SimulationInstance  # noqa: E402
from core.models.decisions import DecisionMarketing             # noqa: E402
from core.models.results_financials import (                    # noqa: E402
    LeaderboardEntry, RoundResultFinancials)
from core.engine import leaderboard as lb                       # noqa: E402
from core.utils.passwords import hash_password                  # noqa: E402

PASSWORD = 'r35-pass'
GAME_NAME = 'R35 Demotion Heat'
OUT = pathlib.Path(__file__).resolve().parent / 'fixture.json'


class SurfaceEmpty(RuntimeError):
    """A condition this fixture exists to create did not occur."""


def _create_legacy_tables():
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
    _create_legacy_tables()
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('r35admin', 'a@e.com', 'x')

    scenario = Scenario.objects.order_by('id').first()
    Scenario.objects.filter(pk=scenario.pk).update(num_rounds=3)
    scenario.refresh_from_db()

    call_command('initialize_game', scenario=scenario.id, teams=4,
                 name=GAME_NAME, verbosity=0)
    game = Game.objects.filter(name=GAME_NAME).order_by('-id').first()
    teams = list(Team.objects.filter(game=game).order_by('id'))

    hashed = hash_password(PASSWORD)
    instructor, _ = User.objects.get_or_create(
        username='r35_instructor',
        defaults={'role': 'instructor', 'email': 'inst@example.invalid'})
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hashed, role='instructor')

    course = Course.objects.create(
        course_code='R35', course_name='R35 Demotion Notice',
        instructor_id=instructor.user_id, academic_year='2026',
        semester='Verification', is_active=True, created_at=timezone.now())
    section = Section.objects.create(
        course=course, section_code='R35-01', section_name='R35 Section',
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
            username = f'r35_t{index}_m{member}'
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={'role': 'student',
                          'email': f'{username}@example.invalid'})
            User.objects.filter(pk=user.pk).update(
                password_hash=hashed, role='student', team_id=team.id)
            Enrollment.objects.update_or_create(
                user_id=user.user_id, section=section,
                defaults={'team_id': team.id, 'is_active': True,
                          'language': 'en', 'enrolled_at': timezone.now()})
            students.append({'username': username, 'team_id': team.id})

    round_obj = Round.objects.get(game=game, round_number=game.current_round)

    # The ordinary decision set for the field, reused verbatim from the v6
    # envelope fixture so the competing firms are realistic rather than a toy.
    from v6_envelope_fixture import seed_round
    seed_round(game, round_obj, scenario)

    # --- hold one firm out: present, locked, and selling nothing ------------
    idle = teams[-1]
    submission = None
    from core.models import DecisionSubmission
    submission = DecisionSubmission.objects.filter(
        team=idle, round=round_obj).first()
    if submission is None:
        raise SurfaceEmpty(f'No submission to strip for {idle.name}.')
    removed = DecisionMarketing.objects.filter(submission=submission).delete()
    # Carried state, set before resolution: this is what makes the demotion an
    # INVERSION rather than a firm that would have finished last anyway.
    idle.performance_index = D('95.00')
    idle.save(update_fields=['performance_index'])

    from core.engine.advance_round import close_round, process_round
    round_obj.deadline = timezone.now()
    round_obj.save(update_fields=['deadline'])
    close_round(game.id, reason='r35-demotion-fixture')
    process_round(game.id)

    # --- assert the guard fired and the inversion is real -------------------
    events = list(DecisionAuditEvent.objects.filter(
        round=round_obj, action=lb.ACTION_INACTIVITY_DEMOTION).order_by('id'))
    if not events:
        raise SurfaceEmpty(
            'The inactivity guard did not fire: no inactivity_rank_demotion '
            'event. A browser pass over this round would prove nothing.')
    entries = {e.team_id: e for e in LeaderboardEntry.objects.filter(
        game=game, round_number=round_obj.round_number)}
    idle_entry = entries.get(idle.id)
    if idle_entry is None:
        raise SurfaceEmpty(f'No leaderboard entry for {idle.name}.')

    # "Below every firm that COMPETED" excludes the other firms the guard also
    # demoted. A realistic seeded field can leave more than one firm below the
    # materiality floor, and comparing against a fellow demoted firm instead of
    # against the firms that actually sold would fail this fixture on exactly
    # the round it was built to produce.
    demoted_ids = {e.team_id for e in events}
    active = [e for tid, e in entries.items() if tid not in demoted_ids]
    if not active:
        raise SurfaceEmpty(
            'No firm competed at all, so there is no inversion to show.')
    worst_active = max(e.rank for e in active)
    if idle_entry.rank <= worst_active:
        raise SurfaceEmpty(
            f'{idle.name} ranked {idle_entry.rank}, not below every firm that '
            f'competed (worst competing rank {worst_active}).')

    idle_event = next((e for e in events if e.team_id == idle.id), None)
    if idle_event is None:
        raise SurfaceEmpty(f'No demotion receipt for {idle.name}.')
    if not idle_event.payload.get('outscored_a_firm_ranked_above'):
        raise SurfaceEmpty(
            'The demotion cost no places, so the screen would not show the '
            'inversion this pass exists to photograph.')

    revenues = {f.team_id: str(f.total_revenue)
                for f in RoundResultFinancials.objects.filter(
                    game=game, round_number=round_obj.round_number)}

    idle_student = next(s['username'] for s in students
                        if s['team_id'] == idle.id)
    # A firm that competed, for the cross-team refusal check.
    rival_team_id = active[0].team_id
    rival_student = next(s['username'] for s in students
                         if s['team_id'] == rival_team_id)

    # A firm the guard demoted that did NOT outscore anyone above it, if the
    # round produced one. It exercises the other wording variant -- the
    # sentence that must NOT claim a lost place -- on the same round.
    plain = next((e for e in events
                  if e.team_id != idle.id
                  and not e.payload.get('outscored_a_firm_ranked_above')), None)
    plain_team_id = plain.team_id if plain else None
    plain_student = (next(s['username'] for s in students
                          if s['team_id'] == plain_team_id)
                     if plain_team_id else None)

    fixture = {
        'game_id': game.id,
        'game_name': game.name,
        'round_number': round_obj.round_number,
        'password': PASSWORD,
        'demoted_team_id': idle.id,
        'demoted_team_name': idle.name,
        'demoted_student': idle_student,
        'rival_student': rival_student,
        'rival_team_id': rival_team_id,
        'plain_demoted_team_id': plain_team_id,
        'plain_demoted_student': plain_student,
        'plain_demotion_payload': plain.payload if plain else None,
        'all_demoted_teams': [e.team.name for e in events],
        'students': students,
        'marketing_rows_removed': removed[0],
        'demotion_payload': idle_event.payload,
        'ranks': {t.name: entries[t.id].rank for t in teams},
        'indexes': {t.name: str(entries[t.id].performance_index)
                    for t in teams},
        'revenues': {t.name: revenues.get(t.id) for t in teams},
        'manifest_schema_version':
            Round.objects.get(pk=round_obj.pk).resolution_manifest.schema_version,
    }
    OUT.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(fixture, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
