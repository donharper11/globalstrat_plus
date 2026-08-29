"""Seed a field-sized cohort: 24 teams, and enough identities for 3x field.

The handoff fixes the field at 24 teams x 4 members = 96 authenticated
sessions, and the margin profile at 288. Sessions must use separate
identities, so 288 users are seeded -- twelve per team -- and the field profile
drives the first four of each team. That is not a classroom shape at twelve
members a team; it is the margin profile the handoff specifies, and the extra
identities exist to generate concurrency rather than to model a class.

Run inside `manage.py shell` against the disposable load database.
"""
TEAMS = 24
MEMBERS_PER_TEAM = 12
PASSWORD = 'loadtest-pass'


def run():
    from django.contrib.auth.models import User as DjangoUser
    from django.core.management import call_command
    from django.utils import timezone

    from core.models import Enrollment, Game, Round, Scenario, Team, User
    from core.models.course import Section
    from core.models.scenario import FirmStarterProfile
    from core.utils.passwords import hash_password

    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('loadadmin', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)

    import fixture_contract as FC
    chosen, _ = FC.scenario_supporting(
        ('sourcing', 'trade_finance', 'compliance', 'logistics'))
    if chosen is None:
        chosen = Scenario.objects.order_by('id').first()
    call_command('setup_test_game', '--scenario', str(chosen.id), verbosity=0)

    game = Game.objects.order_by('-id').first()
    # Enrollment carries a non-null section: a student is enrolled in a
    # section, not directly in a game. setup_test_game already created one for
    # this game, so the seeded identities join that rather than inventing a
    # second one.
    section = Section.objects.order_by('section_id').first()
    if section is None:
        raise RuntimeError('setup_test_game left no section to enrol into')
    profile = FirmStarterProfile.objects.filter(
        scenario=game.scenario).order_by('id').first()

    # setup_test_game seeds a handful of teams; extend to the field size using
    # the same starter profile so every team begins from identical state.
    existing = list(Team.objects.filter(game=game).order_by('id'))
    for n in range(len(existing), TEAMS):
        Team.objects.create(
            game=game, name=f'Load Team {n + 1:02d}',
            firm_starter_profile=profile, performance_index=100,
            cash_on_hand=60_000_000, total_equity=60_000_000,
            participation_status='active')
    teams = list(Team.objects.filter(game=game).order_by('id')[:TEAMS])

    hashed = hash_password(PASSWORD)
    identities = []
    for team_index, team in enumerate(teams):
        for member in range(MEMBERS_PER_TEAM):
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

    instructor, _ = User.objects.get_or_create(
        username='load_instructor',
        defaults={'role': 'instructor', 'password_hash': hashed,
                  'email': 'inst@example.invalid'})
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hashed, role='instructor')

    rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
    return {
        'game_id': game.id,
        'section_id': section.section_id,
        'scenario': chosen.name,
        'round_number': rnd.round_number if rnd else None,
        'teams': len(teams),
        'identities': identities,
        'instructor': {'username': 'load_instructor', 'password': PASSWORD},
        'password': PASSWORD,
    }
