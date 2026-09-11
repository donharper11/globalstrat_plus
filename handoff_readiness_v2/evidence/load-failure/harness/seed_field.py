"""Seed a field-sized cohort: complete firms and enough identities for 3x field.

The handoff fixes the field at 24 teams x 4 members = 96 authenticated
sessions, and the margin profile at 288. Sessions must use separate
identities, so 288 users are seeded -- twelve per team -- and the field profile
drives the first four of each team. That is not a classroom shape at twelve
members a team; it is the margin profile the handoff specifies, and the extra
identities exist to generate concurrency rather than to model a class.

Run inside `manage.py shell` against the disposable load database.

The teams come from ``initialize_game`` rather than extending a four-team
fixture with bare rows.  Phase 1 needs each firm to have the same platform,
product, market-presence and round-zero state a real game has; a team-only
row can exercise a budget endpoint but cannot validly resolve a round.
"""
TEAMS = 24
MEMBERS_PER_TEAM = 12
PASSWORD = 'loadtest-pass'


def run(teams=TEAMS, members_per_team=MEMBERS_PER_TEAM):
    """Seed the cohort.

    `teams=None` means "use exactly the teams `setup_test_game` instantiated"
    rather than extending the roster. The extension path creates bare Team rows
    with no home market and no starter state applied, which is adequate for
    driving HTTP write paths under load but is not a firm: it has no products,
    so it cannot price, produce, or resolve. Anything that resolves a round
    must seed with `teams=None`.
    """
    from django.contrib.auth.models import User as DjangoUser
    from django.core.management import call_command
    from django.utils import timezone

    from core.models import Enrollment, Game, Round, Scenario, Team, User
    from core.models.course import Course, Section, SimulationInstance
    from core.utils.passwords import hash_password

    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('loadadmin', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)

    import fixture_contract as FC
    chosen, _ = FC.scenario_supporting(
        ('sourcing', 'trade_finance', 'compliance', 'logistics'))
    if chosen is None:
        chosen = Scenario.objects.order_by('id').first()
    # Four is sufficient for the recovery walkthrough.  Field/margin calls
    # pass 24 explicitly.  Both paths create real firms, not placeholder rows.
    target = 4 if teams is None else teams
    game_name = f'CRV2 load fixture ({target} firms)'
    call_command('initialize_game', scenario=chosen.id, teams=target,
                 name=game_name, verbosity=0)
    game = Game.objects.get(name=game_name)
    roster = list(Team.objects.filter(game=game).order_by('id'))

    # A lifecycle action is scoped through Game.section_id -> Course.  The
    # load instructor must own this disposable course so process/ exercises
    # the actual authorization boundary instead of an unowned-fixture bypass.
    instructor, _ = User.objects.get_or_create(
        username='load_instructor',
        defaults={'role': 'instructor', 'password_hash': hash_password(PASSWORD),
                  'email': 'inst@example.invalid'})
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hash_password(PASSWORD), role='instructor')
    course = Course.objects.create(
        course_code=f'LOAD-{game.id}', course_name='CRV2 disposable load',
        instructor_id=instructor.user_id, academic_year='2026',
        semester='Load', is_active=True, created_at=timezone.now())
    section = Section.objects.create(
        course=course, section_code='LOAD', section_name='Load fixture',
        max_teams=target, team_size_min=1, team_size_max=MEMBERS_PER_TEAM,
        is_active=True, created_at=timezone.now())
    game.section_id = section.section_id
    game.save(update_fields=['section_id'])
    SimulationInstance.objects.create(
        section=section, game_id=game.id, current_round=game.current_round,
        total_rounds=game.scenario.num_rounds, status='active',
        started_at=timezone.now(), created_at=timezone.now())

    hashed = hash_password(PASSWORD)
    identities = []
    for team_index, team in enumerate(roster):
        for member in range(members_per_team):
            username = f'load_t{team_index + 1:02d}_m{member + 1:02d}'
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={'role': 'student', 'password_hash': hashed,
                          'email': f'{username}@example.invalid',
                          'team_id': team.id})
            User.objects.filter(pk=user.pk).update(
                password_hash=hashed, team_id=team.id, role='student')
            Enrollment.objects.update_or_create(
                user_id=user.user_id, section=section,
                defaults={'team_id': team.id, 'is_active': True,
                          'enrolled_at': timezone.now()})
            identities.append({'username': username, 'password': PASSWORD,
                               'team_id': team.id, 'user_id': user.user_id,
                               'member_index': member})

    rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
    return {
        'game_id': game.id,
        'section_id': section.section_id,
        'scenario': chosen.name,
        'round_number': rnd.round_number if rnd else None,
        'teams': len(roster),
        'identities': identities,
        'instructor': {'username': 'load_instructor', 'password': PASSWORD},
        'password': PASSWORD,
    }
