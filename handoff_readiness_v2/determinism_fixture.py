#!/usr/bin/env python3
"""Build a disposable game and resolve one round under the v2 manifest.

Produces the artefacts the cross-environment replay needs: a pre-resolution
backup, a schema-version-2 resolution manifest, and a competitive hash to
reproduce. Every team gets a differentiated, non-trivial decision set so the
round exercises revenue, R&D, market entry, plant, talent, compliance and
supply-chain paths rather than an empty submission.

ISOLATED USE ONLY. Point DB_* at a disposable stack.

    cd backend && DJANGO_SETTINGS_MODULE=globalstrat.settings \
      python3 ../handoff_readiness_v2/determinism_fixture.py --teams 4
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
    DecisionPlant, DecisionRDInvestment)
from core.models.sc_decisions import SourcingAllocation, SourcingDecision  # noqa: E402
from core.models.sc_models import Supplier  # noqa: E402
from core.models.scenario import (  # noqa: E402
    EntryModeDefinition, FeatureDefinition, MarketDefinition, Scenario)
from core.models.team_state import TeamPlatform, TeamProduct  # noqa: E402


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

        for platform in TeamPlatform.objects.filter(team=team).order_by('id'):
            for offset, feature in enumerate(features):
                DecisionRDInvestment.objects.update_or_create(
                    submission=submission, team_platform=platform, feature=feature,
                    method='in_house',
                    defaults=dict(amount=budget * rd_share / D(len(features)),
                                  calculated_cost=budget * rd_share / D(len(features))))

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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', type=int)
    parser.add_argument('--teams', type=int, default=4)
    parser.add_argument('--rounds', type=int, default=1)
    parser.add_argument('--name', default='DETERMINISM-FIXTURE')
    parser.add_argument('--section-id', type=int, default=90001)
    args = parser.parse_args()

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
    for _ in range(args.rounds):
        round_obj = Round.objects.get(game=game, round_number=game.current_round)
        seed_round(game, round_obj, scenario)
        round_obj.deadline = timezone.now()
        round_obj.save(update_fields=['deadline'])
        close_round(game.id, reason='determinism-fixture')
        process_round(game.id)
        manifest = Round.objects.get(pk=round_obj.pk).resolution_manifest
        print(f'round={round_obj.round_number} '
              f'schema_version={manifest.schema_version} '
              f'input_sha256={manifest.input_sha256} '
              f'output_sha256={manifest.output_sha256} '
              f'narrative_sha256={manifest.narrative_sha256} '
              f'backup={manifest.backup_path}')
        game.refresh_from_db()
        if game.current_round < (scenario.num_rounds or 1):
            advance_to_next_round(game.id)
            game.refresh_from_db()


if __name__ == '__main__':
    main()
