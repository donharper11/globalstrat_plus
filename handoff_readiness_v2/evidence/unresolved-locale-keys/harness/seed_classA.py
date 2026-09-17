"""Seed one game that puts all three Class A screens in reach at once.

The three defects live on three different screens with three different
preconditions, so the fixture is built to satisfy all of them in one round:

  * `topbar.over`  -- the chip renders only when `budget_status.over_budget`
    is true, which is `rd + marketing + strategy spend > total_budget_available`
    on the CURRENT round's submission. A marketing row with a very large
    promotion budget puts the team over.
  * `communications_page.max_words` -- the authored assignment is a
    ROUND_MILESTONE triggered at **round 2**, so the game is advanced to
    round 2 rather than left at round 1.
  * `strategy_tools.swot_placeholder` -- reachable at any round, but it needs
    the four quadrant labels to exist or the placeholder interpolates a key.

Each preconditionent is ASSERTED, not assumed: a screen that silently fails to
show the thing under test would photograph a pass.
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

from django.apps import apps                                     # noqa: E402
from django.contrib.auth.models import User as DjangoUser        # noqa: E402
from django.core.management import call_command                  # noqa: E402
from django.db import connection                                 # noqa: E402
from django.utils import timezone                                # noqa: E402

from core.models import (                                        # noqa: E402
    DecisionSubmission, Enrollment, Game, Round, Scenario, Team, User)
from core.models.cc32_models import CommunicationAssignment      # noqa: E402
from core.models.course import Course, Section, SimulationInstance  # noqa: E402
from core.models.decisions import (                              # noqa: E402
    DecisionBudgetAllocation, DecisionMarketing)
from core.models.scenario import MarketDefinition                # noqa: E402
from core.models.team_state import TeamProduct                   # noqa: E402
from core.utils.passwords import hash_password                   # noqa: E402

PASSWORD = 'classa-pass'
GAME_NAME = 'Class A Verification Heat'
OUT = pathlib.Path(__file__).resolve().parent / 'fixture_classA.json'


class SurfaceEmpty(RuntimeError):
    """A condition this fixture exists to create did not occur."""


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
    _legacy_tables()
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('classaadmin', 'a@e.com', 'x')

    scenario = Scenario.objects.order_by('id').first()
    Scenario.objects.filter(pk=scenario.pk).update(num_rounds=4)
    scenario.refresh_from_db()

    call_command('initialize_game', scenario=scenario.id, teams=4,
                 name=GAME_NAME, verbosity=0)
    game = Game.objects.filter(name=GAME_NAME).order_by('-id').first()
    teams = list(Team.objects.filter(game=game).order_by('id'))
    target = teams[0]

    hashed = hash_password(PASSWORD)
    instructor, _ = User.objects.get_or_create(
        username='classa_instructor',
        defaults={'role': 'instructor', 'email': 'i@example.invalid'})
    User.objects.filter(pk=instructor.pk).update(
        password_hash=hashed, role='instructor')
    course = Course.objects.create(
        course_code='CLASSA', course_name='Class A Verification',
        instructor_id=instructor.user_id, academic_year='2026',
        semester='Verification', is_active=True, created_at=timezone.now())
    section = Section.objects.create(
        course=course, section_code='CA-01', section_name='Class A Section',
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
            username = 'ca_t%d_m%d' % (index, member)
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

    # --- play round 1 so round 2 can open --------------------------------
    round_one = Round.objects.get(game=game, round_number=1)
    from v6_envelope_fixture import seed_round
    seed_round(game, round_one, scenario)
    from core.engine.advance_round import advance_round, close_round
    round_one.deadline = timezone.now()
    round_one.save(update_fields=['deadline'])
    # close_round locks every team's submission, defaulting any team that never
    # submitted. advance_round then processes round 1 and opens round 2.
    # Advancing without closing first raises RoundNotReadyError on the first
    # unlocked team, which is what this fixture hit.
    close_round(game.id, reason='class-a-fixture')
    advance_round(game.id)

    game.refresh_from_db()
    if game.current_round != 2:
        raise SurfaceEmpty('Game is at round %s, not 2; the communication '
                           'assignment triggers at round 2.' % game.current_round)
    round_two = Round.objects.get(game=game, round_number=2)
    if round_two.status != 'open':
        raise SurfaceEmpty('Round 2 is %s, not open.' % round_two.status)

    # --- put the target team OVER BUDGET on round 2 ----------------------
    submission, _ = DecisionSubmission.objects.get_or_create(
        team=target, round=round_two, defaults={'status': 'draft'})
    DecisionBudgetAllocation.objects.update_or_create(
        submission=submission,
        defaults={'rd_budget': D('1000000'), 'marketing_budget': D('1000000'),
                  'strategy_budget': D('1000000')})
    market = MarketDefinition.objects.filter(scenario=scenario).first()
    product = TeamProduct.objects.filter(team=target, status='active').first()
    if product is None:
        raise SurfaceEmpty('No active product to attach a marketing row to.')
    DecisionMarketing.objects.update_or_create(
        submission=submission, team_product=product, market=market,
        defaults={
            'retail_price': D('400'),
            # The whole point: spend far past the formula budget.
            'promotion_budget': D('60000000'),
            'campaign_focus_feature_ids': [],
            'channel_digital_pct': D('0.34'),
            'channel_traditional_pct': D('0.33'),
            'channel_trade_pct': D('0.33'),
            'distribution_strategy': 'mass_retail',
            'distribution_investment': D('0'), 'sales_team_count': 0,
            'distribution_channel_detail': {}, 'production_volume': 100,
            'production_source_market': market, 'demand_estimate': 100,
        })

    # --- assert each precondition actually holds --------------------------
    from core.engine.utils import get_config
    from core.models.results_financials import RoundResultFinancials
    budget_base = float(get_config(scenario, 'budget_base_amount', default=5000000))
    pct = float(get_config(scenario, 'budget_profit_pct', default=0.20))
    prev = RoundResultFinancials.objects.filter(
        game=game, team=target, round_number=game.current_round - 1).first()
    available = budget_base + max((float(prev.net_income) if prev else 0) * pct, 0)
    spend = 60000000.0
    if spend <= available:
        raise SurfaceEmpty('Spend %.0f does not exceed the budget %.0f, so the '
                           'over-budget chip would not render.' % (spend, available))

    assignments = [a for a in CommunicationAssignment.objects.filter(
        scenario=scenario)
        if (a.trigger_condition or {}).get('round') == 2]
    if not assignments:
        raise SurfaceEmpty('No communication assignment triggers at round 2, '
                           'so the word-limit tag would never render.')

    fixture = {
        'game_id': game.id, 'game_name': game.name,
        'round_number': game.current_round,
        'password': PASSWORD,
        'team_id': target.id, 'team_name': target.name,
        'student': next(s['username'] for s in students
                        if s['team_id'] == target.id),
        'budget_available': available,
        'budget_spend': spend,
        'expected_over_budget': True,
        'assignment': {'code': assignments[0].code,
                       'word_limit': assignments[0].word_limit},
    }
    OUT.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(fixture, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
