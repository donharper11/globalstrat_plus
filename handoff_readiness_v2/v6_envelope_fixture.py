#!/usr/bin/env python3
"""Build a disposable game whose round 1 exercises everything new at manifest v6.

`determinism_fixture.py` proved the v2 envelope. It cannot prove the v6 one,
because the sections that moved did not exist when it was written: a round it
builds carries **zero** `decision_research_purchase` rows, so a replay of it
would reproduce the new section's emptiness and call that a pass.

This fixture therefore seeds, and then ASSERTS, three things a v6 replay has to
actually contain:

  1. `decision_research_purchase` -- the section added at v5 -> v6. Whole-game
     reports, a market-scoped report and an analyst query, each priced through
     `research_catalogue.price_for` so the row carries the authored price
     rather than one invented here.
  2. an out-of-band price at the deadline -- a price above the band's upper
     edge, which `close_round` moves to the nearer edge and records with a
     `price_band_adjusted` audit event. The *adjusted* number lands in
     `decision_marketing.retail_price`, which is a hashed output section, so
     this reaches the competitive envelope and not only the audit trail.
  3. a not-for-sale row -- a blank price on a product-market with no
     prior-round price, which the owner's 2026-09-12 ruling records as
     `price_not_offered` and leaves unpriced rather than refusing the round.

Plus ordinary marketing/production/R&D/entry/talent/sourcing decisions for
every team, so the round is not degenerate.

Each of the three is asserted, not assumed: the script exits non-zero and says
which surface was empty rather than resolving a round that proves nothing.

ISOLATED USE ONLY. Point DB_* at a disposable stack.

    cd backend && python3 ../handoff_readiness_v2/v6_envelope_fixture.py --teams 4
"""
import argparse
import io
import json
import os
import sys
from decimal import Decimal as D

import django

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')
django.setup()

from django.core.management import call_command  # noqa: E402
from django.utils import timezone  # noqa: E402

from core.models import (  # noqa: E402
    DecisionAuditEvent, DecisionSubmission, Game, Round, Team, TalentAllocation)
from core.models.cc31_models import ComplianceInvestment  # noqa: E402
from core.models.decisions import (  # noqa: E402
    DecisionBudgetAllocation, DecisionMarketEntry, DecisionMarketing,
    DecisionPlant)
from core.models.research import DecisionResearchPurchase  # noqa: E402
from core.models.results_financials import RoundResultProductMarket  # noqa: E402
from core.models.sc_decisions import SourcingAllocation, SourcingDecision  # noqa: E402
from core.models.sc_models import Supplier  # noqa: E402
from core.models.scenario import (  # noqa: E402
    EntryModeDefinition, FeatureDefinition, MarketDefinition, Scenario)
from core.models.team_state import TeamProduct  # noqa: E402
from core.services import price_band as band_rules  # noqa: E402
from core.services import research_catalogue as rc  # noqa: E402


PROFILES = [
    # (label, price factor, volume, rd share, promo share, entry markets)
    ('aggressive_rd', D('1.05'), 1400, D('0.60'), D('0.20'), 2),
    ('marketing_heavy', D('0.95'), 1800, D('0.15'), D('0.65'), 2),
    ('balanced', D('1.00'), 1200, D('0.35'), D('0.40'), 1),
    ('conservative', D('1.12'), 800, D('0.20'), D('0.20'), 0),
]


class SurfaceEmpty(RuntimeError):
    """A section this fixture exists to populate came out empty."""


def _marketing_defaults(*, budget, promo_share, price, volume, offset, index,
                        features, home):
    return dict(
        retail_price=price,
        promotion_budget=budget * promo_share / D(3),
        campaign_focus_feature_ids=[f.id for f in features[:2]],
        channel_digital_pct=D('0.6'), channel_traditional_pct=D('0.3'),
        channel_trade_pct=D('0.1'), distribution_strategy='hybrid',
        distribution_investment=D('250000'), sales_team_count=5 + index,
        production_volume=volume + 50 * offset,
        demand_estimate=volume + 50 * offset,
        production_source_market=home)


def seed_round(game, round_obj, scenario):
    """The ordinary, non-degenerate decision set, per determinism_fixture."""
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
                    defaults=_marketing_defaults(
                        budget=budget, promo_share=promo_share,
                        price=(D('500') * price_factor).quantize(D('0.01')),
                        volume=volume, offset=offset, index=index,
                        features=features, home=home))

        # NO feature-level R&D. `determinism_fixture.py` seeds
        # `DecisionRDInvestment` rows, but ruling R10 retired feature-level R&D
        # and `_run_phase_1` now REFUSES a round that still carries them
        # ("feature-level R&D investment is retired ... Develop a new platform
        # and re-base the product onto it"). Seeding them here would make the
        # round unresolvable, so the v6 round carries none and `decision_rd` is
        # empty by design rather than by oversight.

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


def seed_research_purchases(game, round_obj, scenario):
    """The v6 section itself. Priced through the one calculator, per team.

    Three shapes on purpose, because the natural key is
    ``(submission_id, report_type, scope_key)`` and a single whole-game report
    would leave the scope_key half of it constant and untested:
      * a whole-game report   -> scope_key ''
      * a market-scoped report -> scope_key '<market code>'
      * an analyst query       -> scope_key '<ordinal>'
    """
    created = []
    teams = list(Team.objects.filter(game=game).order_by('id'))
    markets = list(MarketDefinition.objects.filter(scenario=scenario).order_by('code'))
    # Three of the four teams buy, so the section has several rows and the
    # fourth team's absence is itself represented.
    for index, team in enumerate(teams[:3]):
        submission = DecisionSubmission.objects.get(team=team, round=round_obj)
        home = team.home_market or markets[0]

        for report_type in (rc.MARKETS, rc.PRODUCTS)[:1 + (index % 2)]:
            row, _ = DecisionResearchPurchase.objects.update_or_create(
                submission=submission, report_type=report_type,
                scope_key=rc.scope_key_for(report_type),
                defaults=dict(market=None,
                              price=rc.price_for(scenario, report_type)))
            created.append(row)

        row, _ = DecisionResearchPurchase.objects.update_or_create(
            submission=submission, report_type=rc.SEGMENTS,
            scope_key=rc.scope_key_for(rc.SEGMENTS, home.code),
            defaults=dict(market=home,
                          price=rc.price_for(scenario, rc.SEGMENTS)))
        created.append(row)

        for ordinal in range(1, 2 + (index % 2)):
            row, _ = DecisionResearchPurchase.objects.update_or_create(
                submission=submission, report_type=rc.ANALYST_QUERY,
                scope_key=str(ordinal),
                defaults=dict(market=None,
                              price=rc.price_for(scenario, rc.ANALYST_QUERY)))
            created.append(row)

    if not created:
        raise SurfaceEmpty('No research purchases were created.')
    return created


def seed_out_of_band_price(game, round_obj, scenario):
    """One price above the band's upper edge, on a genuinely banded row.

    "Banded" is the load-bearing word: the deadline only adjusts a price that
    has an anchor, and after the 2026-09-12 narrowing only a prior-round
    RESULT row is a `previous_round` anchor. So the row is chosen from
    `RoundResultProductMarket` at round 0 rather than assumed.
    """
    for team in Team.objects.filter(game=game).order_by('id'):
        submission = DecisionSubmission.objects.filter(
            team=team, round=round_obj).first()
        if not submission:
            continue
        for prior in (RoundResultProductMarket.objects
                      .filter(game=game, round_number=0, team=team)
                      .select_related('team_product', 'market')
                      .order_by('id')):
            band = band_rules.price_band(
                scenario, team, prior.team_product, prior.market,
                round_obj.round_number)
            if band.get('max') is None:
                continue
            if band.get('anchor_source') != band_rules.ANCHOR_PREVIOUS_ROUND:
                continue
            md = DecisionMarketing.objects.filter(
                submission=submission, team_product=prior.team_product,
                market=prior.market).first()
            if md is None:
                continue
            submitted = (band['max'] * D('2')).quantize(D('0.01'))
            md.retail_price = submitted
            md.save(update_fields=['retail_price'])
            return {
                'team': team.name, 'product': prior.team_product.name,
                'market': prior.market.code, 'submitted_price': str(submitted),
                'band_min': str(band['min']), 'band_max': str(band['max']),
                'anchor_price': str(band['anchor']),
                'anchor_source': band['anchor_source'],
                'expected_applied_price': str(band['max']),
            }
    raise SurfaceEmpty(
        'No product-market had a previous_round anchor, so no price could be '
        'put out of band. Round 0 results are missing.')


def seed_not_for_sale(game, round_obj, scenario, avoid):
    """A blank price on a product-market with no prior-round price.

    Asserts `blank_price(band) is None` before writing, because a row with a
    prior-round anchor would be filled at the floor and recorded under
    RULE_BLANK -- a different rule, and not the one this run is here to put in
    the envelope.
    """
    markets = list(MarketDefinition.objects.filter(scenario=scenario).order_by('code'))
    for team in Team.objects.filter(game=game).order_by('id'):
        submission = DecisionSubmission.objects.filter(
            team=team, round=round_obj).first()
        if not submission:
            continue
        for product in TeamProduct.objects.filter(team=team).order_by('id'):
            for market in markets:
                if (team.name, product.name, market.code) == avoid:
                    continue
                if RoundResultProductMarket.objects.filter(
                        game=game, team=team, team_product=product,
                        market=market, round_number__lt=round_obj.round_number
                ).exists():
                    continue
                band = band_rules.price_band(
                    scenario, team, product, market, round_obj.round_number)
                if band_rules.blank_price(band) is not None:
                    continue
                home = team.home_market or markets[0]
                md, _ = DecisionMarketing.objects.update_or_create(
                    submission=submission, team_product=product, market=market,
                    defaults=_marketing_defaults(
                        budget=D('10000000'), promo_share=D('0.30'),
                        price=None, volume=0, offset=0, index=0,
                        features=[], home=home))
                md.retail_price = None
                md.save(update_fields=['retail_price'])
                return {
                    'team': team.name, 'product': product.name,
                    'market': market.code,
                    'anchor_source': band['anchor_source'],
                    'blank_floor': None,
                    'decision_marketing_id': md.id,
                }
    raise SurfaceEmpty(
        'No product-market lacked a prior-round price, so no not-for-sale row '
        'could be created.')


def _section_rows(manifest_body, name):
    sections = (manifest_body or {}).get('sections', {})
    rows = sections.get(name)
    if rows is None:
        return None
    if isinstance(rows, dict):
        return len(rows)
    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', type=int)
    parser.add_argument('--teams', type=int, default=4)
    parser.add_argument('--name', default='V6-ENVELOPE-FIXTURE')
    parser.add_argument('--section-id', type=int, default=90601)
    parser.add_argument('--summary', help='Write a JSON summary here.')
    args = parser.parse_args()

    scenario = (Scenario.objects.get(pk=args.scenario) if args.scenario
                else Scenario.objects.order_by('id').first())
    call_command('initialize_game', scenario=scenario.id, teams=args.teams,
                 name=args.name, stdout=io.StringIO())
    game = Game.objects.filter(name=args.name).order_by('-id').first()
    game.section_id = args.section_id
    game.save(update_fields=['section_id'])

    round_obj = Round.objects.get(game=game, round_number=game.current_round)
    seed_round(game, round_obj, scenario)
    purchases = seed_research_purchases(game, round_obj, scenario)
    out_of_band = seed_out_of_band_price(game, round_obj, scenario)
    not_for_sale = seed_not_for_sale(
        game, round_obj, scenario,
        avoid=(out_of_band['team'], out_of_band['product'], out_of_band['market']))

    summary = {
        'game_id': game.id, 'scenario_id': scenario.id,
        'section_id': game.section_id, 'round_number': round_obj.round_number,
        'teams': args.teams,
        'seeded': {
            'research_purchases': len(purchases),
            'research_purchase_rows': [
                {'team': p.submission.team.name, 'report_type': p.report_type,
                 'scope_key': p.scope_key, 'price': str(p.price)}
                for p in purchases],
            'out_of_band': out_of_band,
            'not_for_sale': not_for_sale,
        },
    }

    from core.engine.advance_round import close_round, process_round
    round_obj.deadline = timezone.now()
    round_obj.save(update_fields=['deadline'])
    close_round(game.id, reason='v6-envelope-fixture')

    # --- the deadline actually did what the round was built to make it do ---
    adjusted = DecisionAuditEvent.objects.filter(
        round=round_obj, action=band_rules.ACTION_ADJUSTED)
    not_offered = DecisionAuditEvent.objects.filter(
        round=round_obj, action=band_rules.ACTION_NOT_OFFERED)
    summary['after_close'] = {
        'price_band_adjusted_events': adjusted.count(),
        'price_not_offered_events': not_offered.count(),
        'adjusted_payloads': [e.payload for e in adjusted.order_by('id')[:5]],
        'not_offered_payloads': [e.payload for e in not_offered.order_by('id')[:5]],
        'null_price_rows_remaining': DecisionMarketing.objects.filter(
            submission__round=round_obj, retail_price__isnull=True).count(),
    }
    if not adjusted.exists():
        raise SurfaceEmpty('close_round wrote no price_band_adjusted event.')
    if not not_offered.exists():
        raise SurfaceEmpty('close_round wrote no price_not_offered event.')

    process_round(game.id)
    manifest = Round.objects.get(pk=round_obj.pk).resolution_manifest

    counts = {}
    for name in ('decision_research_purchase', 'decision_marketing',
                 'decision_submission', 'financials', 'product_market'):
        counts[name] = _section_rows(manifest.output_manifest, name)
    input_audit = _section_rows(manifest.input_manifest, 'decision_audit_event')

    summary['manifest'] = {
        'schema_version': manifest.schema_version,
        'input_sha256': manifest.input_sha256,
        'output_sha256': manifest.output_sha256,
        'narrative_sha256': manifest.narrative_sha256,
        'code_revision': manifest.code_revision,
        'source_tree_sha256': manifest.source_tree_sha256,
        'backup_path': manifest.backup_path,
        'output_section_row_counts': counts,
        'input_decision_audit_event_rows': input_audit,
    }

    if manifest.schema_version != 6:
        raise SurfaceEmpty(
            f'Manifest is schema version {manifest.schema_version}, not 6.')
    if not counts.get('decision_research_purchase'):
        raise SurfaceEmpty(
            'decision_research_purchase is EMPTY in the output manifest. A '
            'replay of this round would prove nothing about the v6 change.')

    print(json.dumps(summary, indent=2, default=str))
    if args.summary:
        with open(args.summary, 'w', encoding='utf-8') as handle:
            json.dump(summary, handle, indent=2, sort_keys=True, default=str)


if __name__ == '__main__':
    main()
