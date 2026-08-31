"""A game with an open round, for Stage-1 probes.

Not CRV2-08's completed game: these probes submit decisions and advance rounds,
so the fixture has to start with a round open and rounds left to play. Nothing
here is committed to the candidate; this seeds a throwaway database.
"""
TEAMS = 3
PASSWORD = 'crv210-probe'


def seed(password=PASSWORD):
    from django.contrib.auth.models import User as DjangoUser
    from django.core.management import call_command
    from django.utils import timezone

    from core.models import Enrollment, Game, Scenario, Team, User
    from core.models.course import Course, Section
    from core.utils.passwords import hash_password

    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('crv210admin', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)

    import fixture_contract as FC
    chosen, _ = FC.scenario_supporting(
        ('sourcing', 'trade_finance', 'compliance', 'logistics'))
    if chosen is None:
        chosen = Scenario.objects.order_by('id').first()
    call_command('setup_test_game', '--scenario', str(chosen.id), verbosity=0)

    game = Game.objects.order_by('-id').first()
    section = Section.objects.order_by('section_id').first()
    hashed = hash_password(password)

    roster = list(Team.objects.filter(game=game).order_by('id'))
    for extra in roster[TEAMS:]:
        Team.objects.filter(pk=extra.pk).update(participation_status='withdrawn')
    keep = roster[:TEAMS]

    teams = []
    for index, team in enumerate(keep, start=1):
        username = f'crv210_student_{index}'
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={'role': 'student', 'email': f'{username}@example.invalid'})
        User.objects.filter(pk=user.pk).update(
            password_hash=hashed, role='student', team_id=team.id)
        Enrollment.objects.update_or_create(
            user_id=user.user_id, section=section,
            defaults={'team_id': team.id, 'is_active': True,
                      'enrolled_at': timezone.now()})
        teams.append({'id': team.id, 'name': team.name, 'student': username,
                      'user_id': user.user_id,
                      'cash_on_hand': str(team.cash_on_hand)})

    instructor, _ = User.objects.get_or_create(
        username='crv210_instructor',
        defaults={'role': 'instructor', 'email': 'inst@example.invalid'})
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hashed, role='instructor')

    # The game must be reachable from its section, and owned, or every
    # game-scoped instructor route refuses the fixture's own instructor.
    Game.objects.filter(pk=game.pk).update(section_id=section.section_id)
    Course.objects.filter(course_id=section.course_id).update(
        instructor_id=instructor.user_id)

    return {'game_id': game.id, 'scenario': chosen.name,
            'scenario_id': chosen.id, 'section_id': section.section_id,
            'teams': teams, 'instructor': 'crv210_instructor',
            'password': password}


def context(game_id):
    """What the probes need to address: generations, features, products."""
    from core.models import Game, Round, Team
    from core.models.scenario import (PlatformFeatureCeiling,
                                      PlatformGenerationDefinition)
    from core.models.team_state import (TeamMarketPresence, TeamPlatform,
                                        TeamProduct, TeamProductMarket)
    game = Game.objects.get(id=game_id)
    generations = list(PlatformGenerationDefinition.objects
                       .filter(scenario=game.scenario)
                       .order_by('generation_order')
                       .values('id', 'name', 'generation_order', 'unlock_round',
                               'development_cost', 'license_cost',
                               'development_rounds', 'is_starting_platform'))
    teams = {}
    for team in Team.objects.filter(game=game, participation_status='active'):
        platform = TeamPlatform.objects.filter(team=team).order_by('id').first()
        ceilings = list(PlatformFeatureCeiling.objects
                        .filter(platform_generation=platform.platform_generation)
                        .values('feature_id', 'ceiling_value')[:3]) if platform else []
        teams[team.id] = {
            'name': team.name,
            'cash_on_hand': str(team.cash_on_hand),
            'team_platform_id': platform.id if platform else None,
            'platform_generation_id': (platform.platform_generation_id
                                       if platform else None),
            'ceilings': ceilings,
            'products': list(TeamProduct.objects.filter(team=team)
                             .values('id', 'name', 'status', 'positioning')),
            'product_markets': list(
                TeamProductMarket.objects
                .filter(team_product__team=team)
                .values('id', 'team_product_id', 'market_id', 'is_active')),
            'markets': list(TeamMarketPresence.objects.filter(team=team)
                            .values_list('market_id', flat=True)),
        }
    rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
    return {'current_round': game.current_round,
            'round_status': rnd.status if rnd else None,
            'num_rounds': game.scenario.num_rounds,
            'generations': generations, 'teams': teams}
