"""
CC-31F Balance Verification: 4-round test with 3 teams (AFR, APAC, NA).
Team A (AFR): Home market revenue viability
Team B (APAC): Licensing, sanctions eligibility, trust penalties
Team C (NA): JV into APAC, foreign market profitability, repatriation costs
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models.core import Game, Team, Round
from core.models.team_state import TeamProduct, TeamProductMarket, TeamMarketPresence
from core.models.scenario import MarketDefinition, EntryModeDefinition
from core.models.decisions import (
    DecisionSubmission, DecisionBudgetAllocation, DecisionMarketing,
    DecisionMarketEntry, DecisionFinancing,
)
from core.models.cc31_models import TeamMarketCompliance, ComplianceInvestment
from core.models.results_financials import RoundResultFinancials, RoundResultMarketRevenue
from core.engine.advance_round import advance_round


def _mkt_defaults(price, volume, promo, market, strategy='hybrid'):
    """Build full DecisionMarketing defaults dict."""
    return {
        'retail_price': Decimal(str(price)),
        'production_volume': volume,
        'promotion_budget': Decimal(str(promo)),
        'campaign_focus_feature_ids': [],
        'channel_digital_pct': Decimal('0.40'),
        'channel_traditional_pct': Decimal('0.30'),
        'channel_trade_pct': Decimal('0.30'),
        'distribution_strategy': strategy,
        'distribution_investment': Decimal('0'),
        'production_source_market': market,
        'demand_estimate': volume,
    }


class Command(BaseCommand):
    help = 'CC-31F balance verification playthrough'

    def add_arguments(self, parser):
        parser.add_argument('--game', type=int, required=True)

    def handle(self, *args, **options):
        game = Game.objects.get(id=options['game'])
        scenario = game.scenario
        teams = list(Team.objects.filter(game=game).order_by('id'))
        markets = {m.code: m for m in MarketDefinition.objects.filter(scenario=scenario)}
        entry_modes = {}
        for em in EntryModeDefinition.objects.filter(scenario=scenario):
            key = em.name.lower()
            if 'licensing' in key:
                entry_modes['licensing'] = em
            elif 'joint venture' in key:
                entry_modes['jv'] = em
            elif 'export' in key:
                entry_modes['export'] = em

        team_a, team_b, team_c = teams[0], teams[1], teams[2]
        self.stdout.write(f'Game {game.id}: {game.name}')
        self.stdout.write(f'  Team A ({team_a.id}): home={team_a.home_market.code}')
        self.stdout.write(f'  Team B ({team_b.id}): home={team_b.home_market.code}')
        self.stdout.write(f'  Team C ({team_c.id}): home={team_c.home_market.code}')

        for round_num in range(1, 5):
            self.stdout.write(f'\n=== ROUND {round_num} ===')
            round_obj = Round.objects.get(game=game, round_number=round_num)
            if round_obj.status in ('pending', 'processed'):
                round_obj.status = 'open'
                round_obj.opened_at = timezone.now()
                round_obj.save()

            # --- TEAM A (AFR): Conservative home focus, low spend ---
            sub_a = self._sub(team_a, round_obj)
            products_a = list(TeamProduct.objects.filter(team=team_a))
            DecisionBudgetAllocation.objects.update_or_create(
                submission=sub_a,
                defaults={'rd_budget': 1500000, 'marketing_budget': 1000000, 'strategy_budget': 500000},
            )
            for p in products_a:
                price = 350 if 'One' in p.name else 180
                vol = 30000 if 'One' in p.name else 40000
                DecisionMarketing.objects.update_or_create(
                    submission=sub_a, team_product=p, market=markets['AFR'],
                    defaults=_mkt_defaults(price, vol, 500000, markets['AFR']),
                )
            sub_a.status = 'locked'
            sub_a.locked_at = timezone.now()
            sub_a.save()

            # --- TEAM B (APAC): Licensing, enters NA R1, zero compliance ---
            sub_b = self._sub(team_b, round_obj)
            products_b = list(TeamProduct.objects.filter(team=team_b))
            DecisionBudgetAllocation.objects.update_or_create(
                submission=sub_b,
                defaults={'rd_budget': 2000000, 'marketing_budget': 1500000, 'strategy_budget': 1000000},
            )
            for p in products_b:
                price = 500 if 'Pro' in p.name else 300
                DecisionMarketing.objects.update_or_create(
                    submission=sub_b, team_product=p, market=markets['APAC'],
                    defaults=_mkt_defaults(price, 25000, 500000, markets['APAC']),
                )
            if round_num == 1:
                DecisionMarketEntry.objects.update_or_create(
                    submission=sub_b, market=markets['NA'],
                    defaults={'entry_mode': entry_modes['licensing'], 'action': 'enter', 'initial_investment': 0},
                )
            if round_num >= 2:
                na_pres = TeamMarketPresence.objects.filter(team=team_b, market=markets['NA'], status='active').first()
                if na_pres:
                    for p in products_b:
                        TeamProductMarket.objects.get_or_create(
                            team_product=p, market=markets['NA'],
                            defaults={'first_offered_round': round_num},
                        )
                        price = 450 if 'Pro' in p.name else 250
                        DecisionMarketing.objects.update_or_create(
                            submission=sub_b, team_product=p, market=markets['NA'],
                            defaults=_mkt_defaults(price, 20000, 400000, markets['NA']),
                        )
            sub_b.status = 'locked'
            sub_b.locked_at = timezone.now()
            sub_b.save()

            # --- TEAM C (NA): JV into APAC R1, compliance investment ---
            sub_c = self._sub(team_c, round_obj)
            products_c = list(TeamProduct.objects.filter(team=team_c))
            DecisionBudgetAllocation.objects.update_or_create(
                submission=sub_c,
                defaults={'rd_budget': 2000000, 'marketing_budget': 2000000, 'strategy_budget': 1000000},
            )
            for p in products_c:
                price = 400 if 'X' in p.name else 200
                DecisionMarketing.objects.update_or_create(
                    submission=sub_c, team_product=p, market=markets['NA'],
                    defaults=_mkt_defaults(price, 30000, 600000, markets['NA']),
                )
            if round_num == 1:
                DecisionMarketEntry.objects.update_or_create(
                    submission=sub_c, market=markets['APAC'],
                    defaults={'entry_mode': entry_modes['jv'], 'action': 'enter', 'initial_investment': 5000000},
                )
            if round_num >= 2:
                apac_pres = TeamMarketPresence.objects.filter(team=team_c, market=markets['APAC'], status='active').first()
                if apac_pres:
                    for p in products_c:
                        TeamProductMarket.objects.get_or_create(
                            team_product=p, market=markets['APAC'],
                            defaults={'first_offered_round': round_num},
                        )
                        price = 350 if 'X' in p.name else 170
                        DecisionMarketing.objects.update_or_create(
                            submission=sub_c, team_product=p, market=markets['APAC'],
                            defaults=_mkt_defaults(price, 25000, 500000, markets['APAC']),
                        )
                    ComplianceInvestment.objects.update_or_create(
                        submission=sub_c, market=markets['APAC'],
                        defaults={'investment_amount': Decimal('2000000')},
                    )
            DecisionFinancing.objects.update_or_create(
                submission=sub_c,
                defaults={'new_debt': 0, 'debt_repayment': 0, 'new_equity': 0, 'dividend_per_share': 0},
            )
            sub_c.status = 'locked'
            sub_c.locked_at = timezone.now()
            sub_c.save()

            # Advance
            self.stdout.write(f'  Advancing round {round_num}...')
            try:
                advance_round(game.id)
                self.stdout.write(f'  Round {round_num} processed.')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  ERROR: {e}'))
                import traceback
                traceback.print_exc()
                return

        # === VALIDATION ===
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('VALIDATION')
        self.stdout.write('=' * 60)
        passed = failed = 0

        # Team A: AFR revenue
        self.stdout.write('\n--- Team A (AFR Home) ---')
        for rn in range(1, 5):
            fin = RoundResultFinancials.objects.filter(team=team_a, round_number=rn).first()
            if fin:
                self.stdout.write(f'  R{rn}: rev=${float(fin.total_revenue):,.0f}  net=${float(fin.net_income):,.0f}')

        r1_fin = RoundResultFinancials.objects.filter(team=team_a, round_number=1).first()
        r1_rev = float(r1_fin.total_revenue) if r1_fin else 0
        if r1_rev >= 500000:
            self.stdout.write(self.style.SUCCESS(f'  [PASS] R1 revenue ${r1_rev:,.0f} >= $500K'))
            passed += 1
        else:
            self.stdout.write(self.style.ERROR(f'  [FAIL] R1 revenue ${r1_rev:,.0f} < $500K'))
            failed += 1

        cum_rev = sum(
            float(f.total_revenue)
            for f in RoundResultFinancials.objects.filter(team=team_a, round_number__gte=1, round_number__lte=4)
        )
        if cum_rev >= 3000000:
            self.stdout.write(self.style.SUCCESS(f'  [PASS] 4-round cumulative ${cum_rev:,.0f} >= $3M'))
            passed += 1
        else:
            self.stdout.write(self.style.ERROR(f'  [FAIL] 4-round cumulative ${cum_rev:,.0f} < $3M'))
            failed += 1

        # Team B: Trust/sanctions
        self.stdout.write('\n--- Team B (APAC, Licensing) ---')
        tmc_na = TeamMarketCompliance.objects.filter(game=game, team=team_b, market=markets['NA']).first()
        if tmc_na and float(tmc_na.current_trust_multiplier) < 1.0:
            self.stdout.write(self.style.SUCCESS(f'  [PASS] Trust in NA = {float(tmc_na.current_trust_multiplier):.2f} < 1.0'))
            passed += 1
        else:
            trust = float(tmc_na.current_trust_multiplier) if tmc_na else 'N/A'
            self.stdout.write(self.style.ERROR(f'  [FAIL] Trust in NA = {trust}'))
            failed += 1

        from core.models.scenario import EventTemplateDefinition
        tech = EventTemplateDefinition.objects.filter(scenario=scenario, name='Technology Export Restrictions').first()
        if tech and float(tech.probability_per_round) >= 0.12:
            self.stdout.write(self.style.SUCCESS(f'  [PASS] Sanctions prob = {tech.probability_per_round}'))
            passed += 1
        else:
            self.stdout.write(self.style.ERROR(f'  [FAIL] Sanctions prob wrong'))
            failed += 1

        # Team C: JV, compliance, repatriation
        self.stdout.write('\n--- Team C (NA, JV in APAC) ---')
        for rn in range(1, 5):
            fin = RoundResultFinancials.objects.filter(team=team_c, round_number=rn).first()
            if fin:
                self.stdout.write(f'  R{rn}: rev=${float(fin.total_revenue):,.0f}  repat=${float(fin.repatriation_costs):,.0f}')

        tmc_apac = TeamMarketCompliance.objects.filter(game=game, team=team_c, market=markets['APAC']).first()
        if tmc_apac and float(tmc_apac.compliance_level) > 0:
            self.stdout.write(self.style.SUCCESS(f'  [PASS] APAC compliance = {float(tmc_apac.compliance_level):.2f}'))
            passed += 1
        else:
            self.stdout.write(self.style.ERROR(f'  [FAIL] APAC compliance = 0'))
            failed += 1

        jv_pres = TeamMarketPresence.objects.filter(team=team_c, market=markets['APAC']).first()
        if jv_pres and 'joint' in (jv_pres.entry_mode.name or '').lower():
            self.stdout.write(self.style.SUCCESS(f'  [PASS] JV entry confirmed'))
            passed += 1
        else:
            self.stdout.write(self.style.ERROR(f'  [FAIL] No JV in APAC'))
            failed += 1

        # Repatriation (informational — may be $0 if not yet profitable)
        any_repat = RoundResultFinancials.objects.filter(team=team_c, repatriation_costs__gt=0).exists()
        if any_repat:
            self.stdout.write(self.style.SUCCESS(f'  [PASS] Repatriation costs > $0'))
            passed += 1
        else:
            r4_mr = RoundResultMarketRevenue.objects.filter(team=team_c, round_number=4, market=markets['APAC']).first()
            apac_profit = float(r4_mr.market_profit) if r4_mr else 0
            self.stdout.write(f'  [INFO] Repatriation $0 — APAC profit R4: ${apac_profit:,.0f} (needs positive profit)')

        self.stdout.write(f'\n=== {passed} PASSED, {failed} FAILED ===')

    def _sub(self, team, round_obj):
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=round_obj,
            defaults={'status': 'draft'},
        )
        return sub
