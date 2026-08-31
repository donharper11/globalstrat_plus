"""ORM-side seeding and row reading for the GSP-CRV2-10 Stage-1 probes.

Only identities and read-back live here. Every decision, lock and lifecycle
action in the probe run is driven through the HTTP API, because a row written
by the seeder proves nothing about what the product accepts.

One deliberate exception is declared in `seed`: the A3 team's starter Gen-1
platform is set to `retired` before play begins. Every team is initialised
owning the starting generation, and `_process_platform_development` skips a
generation the team already holds, so a `development_rounds: 0` generation is
unreachable through the API on a fresh team. Retiring the starter platform is
the only way to ask the question the handoff asks; it is fixture setup, stated
here, and it is not itself a probe result.
"""
PASSWORD = 'crv210-pass'
TEAM_COUNT = 8
SCENARIO_FILE_NAME = 'Consumer Electronics 2026'


def seed(password=PASSWORD):
    from django.contrib.auth.models import User as DjangoUser
    from django.core.management import call_command
    from django.utils import timezone

    from core.models import Game, Team, User
    from core.models.course import Course, Enrollment, Section, SimulationInstance
    from core.models.scenario import (
        FeatureDefinition, FeatureLevelCost, PlatformFeatureCeiling,
        PlatformGenerationDefinition, Scenario,
    )
    from core.models.team_state import (
        TeamPlatform, TeamPlatformFeatureLevel, TeamProduct, TeamProductMarket,
    )
    from core.utils.passwords import hash_password

    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('crv210admin', 'a@example.invalid', 'x')
    call_command('load_all_scenarios', verbosity=0)

    scenario = (Scenario.objects.filter(name__icontains='Consumer Electronics')
                .order_by('id').first()
                or Scenario.objects.order_by('id').first())

    call_command('initialize_game', scenario=scenario.pk, teams=TEAM_COUNT,
                 name='CRV2-10 Stage 1 probe game', verbosity=0)
    game = Game.objects.order_by('-id').first()

    instructor, _ = User.objects.get_or_create(
        username='crv210_instructor',
        defaults={'role': 'instructor', 'email': 'inst@example.invalid'})
    hashed = hash_password(password)
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hashed, role='instructor')

    course, _ = Course.objects.get_or_create(
        course_code='CRV210',
        defaults={'course_name': 'CRV2-10 Stage 1', 'academic_year': '2026',
                  'semester': 'Spring', 'is_active': True,
                  'created_at': timezone.now()})
    Course.objects.filter(pk=course.pk).update(
        instructor_id=instructor.user_id, is_active=True)
    section, _ = Section.objects.get_or_create(
        course=course, section_code='CRV210-01',
        defaults={'section_name': 'Probe section', 'is_active': True,
                  'created_at': timezone.now()})
    # The model defaults are the authored caps under test. Restate them so the
    # fixture cannot pass because a previous run left different numbers.
    Section.objects.filter(pk=section.pk).update(
        max_teams=8, team_size_min=3, team_size_max=5, is_active=True)
    section.refresh_from_db()
    SimulationInstance.objects.update_or_create(
        section=section,
        defaults={'game_id': game.id, 'current_round': game.current_round,
                  'total_rounds': scenario.num_rounds, 'status': 'active',
                  'started_at': timezone.now(), 'created_at': timezone.now()})
    Game.objects.filter(pk=game.pk).update(section_id=section.section_id)

    teams = []
    for index, team in enumerate(Team.objects.filter(game=game).order_by('id'), 1):
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
        platforms = [
            {'id': p.id, 'name': p.name, 'status': p.status,
             'generation_order': p.platform_generation.generation_order,
             'generation_id': p.platform_generation_id}
            for p in TeamPlatform.objects.filter(team=team).order_by('id')]
        products = []
        for product in TeamProduct.objects.filter(team=team).order_by('id'):
            products.append({
                'id': product.id, 'name': product.name,
                'status': product.status,
                'team_platform_id': product.team_platform_id,
                'markets': [
                    {'id': link.id, 'market_id': link.market_id,
                     'market_code': link.market.code,
                     'is_active': link.is_active}
                    for link in TeamProductMarket.objects.filter(
                        team_product=product).order_by('id')]})
        feature_levels = [
            {'feature_id': fl.feature_id, 'code': fl.feature.code,
             'name': fl.feature.name, 'level': float(fl.current_level),
             'team_platform_id': fl.team_platform_id}
            for fl in TeamPlatformFeatureLevel.objects.filter(
                team_platform__team=team).order_by('feature__code')]
        teams.append({
            'index': index, 'id': team.id, 'name': team.name,
            'student': username, 'user_id': user.user_id,
            'cash_on_hand': float(team.cash_on_hand),
            'total_equity': float(team.total_equity),
            'performance_index': float(team.performance_index),
            'starter_profile': team.firm_starter_profile.profile_name,
            'firm_starter_profile_id': team.firm_starter_profile_id,
            'home_market': team.home_market.code,
            'platforms': platforms, 'products': products,
            'feature_levels': feature_levels})

    generations = [
        {'id': g.id, 'name': g.name, 'generation_order': g.generation_order,
         'unlock_round': g.unlock_round,
         'development_cost': float(g.development_cost),
         'license_cost': float(g.license_cost),
         'development_rounds': g.development_rounds,
         'is_starting_platform': g.is_starting_platform,
         'ceilings': {c.feature.code: float(c.ceiling_value)
                      for c in PlatformFeatureCeiling.objects.filter(
                          platform_generation=g)}}
        for g in PlatformGenerationDefinition.objects.filter(
            scenario=scenario).order_by('generation_order')]

    features = [{'id': f.id, 'code': f.code, 'name': f.name, 'layer': f.layer,
                 'is_licensable': f.is_licensable,
                 'time_lag_rounds': f.time_lag_rounds,
                 'max_value': float(f.max_value)}
                for f in FeatureDefinition.objects.filter(
                    scenario=scenario, layer='platform').order_by('code')]

    level_costs = [
        {'feature_id': lc.feature_id, 'feature_code': lc.feature.code,
         'generation_order': lc.platform_generation.generation_order,
         'level': lc.level, 'incremental_cost': float(lc.incremental_cost)}
        for lc in FeatureLevelCost.objects.filter(
            platform_generation__scenario=scenario).order_by(
                'platform_generation__generation_order', 'feature__code', 'level')]

    markets = [{'id': m.id, 'code': m.code, 'name': m.name}
               for m in scenario.markets.order_by('id')]

    # --- declared fixture setup, not a probe result ---------------------
    a3_team = teams[7]
    retired = []
    for platform in a3_team['platforms']:
        TeamPlatform.objects.filter(pk=platform['id']).update(status='retired')
        retired.append(platform['id'])
        platform['status'] = 'retired'
    a3_setup = {'team_id': a3_team['id'], 'retired_platform_ids': retired,
                'why': 'a development_rounds:0 generation is otherwise '
                       'unreachable: every team is initialised owning it'}

    return {'game_id': game.id, 'scenario_id': scenario.id,
            'scenario': scenario.name, 'num_rounds': scenario.num_rounds,
            'section_id': section.section_id, 'course_id': course.course_id,
            'section_caps': {'max_teams': section.max_teams,
                             'team_size_min': section.team_size_min,
                             'team_size_max': section.team_size_max},
            'instructor': 'crv210_instructor',
            'instructor_user_id': instructor.user_id,
            'teams': teams, 'generations': generations, 'features': features,
            'feature_level_costs': level_costs, 'markets': markets,
            'a3_fixture_setup': a3_setup}


def snapshot(game_id):
    """Every row the probe record cites, read straight from the database."""
    from core.models import Game, Team
    from core.models.decisions import (
        DecisionPlatformDevelopment, DecisionProductRetire,
        DecisionRDInvestment, DecisionSubmission, DecisionMarketing,
        DecisionBudgetAllocation,
    )
    from core.models.results_financials import (
        RoundResultFinancials, RoundResultProductMarket)
    from core.models.team_state import (
        PendingFeatureGain, TeamPlatform, TeamPlatformFeatureLevel,
        TeamProduct, TeamProductMarket)

    game = Game.objects.get(pk=game_id)
    out = {'game_id': game.id, 'current_round': game.current_round,
           'status': game.status, 'teams': {}}
    for team in Team.objects.filter(game=game).order_by('id'):
        out['teams'][str(team.id)] = {
            'name': team.name,
            'cash_on_hand': float(team.cash_on_hand),
            'total_debt': float(team.total_debt),
            'total_equity': float(team.total_equity),
            'platforms': [
                {'id': p.id, 'name': p.name, 'status': p.status,
                 'generation_order': p.platform_generation.generation_order,
                 'development_method': p.development_method,
                 'development_started_round': p.development_started_round,
                 'development_rounds_remaining': p.development_rounds_remaining,
                 'activated_round': p.activated_round,
                 'capitalized_cost': float(p.capitalized_cost or 0),
                 'authored_development_cost': float(
                     p.platform_generation.development_cost),
                 'authored_license_cost': float(
                     p.platform_generation.license_cost),
                 'authored_development_rounds':
                     p.platform_generation.development_rounds}
                for p in TeamPlatform.objects.filter(team=team).order_by('id')],
            'feature_levels': [
                {'team_platform_id': fl.team_platform_id,
                 'feature_code': fl.feature.code,
                 'level': float(fl.current_level)}
                for fl in TeamPlatformFeatureLevel.objects.filter(
                    team_platform__team=team).order_by(
                        'team_platform_id', 'feature__code')],
            'pending_feature_gains': [
                {'team_platform_id': g.team_platform_id,
                 'feature_code': g.feature.code,
                 'gain_amount': float(g.gain_amount),
                 'applies_round': g.applies_round,
                 'applied': getattr(g, 'applied', None)}
                for g in PendingFeatureGain.objects.filter(
                    team_platform__team=team).order_by('id')],
            'products': [
                {'id': p.id, 'name': p.name, 'status': p.status,
                 'created_round': p.created_round,
                 'retired_round': p.retired_round,
                 'team_platform_id': p.team_platform_id,
                 'markets': [
                     {'market_code': link.market.code,
                      'is_active': link.is_active,
                      'first_offered_round': link.first_offered_round}
                     for link in TeamProductMarket.objects.filter(
                         team_product=p).order_by('id')]}
                for p in TeamProduct.objects.filter(team=team).order_by('id')],
            'financials': [
                {'round': f.round_number,
                 'rd_expense': float(f.rd_expense),
                 'platform_amortization': float(f.platform_amortization),
                 'marketing_expense': float(f.marketing_expense),
                 'strategy_expense': float(f.strategy_expense),
                 'total_revenue': float(f.total_revenue),
                 'net_income': float(f.net_income),
                 'cash_opening': float(f.cash_opening),
                 'cash_closing': float(f.cash_closing),
                 'investing_cash_flow': float(f.investing_cash_flow)}
                for f in RoundResultFinancials.objects.filter(
                    game=game, team=team).order_by('round_number')],
            'product_market_results': [
                {'round': r.round_number, 'product': r.team_product.name,
                 'market': r.market.code,
                 'retail_price': float(r.retail_price),
                 'units_produced': r.units_produced,
                 'units_sold': float(r.units_sold),
                 'local_revenue': float(r.local_revenue)}
                for r in RoundResultProductMarket.objects.filter(
                    game=game, team=team).order_by(
                        'round_number', 'team_product_id', 'market_id')],
            'submissions': [],
        }
        for submission in DecisionSubmission.objects.filter(
                team=team, round__game=game).order_by('round__round_number'):
            budget = DecisionBudgetAllocation.objects.filter(
                submission=submission).first()
            out['teams'][str(team.id)]['submissions'].append({
                'round': submission.round.round_number,
                'status': submission.status,
                'budget': None if budget is None else {
                    'rd_budget': float(budget.rd_budget),
                    'marketing_budget': float(budget.marketing_budget),
                    'strategy_budget': float(budget.strategy_budget)},
                'platform_developments': [
                    {'generation_order':
                        d.platform_generation.generation_order,
                     'method': d.method,
                     'committed_cost': float(d.committed_cost),
                     'authored_development_cost': float(
                         d.platform_generation.development_cost),
                     'authored_license_cost': float(
                         d.platform_generation.license_cost),
                     'platform_name': d.platform_name,
                     'feature_levels': d.feature_levels}
                    for d in DecisionPlatformDevelopment.objects.filter(
                        submission=submission).order_by('id')],
                'rd_investments': [
                    {'team_platform_id': i.team_platform_id,
                     'feature_code': i.feature.code, 'method': i.method,
                     'amount': float(i.amount),
                     'target_level': i.target_level,
                     'calculated_cost': float(i.calculated_cost)}
                    for i in DecisionRDInvestment.objects.filter(
                        submission=submission).order_by('id')],
                'marketing': [
                    {'product': m.team_product.name, 'market': m.market.code,
                     'retail_price': float(m.retail_price),
                     'promotion_budget': float(m.promotion_budget),
                     'production_volume': m.production_volume}
                    for m in DecisionMarketing.objects.filter(
                        submission=submission).order_by('id')],
                'product_retires': [
                    {'product': r.team_product.name, 'timing': r.timing}
                    for r in DecisionProductRetire.objects.filter(
                        submission=submission).order_by('id')],
            })
    return out


def cohort_state(section_id, game_id):
    """What the A6 caps would have to bind on."""
    from core.models import Team, User
    from core.models.course import Enrollment, Section

    section = Section.objects.get(pk=section_id)
    teams = list(Team.objects.filter(game_id=game_id).order_by('id'))
    per_team = {}
    for team in teams:
        per_team[str(team.id)] = {
            'name': team.name,
            'users_with_team_id': User.objects.filter(team_id=team.id).count(),
            'active_enrollments': Enrollment.objects.filter(
                team_id=team.id, is_active=True).count()}
    return {'section_id': section.section_id,
            'max_teams': section.max_teams,
            'team_size_min': section.team_size_min,
            'team_size_max': section.team_size_max,
            'teams_in_game': len(teams),
            'enrollments_in_section': Enrollment.objects.filter(
                section=section, is_active=True).count(),
            'per_team': per_team}


def games_for_section(section_id):
    from core.models import Game, Team
    rows = []
    for game in Game.objects.filter(section_id=section_id).order_by('id'):
        rows.append({'game_id': game.id, 'name': game.name,
                     'teams': Team.objects.filter(game=game).count()})
    return rows
