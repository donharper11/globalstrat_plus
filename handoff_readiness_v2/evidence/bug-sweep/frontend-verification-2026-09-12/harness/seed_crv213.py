"""Seed the CRV2-13 frontend-verification fixture on a disposable database.

Deliberately shaped for the seven things the browser pass has to show:

  * starter products carry a round-0 price, so `price_band` anchors on a real
    previous-round price and the pricing screen can state a legal range;
  * ONE extra product is created with no price history at all, so its anchor
    falls back to the positioning reference. `blank_price` returns None for it,
    which is the "could not be priced -> not for sale" case;
  * the section authors max_teams=8 and team_size_max=5 and is filled to
    exactly 5 members a team, so a sixth member and a ninth firm are both one
    step away from the cap.
"""
import json

from django.apps import apps
from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.db import connection
from django.utils import timezone

from core.models import Enrollment, Game, Round, Scenario, Team, User
from core.models.course import Course, Section, SimulationInstance
from core.models.scenario import MarketDefinition
from core.models.team_state import TeamPlatform, TeamProduct, TeamProductMarket
from core.utils.passwords import hash_password

PASSWORD = 'crv213-pass'
GAME_NAME = 'CRV2-13 Verification Heat'


def _create_legacy_tables():
    """Unmanaged models have no migration; the app still reads them."""
    existing = set(connection.introspection.table_names())
    unmanaged = [m for m in apps.get_models() if not m._meta.managed]
    for m in unmanaged:
        m._meta.managed = True
    created = []
    with connection.schema_editor() as editor:
        for m in unmanaged:
            if m._meta.db_table not in existing:
                editor.create_model(m)
                created.append(m._meta.db_table)
    for m in unmanaged:
        m._meta.managed = False
    return created


def run():
    _create_legacy_tables()

    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('crv213admin', 'a@e.com', 'x')

    call_command('load_scenario',
                 file='scenarios/consumer_electronics_2026.yaml', verbosity=0)
    scenario = Scenario.objects.order_by('-id').first()
    # Three rounds keeps close/process/advance reachable inside one pass.
    Scenario.objects.filter(pk=scenario.pk).update(num_rounds=3)
    scenario.refresh_from_db()

    call_command('initialize_game', scenario=scenario.id, teams=3,
                 name=GAME_NAME, verbosity=0)
    game = Game.objects.get(name=GAME_NAME)
    teams = list(Team.objects.filter(game=game).order_by('id'))

    hashed = hash_password(PASSWORD)
    instructor, _ = User.objects.get_or_create(
        username='crv213_instructor',
        defaults={'role': 'instructor', 'email': 'inst@example.invalid'})
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hashed, role='instructor')

    course = Course.objects.create(
        course_code='CRV213', course_name='CRV2-13 Verification',
        instructor_id=instructor.user_id, academic_year='2026',
        semester='Verification', is_active=True, created_at=timezone.now())
    # The authored competition shape: max 8 firms, teams of 3-5 (Ruling 4).
    section = Section.objects.create(
        course=course, section_code='CRV213-01',
        section_name='Verification Section', max_teams=8, team_size_min=3,
        team_size_max=5, is_active=True, created_at=timezone.now())
    game.section_id = section.section_id
    game.save(update_fields=['section_id'])
    SimulationInstance.objects.create(
        section=section, game_id=game.id, current_round=game.current_round,
        total_rounds=scenario.num_rounds, status='active',
        started_at=timezone.now(), created_at=timezone.now())

    students = []
    for team_index, team in enumerate(teams, start=1):
        # Exactly team_size_max members, so the next one is the refusal.
        for member in range(1, 6):
            username = f'crv213_t{team_index}_m{member}'
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={'role': 'student',
                          'email': f'{username}@example.invalid'})
            User.objects.filter(pk=user.pk).update(
                password_hash=hashed, role='student', team_id=team.id)
            Enrollment.objects.update_or_create(
                user_id=user.user_id, section=section,
                defaults={'team_id': team.id, 'is_active': True,
                          'enrolled_at': timezone.now()})
            students.append({'username': username, 'team_id': team.id,
                             'user_id': user.user_id, 'member': member})

    # One spare identity, enrolled in the section but on no team, so the
    # sixth-member refusal can be provoked without inventing a user mid-run.
    spare, _ = User.objects.get_or_create(
        username='crv213_spare',
        defaults={'role': 'student', 'email': 'spare@example.invalid'})
    User.objects.filter(pk=spare.pk).update(password_hash=hashed,
                                            role='student', team_id=None)
    Enrollment.objects.update_or_create(
        user_id=spare.user_id, section=section,
        defaults={'team_id': None, 'is_active': True,
                  'enrolled_at': timezone.now()})

    # --- the product that cannot be priced -------------------------------
    # No RoundResultProductMarket row will exist for it, so `price_anchor`
    # falls through to the positioning reference and `blank_price` returns
    # None: blank here means NOT FOR SALE, not "priced at the floor".
    team_a = teams[0]
    platform = TeamPlatform.objects.filter(team=team_a).order_by('id').first()
    seed_tpm = (TeamProductMarket.objects
                .filter(team_product__team=team_a, is_active=True)
                .select_related('market').order_by('id').first())
    new_product = TeamProduct.objects.create(
        team=team_a, team_platform=platform, name='Aurora NX',
        positioning='premium', status='active',
        created_round=game.current_round)
    TeamProductMarket.objects.create(
        team_product=new_product, market=seed_tpm.market, is_active=True,
        first_offered_round=game.current_round)

    rnd = Round.objects.filter(
        game=game, round_number=game.current_round).first()

    # Report every product-market the pricing screen will show, and whether it
    # has a prior-round price, so the walkthrough addresses them by fact
    # rather than by guessing which row is which.
    from core.models.results_financials import RoundResultProductMarket
    product_markets = []
    for product in TeamProduct.objects.filter(team=team_a, status='active'):
        for tpm in TeamProductMarket.objects.filter(
                team_product=product, is_active=True).select_related('market'):
            has_history = RoundResultProductMarket.objects.filter(
                team=team_a, team_product=product, market=tpm.market,
                round_number__lt=game.current_round).exists()
            product_markets.append({
                'key': f'{product.id}_{tpm.market_id}',
                'product_id': product.id, 'product_name': product.name,
                'market_id': tpm.market_id, 'market_name': tpm.market.name,
                'has_price_history': has_history,
            })

    return {
        'game_id': game.id, 'game_name': game.name,
        'section_id': section.section_id, 'scenario': scenario.name,
        'password': PASSWORD,
        'current_round': game.current_round,
        'round_status': rnd.status if rnd else None,
        'total_rounds': scenario.num_rounds,
        'instructor': 'crv213_instructor',
        'spare_student': 'crv213_spare',
        'section_caps': {'max_teams': section.max_teams,
                         'team_size_min': section.team_size_min,
                         'team_size_max': section.team_size_max},
        'teams': [{'id': t.id, 'name': t.name} for t in teams],
        'students': students,
        'team_a_id': team_a.id,
        'new_product': {'id': new_product.id, 'name': new_product.name,
                        'market_id': seed_tpm.market_id,
                        'market_name': seed_tpm.market.name,
                        'key': f'{new_product.id}_{seed_tpm.market_id}'},
        'product_markets': product_markets,
    }
