#!/usr/bin/env python3
"""Build a disposable game and resolve rounds under the current manifest.

Produces the artefacts the cross-environment replay needs: a pre-resolution
backup, a resolution manifest at whatever schema version the code is on, and a
competitive hash to reproduce. Every team gets a differentiated, non-trivial
decision set so the round exercises revenue, market entry, plant, talent,
compliance and supply-chain paths rather than an empty submission.

R&D, under the rules in force (V2-116). This fixture used to seed
feature-level `DecisionRDInvestment` rows. Owner ruling R10 retired that
decision, and `_run_phase_1` REFUSES a round that still carries one, so the
fixture could not resolve a round at all. R&D is now what R10 left standing: a
`DecisionPlatformDevelopment`, seeded only where the rules allow one -- a
generation that is unlocked this round and that the team does not already
hold, priced through `rd_costs.platform_development_cost` rather than by a
number invented here, with no more features than `rd_costs.feature_cap`.

Consequence to read before relying on a round: in the shipped scenarios the
first non-starting generation unlocks in round 2, so **round 1 carries no R&D
decision and `decision_platform` is empty there**. Use `--rounds 2` (or more)
when the platform path has to be inside the replayed round; the per-round
line printed below says how many development rows each round carried.
`--require-platform-development` turns an all-empty run into a non-zero exit.

ISOLATED USE ONLY. Point DB_* at a disposable stack; this script refuses the
production database host. `initialize_game` needs a superuser to own the
game; on a fresh disposable database the fixture creates one with an unusable
password.

    cd backend && DJANGO_SETTINGS_MODULE=globalstrat.settings \
      python3 ../handoff_readiness_v2/determinism_fixture.py --teams 4 --rounds 2
"""
import argparse
import io
import os
import sys
from decimal import Decimal as D

import django

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
django.setup()

from django.core.management import call_command  # noqa: E402
from django.utils import timezone  # noqa: E402

from core.models import DecisionSubmission, Game, Round, Team, TalentAllocation  # noqa: E402
from core.models.cc31_models import ComplianceInvestment  # noqa: E402
from core.models.decisions import (  # noqa: E402
    DecisionBudgetAllocation, DecisionMarketEntry, DecisionMarketing,
    DecisionPlant, DecisionPlatformDevelopment)
from core.models.sc_decisions import SourcingAllocation, SourcingDecision  # noqa: E402
from core.models.sc_models import Supplier  # noqa: E402
from core.models.scenario import (  # noqa: E402
    EntryModeDefinition, FeatureDefinition, MarketDefinition,
    PlatformFeatureCeiling, PlatformGenerationDefinition, Scenario)
from core.models.team_state import TeamProduct  # noqa: E402
from core.services import rd_costs  # noqa: E402

PRODUCTION_DB_HOST = '192.168.50.38'

# Which profiles develop a platform, and how. Two methods on purpose: they are
# priced from different authored fields (`development_cost`, `license_cost`).
PLATFORM_METHOD = {'aggressive_rd': 'in_house', 'balanced': 'license'}


PROFILES = [
    # (label, price factor, volume, rd share, promo share, entry markets)
    ('aggressive_rd', D('1.05'), 1400, D('0.60'), D('0.20'), 2),
    ('marketing_heavy', D('0.95'), 1800, D('0.15'), D('0.65'), 2),
    ('balanced', D('1.00'), 1200, D('0.35'), D('0.40'), 1),
    ('conservative', D('1.12'), 800, D('0.20'), D('0.20'), 0),
]


def seed_round(game, round_obj, scenario):
    markets = list(MarketDefinition.objects.filter(scenario=scenario).order_by('code'))
    features = list(FeatureDefinition.objects.filter(scenario=scenario).order_by('code')[:4])
    entry_mode = EntryModeDefinition.objects.filter(scenario=scenario).order_by('code').first()
    suppliers = list(Supplier.objects.filter(scenario=scenario).order_by('supplier_id')[:3])
    teams = list(Team.objects.filter(game=game).order_by('id'))
    developments = 0

    for index, team in enumerate(teams):
        label, price_factor, volume, rd_share, promo_share, entries = \
            PROFILES[index % len(PROFILES)]
        submission, _ = DecisionSubmission.objects.update_or_create(
            team=team, round=round_obj, defaults={'status': 'draft'})
        budget = D('10000000')
        DecisionBudgetAllocation.objects.update_or_create(
            submission=submission, defaults=dict(
                rd_budget=budget * rd_share,
                marketing_budget=budget * promo_share,
                strategy_budget=budget * D('0.15'),
                research_budget=budget * D('0.05')))

        home = team.home_market or markets[0]
        for product in TeamProduct.objects.filter(team=team).order_by('id'):
            for offset, market in enumerate([home] + markets[:entries]):
                DecisionMarketing.objects.update_or_create(
                    submission=submission, team_product=product, market=market,
                    defaults=dict(
                        retail_price=(D('500') * price_factor).quantize(D('0.01')),
                        promotion_budget=budget * promo_share / D(3),
                        campaign_focus_feature_ids=[f.id for f in features[:2]],
                        channel_digital_pct=D('0.6'), channel_traditional_pct=D('0.3'),
                        channel_trade_pct=D('0.1'), distribution_strategy='hybrid',
                        distribution_investment=D('250000'), sales_team_count=5 + index,
                        production_volume=volume + 50 * offset,
                        demand_estimate=volume + 50 * offset,
                        production_source_market=home))

        # R10: no `DecisionRDInvestment`. The engine refuses every stored row.
        if seed_platform_development(submission, team, round_obj, scenario,
                                     PLATFORM_METHOD.get(label)):
            developments += 1

        for market in markets[:entries]:
            if market == home:
                continue
            DecisionMarketEntry.objects.update_or_create(
                submission=submission, market=market, action='enter',
                defaults=dict(entry_mode=entry_mode,
                              initial_investment=D('1500000')))
            DecisionPlant.objects.update_or_create(
                submission=submission, market=market, action='contract',
                defaults=dict(capacity_units=0, contract_mfg_volume=volume // 2))
            ComplianceInvestment.objects.update_or_create(
                submission=submission, market=market,
                defaults=dict(investment_amount=D('200000')))

        for pool in ('rd', 'commercial', 'operations'):
            TalentAllocation.objects.update_or_create(
                submission=submission, talent_pool=pool,
                defaults=dict(hq_count=8 + index,
                              market_allocation={m.code: 3 + index for m in markets[:3]}))

        SourcingDecision.objects.update_or_create(
            team=team, round=round_obj, defaults=dict(
                multi_sourcing_strategy='dual_source' if index % 2 else 'single_source',
                tier_2_3_visibility_investment='comprehensive' if index % 2 else 'none'))
        share = 100 // max(len(suppliers), 1)
        for supplier in suppliers:
            SourcingAllocation.objects.update_or_create(
                team=team, round=round_obj, supplier=supplier,
                critical_input_category='semiconductor',
                defaults=dict(allocation_pct=share, volume_commitment_units=0,
                              payment_terms='net30'))
    return developments


def seed_platform_development(submission, team, round_obj, scenario, method):
    """One platform development, only where the rules in force allow one.

    Every condition here is asked of the same helper the engine's
    preconditions ask, so the fixture cannot drift from them again the way the
    feature-level rows did: unlock (`unlock_problem`), one platform per
    generation (`held_generation_ids`), the authored price
    (`platform_development_cost`) and the feature cap (`feature_cap`).
    """
    if not method:
        return False
    held = rd_costs.held_generation_ids(team)
    for generation in (PlatformGenerationDefinition.objects
                       .filter(scenario=scenario)
                       .order_by('generation_order')):
        if generation.pk in held:
            continue
        if rd_costs.unlock_problem(generation, round_obj.round_number):
            continue
        ceilings = (PlatformFeatureCeiling.objects
                    .filter(platform_generation=generation,
                            starting_value__gt=0)
                    .select_related('feature')
                    .order_by('feature__code')[:rd_costs.feature_cap(scenario)])
        DecisionPlatformDevelopment.objects.update_or_create(
            submission=submission, platform_generation=generation,
            defaults=dict(
                method=method,
                committed_cost=rd_costs.platform_development_cost(
                    generation, method),
                platform_name=f'{team.name} {generation.name}'[:100],
                feature_levels={str(c.feature_id): float(c.starting_value)
                                for c in ceilings}))
        return True
    return False


def ensure_game_owner():
    """`initialize_game` needs a superuser. A fresh disposable database has none."""
    from django.contrib.auth import get_user_model
    users = get_user_model().objects
    if users.filter(is_superuser=True).exists():
        return
    owner = users.create(username='determinism-fixture', is_superuser=True,
                         is_staff=True)
    owner.set_unusable_password()
    owner.save()


def main():
    # V2-128: never write a pre-resolution dump into the live backup root.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from harness_isolation import require_disposable_backup_dir
    require_disposable_backup_dir()

    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', type=int)
    parser.add_argument('--teams', type=int, default=4)
    parser.add_argument('--rounds', type=int, default=1)
    parser.add_argument('--name', default='DETERMINISM-FIXTURE')
    parser.add_argument('--section-id', type=int, default=90001)
    parser.add_argument('--require-platform-development', action='store_true',
                        help='Exit non-zero if no resolved round carried a '
                             'platform development (needs --rounds 2 or more '
                             'in the shipped scenarios).')
    args = parser.parse_args()

    from django.conf import settings
    db_host = settings.DATABASES['default'].get('HOST')
    if db_host == PRODUCTION_DB_HOST or getattr(settings, 'IS_PRODUCTION', False):
        raise SystemExit(
            f'Refusing to build a fixture game: database host {db_host!r} / '
            f'environment {getattr(settings, "ENVIRONMENT", "?")!r} is '
            f'production. Point DB_* at a disposable stack.')
    ensure_game_owner()

    scenario = (Scenario.objects.get(pk=args.scenario) if args.scenario
                else Scenario.objects.order_by('id').first())
    call_command('initialize_game', scenario=scenario.id, teams=args.teams,
                 name=args.name, stdout=io.StringIO())
    game = Game.objects.filter(name=args.name).order_by('-id').first()
    game.section_id = args.section_id
    game.save(update_fields=['section_id'])
    print(f'game_id={game.id} scenario={scenario.id} section_id={game.section_id}')

    from core.engine.advance_round import (
        advance_to_next_round, close_round, process_round)
    total_developments = 0
    for _ in range(args.rounds):
        round_obj = Round.objects.get(game=game, round_number=game.current_round)
        developments = seed_round(game, round_obj, scenario)
        total_developments += developments
        round_obj.deadline = timezone.now()
        round_obj.save(update_fields=['deadline'])
        close_round(game.id, reason='determinism-fixture')
        process_round(game.id)
        manifest = Round.objects.get(pk=round_obj.pk).resolution_manifest
        print(f'round={round_obj.round_number} '
              f'platform_developments={developments} '
              f'schema_version={manifest.schema_version} '
              f'input_sha256={manifest.input_sha256} '
              f'output_sha256={manifest.output_sha256} '
              f'narrative_sha256={manifest.narrative_sha256} '
              f'backup={manifest.backup_path}')
        game.refresh_from_db()
        if game.current_round < (scenario.num_rounds or 1):
            advance_to_next_round(game.id)
            game.refresh_from_db()

    if args.require_platform_development and not total_developments:
        raise SystemExit(
            'No resolved round carried a platform development, so the R&D '
            'path is untested by this run. Use --rounds 2 or more.')


if __name__ == '__main__':
    main()
