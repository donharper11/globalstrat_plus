"""
CC-31I: Full 8-Round Integration Test — 5 Markets, 5 Home Markets.

Creates a fresh game, scripts 8 rounds of decisions for 5 teams following
the strategy profiles in the spec, advances each round through the engine,
and collects validation data for the report.
"""
import json
import traceback
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone

from core.models.core import Game, Team, Round
from core.models.scenario import (
    Scenario, MarketDefinition, EntryModeDefinition,
    PlatformGenerationDefinition, FeatureDefinition,
    StrategyOptionDefinition, AcquisitionTarget,
)
from core.models.decisions import (
    DecisionSubmission, DecisionBudgetAllocation,
    DecisionRDInvestment, DecisionPlatformDevelopment,
    DecisionProductCreate, DecisionProductRetire,
    DecisionMarketing, DecisionMarketEntry,
    DecisionFinancing, DecisionPlant, DecisionPartnership,
    DecisionAcquisition, DecisionESG, DecisionEventResponse,
    DecisionResearchAllocation,
)
from core.models.talent import DecisionTalent
from core.models.cc31_models import (
    TalentAllocation, ComplianceInvestment, TeamMarketCompliance,
)
from core.models.team_state import (
    TeamPlatform, TeamPlatformFeatureLevel,
    TeamProduct, TeamProductMarket,
    TeamMarketPresence, TeamPartnership as TeamPartnershipState,
    TeamPlant, TeamAcquisition,
)
from core.models.results_financials import (
    RoundResultFinancials, RoundResultPerformanceIndex,
    RoundResultMarketRevenue,
)
from core.models.results import EventInstance, ActiveModifier, RoundResultAdoption
from core.models.cc26_models import AIInvestorHolding
from core.models.cc32f_models import GovernmentSatisfaction, GovernmentAction


class Command(BaseCommand):
    help = 'CC-31I: Full 8-round integration test'

    def handle(self, *args, **options):
        self.results = {
            'setup_checks': [],
            'round_data': {},
            'trust_trajectories': {},
            'events': [],
            'bugs_found': [],
            'round_errors': [],
        }

        try:
            self._setup_game()
            self._verify_setup()

            for round_num in range(1, 9):
                self.stdout.write(f'\n{"="*60}')
                self.stdout.write(f'  ROUND {round_num}')
                self.stdout.write(f'{"="*60}')
                self._script_round_decisions(round_num)
                success = self._advance_round(round_num)
                if success:
                    self._collect_round_data(round_num)
                else:
                    self.stdout.write(self.style.ERROR(
                        f'  Round {round_num} failed — stopping.'
                    ))
                    break

            self._final_summary()

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\nFATAL: {e}'))
            traceback.print_exc()

    # ===================================================================
    # SETUP
    # ===================================================================

    def _setup_game(self):
        self.stdout.write('\n--- Setting up fresh game ---')

        # Find scenario
        self.scenario = Scenario.objects.filter(
            name__icontains='Consumer Electronics',
        ).order_by('-id').first()
        if not self.scenario:
            raise RuntimeError('No Consumer Electronics scenario found. Run load_scenario first.')
        self.stdout.write(f'  Scenario: {self.scenario.name} (ID: {self.scenario.id})')

        # Reload scenario to ensure clean state
        self.stdout.write('  Reloading scenario...')
        call_command('load_scenario', 'electronics', '--flush', '--markets', '5', verbosity=0)
        self.scenario = Scenario.objects.filter(
            name__icontains='Consumer Electronics',
        ).order_by('-id').first()
        self.stdout.write(f'  Scenario reloaded (ID: {self.scenario.id})')

        # Initialize game
        call_command(
            'initialize_game',
            '--scenario', str(self.scenario.id),
            '--teams', '5',
            '--name', 'CC-31I Full Integration Test',
            '--home_markets', 'NA,APAC,EU,LATAM,AFR',
        )

        self.game = Game.objects.filter(
            scenario=self.scenario, name='CC-31I Full Integration Test',
        ).order_by('-id').first()
        self.stdout.write(f'  Game created (ID: {self.game.id})')

        # Cache lookups
        self._cache_lookups()

    def _cache_lookups(self):
        """Cache all scenario fixture IDs for decision scripting."""
        s = self.scenario

        # Markets: code -> id
        self.markets = {}
        for m in MarketDefinition.objects.filter(scenario=s):
            self.markets[m.code] = m.id

        # Entry modes: code -> id
        self.entry_modes = {}
        for e in EntryModeDefinition.objects.filter(scenario=s):
            self.entry_modes[e.code] = e.id

        # Platform generations: gen_order -> id
        self.platform_gens = {}
        for p in PlatformGenerationDefinition.objects.filter(scenario=s):
            self.platform_gens[p.generation_order] = p.id

        # Features: code -> id
        self.features = {}
        for f in FeatureDefinition.objects.filter(scenario=s, layer='platform'):
            self.features[f.code] = f.id

        # Strategy options: code -> id
        self.strategy_options = {}
        for so in StrategyOptionDefinition.objects.filter(scenario=s):
            self.strategy_options[so.code] = so.id

        # Acquisition targets: market_code -> id
        self.acq_targets = {}
        for at in AcquisitionTarget.objects.filter(scenario=s):
            self.acq_targets[at.market.code] = at.id

        # Teams: team_number (1-5) -> Team object
        self.teams = {}
        for t in Team.objects.filter(game=self.game).order_by('id'):
            num = int(t.name.split()[-1])
            self.teams[num] = t

        self.stdout.write(f'  Markets: {list(self.markets.keys())}')
        self.stdout.write(f'  Teams: {[(n, t.home_market.code) for n, t in self.teams.items()]}')

    # ===================================================================
    # VERIFY SETUP (Part A2 checks)
    # ===================================================================

    def _verify_setup(self):
        self.stdout.write('\n--- Verifying setup (Part A2) ---')
        checks = self.results['setup_checks']

        # A2.1: 5 teams with correct home markets
        expected_homes = {1: 'NA', 2: 'APAC', 3: 'EU', 4: 'LATAM', 5: 'AFR'}
        all_ok = True
        for num, code in expected_homes.items():
            t = self.teams[num]
            actual = t.home_market.code if t.home_market else 'NONE'
            if actual != code:
                all_ok = False
                self.stdout.write(f'  FAIL: Team {num} home={actual}, expected {code}')
        checks.append(('5 teams with correct home markets', all_ok))
        self._check(all_ok, 'A2.1: 5 teams with correct home markets')

        # A2.2: Products in home market
        ok = True
        for num, t in self.teams.items():
            for tp in TeamProduct.objects.filter(team=t, status='active'):
                tpm = TeamProductMarket.objects.filter(team_product=tp).first()
                if tpm and tpm.market_id != t.home_market_id:
                    ok = False
                    self.stdout.write(f'  FAIL: {t.name} product {tp.name} in wrong market')
        checks.append(('Products in home market', ok))
        self._check(ok, 'A2.2: Products placed in home market')

        # A2.3: TeamMarketCompliance for home market
        ok = True
        for num, t in self.teams.items():
            tmc = TeamMarketCompliance.objects.filter(
                game=self.game, team=t, market=t.home_market,
            ).first()
            if not tmc or float(tmc.current_trust_multiplier) != 1.0:
                ok = False
        checks.append(('Home market compliance trust=1.0', ok))
        self._check(ok, 'A2.3: Home market compliance trust=1.0')

        # A2.4: Africa shows NGN
        afr = MarketDefinition.objects.get(scenario=self.scenario, code='AFR')
        ok = afr.currency_code == 'NGN'
        checks.append(('Africa currency is NGN', ok))
        self._check(ok, f'A2.4: Africa currency={afr.currency_code}')

        # A2.5: 5 acquisition targets
        n_acq = AcquisitionTarget.objects.filter(scenario=self.scenario).count()
        checks.append(('5 acquisition targets', n_acq == 5))
        self._check(n_acq == 5, f'A2.5: {n_acq} acquisition targets')

        # A2.6: 5 markets loaded
        n_markets = MarketDefinition.objects.filter(scenario=self.scenario).count()
        checks.append(('5 markets loaded', n_markets == 5))
        self._check(n_markets == 5, f'A2.6: {n_markets} markets')

    # ===================================================================
    # DECISION SCRIPTING
    # ===================================================================

    def _script_round_decisions(self, round_num):
        """Create decisions for all 5 teams for this round."""
        round_obj = Round.objects.get(game=self.game, round_number=round_num)
        self.current_round_obj = round_obj

        for team_num in range(1, 6):
            team = self.teams[team_num]
            method = getattr(self, f'_team{team_num}_round{round_num}', None)
            if method:
                try:
                    method(team, round_obj)
                    self.stdout.write(f'  Team {team_num} decisions scripted')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(
                        f'  Team {team_num} decisions FAILED: {e}'
                    ))
                    self.results['bugs_found'].append(
                        f'R{round_num} T{team_num} decision scripting: {e}'
                    )
                    # Create minimal submission so engine can proceed
                    self._create_minimal_submission(team, round_obj)
            else:
                # Fallback: create minimal submission (just marketing existing products)
                self._create_default_submission(team, round_obj, round_num)
                self.stdout.write(f'  Team {team_num} default decisions')

    def _create_submission(self, team, round_obj):
        """Create a DecisionSubmission and return it."""
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=round_obj,
            defaults={'status': 'draft'},
        )
        return sub

    def _create_minimal_submission(self, team, round_obj):
        """Create absolute minimum submission."""
        sub = self._create_submission(team, round_obj)
        DecisionBudgetAllocation.objects.get_or_create(
            submission=sub,
            defaults={
                'rd_budget': 1000000,
                'marketing_budget': 2000000,
                'strategy_budget': 500000,
            },
        )
        return sub

    def _create_default_submission(self, team, round_obj, round_num):
        """Create submission with marketing for existing products."""
        sub = self._create_submission(team, round_obj)
        self._add_budget(sub)
        self._add_marketing_for_active_products(sub, team)
        self._add_default_talent(sub, team)
        return sub

    def _add_budget(self, sub, rd=2000000, mkt=3000000, strat=1000000, research=500000):
        DecisionBudgetAllocation.objects.get_or_create(
            submission=sub,
            defaults={
                'rd_budget': rd,
                'marketing_budget': mkt,
                'strategy_budget': strat,
                'research_budget': research,
            },
        )

    def _add_marketing_for_active_products(self, sub, team, extra_markets=None):
        """Create marketing decisions for all active products in active markets."""
        home = team.home_market
        active_presences = TeamMarketPresence.objects.filter(
            team=team, status='active',
        ).select_related('market')
        active_market_ids = set(p.market_id for p in active_presences)

        if extra_markets:
            for code in extra_markets:
                active_market_ids.add(self.markets[code])

        products = TeamProduct.objects.filter(team=team, status='active')
        for product in products:
            product_markets = TeamProductMarket.objects.filter(
                team_product=product, is_active=True,
            )
            for tpm in product_markets:
                if tpm.market_id not in active_market_ids:
                    continue
                self._add_marketing_decision(
                    sub, product, tpm.market_id, home.id,
                    product.positioning,
                )

    def _add_marketing_decision(self, sub, product, market_id, source_market_id,
                                 positioning, price_override=None, volume_override=None,
                                 promo_override=None):
        """Create a single marketing decision."""
        prices = {'budget': 250, 'mainstream': 420, 'premium': 700, 'ultra_premium': 1000}
        volumes = {'budget': 25000, 'mainstream': 20000, 'premium': 12000, 'ultra_premium': 8000}
        promos = {'budget': 200000, 'mainstream': 300000, 'premium': 400000, 'ultra_premium': 500000}

        price = price_override or prices.get(positioning, 400)
        volume = volume_override or volumes.get(positioning, 20000)
        promo = promo_override or promos.get(positioning, 300000)

        # Get top features for campaign focus
        platform = product.team_platform
        top_features = TeamPlatformFeatureLevel.objects.filter(
            team_platform=platform, current_level__gt=0,
        ).order_by('-current_level')[:3]
        focus_ids = [fl.feature_id for fl in top_features]

        # Check if already exists
        if DecisionMarketing.objects.filter(
            submission=sub, team_product=product, market_id=market_id,
        ).exists():
            return

        DecisionMarketing.objects.create(
            submission=sub,
            team_product=product,
            market_id=market_id,
            retail_price=price,
            promotion_budget=promo,
            campaign_focus_feature_ids=focus_ids,
            channel_digital_pct=Decimal('0.4000'),
            channel_traditional_pct=Decimal('0.3000'),
            channel_trade_pct=Decimal('0.3000'),
            distribution_strategy='hybrid',
            distribution_investment=200000,
            sales_team_count=10,
            distribution_channel_detail={'direct_online': 5, 'selective_retail': 3, 'mass_retail': 2},
            production_volume=volume,
            production_source_market_id=source_market_id,
            demand_estimate=int(volume * 1.5),
        )

    def _add_default_talent(self, sub, team, market_allocs=None):
        """Create talent decision with allocations."""
        home_code = team.home_market.code
        active_markets = list(
            TeamMarketPresence.objects.filter(
                team=team, status='active',
            ).values_list('market__code', flat=True)
        )

        # Default: keep 50% at HQ, distribute rest
        rd, com, ops = 50, 30, 40

        if not hasattr(sub, '_talent_created'):
            DecisionTalent.objects.get_or_create(
                submission=sub,
                defaults={
                    'rd_headcount': rd,
                    'rd_salary_level': 3,
                    'commercial_headcount': com,
                    'commercial_salary_level': 3,
                    'operations_headcount': ops,
                    'operations_salary_level': 3,
                },
            )
            sub._talent_created = True

        if market_allocs is None:
            market_allocs = self._auto_talent_alloc(active_markets, home_code, rd, com, ops)

        # Clear existing
        TalentAllocation.objects.filter(submission=sub).delete()

        for pool, hq, alloc in market_allocs:
            TalentAllocation.objects.create(
                submission=sub,
                talent_pool=pool,
                hq_count=hq,
                market_allocation=alloc,
            )

    def _auto_talent_alloc(self, active_markets, home_code, rd=50, com=30, ops=40):
        """Auto-generate balanced talent allocations."""
        result = []
        for pool, total in [('rd', rd), ('commercial', com), ('operations', ops)]:
            hq = max(int(total * 0.4), int(total * 0.2) + 1)
            remaining = total - hq

            alloc = {}
            if active_markets:
                per_market = max(1, remaining // len(active_markets))
                for m in active_markets:
                    alloc[m] = per_market
                # Fix rounding
                allocated = sum(alloc.values())
                diff = remaining - allocated
                if diff != 0:
                    first = active_markets[0]
                    alloc[first] = alloc[first] + diff
            else:
                alloc[home_code] = remaining

            result.append((pool, hq, alloc))
        return result

    def _talent_alloc(self, active_markets, home_code, rd=50, com=30, ops=40, hq_pct=0.5):
        """Generate talent allocations with custom HQ percentage."""
        result = []
        for pool, total in [('rd', rd), ('commercial', com), ('operations', ops)]:
            hq = max(int(total * hq_pct), int(total * 0.2) + 1)
            remaining = total - hq

            alloc = {}
            if active_markets:
                per_market = max(1, remaining // len(active_markets))
                for m in active_markets:
                    alloc[m] = per_market
                allocated = sum(alloc.values())
                diff = remaining - allocated
                if diff != 0:
                    alloc[active_markets[0]] = alloc[active_markets[0]] + diff
            else:
                alloc[home_code] = remaining

            result.append((pool, hq, alloc))
        return result

    # ===================================================================
    # TEAM 1 — NA HQ: "The Methodical Globalizer"
    # ===================================================================

    def _team1_round1(self, team, rnd):
        """R1: Optimize NA. R&D in-house (2 features). ESG $1M."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=3000000, mkt=3000000, strat=1000000)
        self._add_marketing_for_active_products(sub, team)

        # R&D: 2 features in-house
        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['processing_power'],
            method='in_house', amount=300000, target_level=10,
        )
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['battery_life'],
            method='in_house', amount=200000, target_level=6,
        )

        # ESG
        DecisionESG.objects.create(
            submission=sub,
            environmental_investment=600000,
            social_investment=400000,
        )

        # Talent: 70% HQ, rest in NA
        self._add_default_talent(sub, team,
            self._talent_alloc(['NA'], 'NA', hq_pct=0.7))

    def _team1_round2(self, team, rnd):
        """R2: Enter EU via Subsidiary. Compliance EU: $1M."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=3000000, strat=2000000)
        self._add_marketing_for_active_products(sub, team)

        # Enter EU via subsidiary
        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['EU'],
            entry_mode_id=self.entry_modes['subsidiary'],
            initial_investment=15000000,
            action='enter',
        )

        # Compliance EU
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'],
            investment_amount=1000000,
        )

        DecisionESG.objects.create(sub=sub, environmental_investment=500000, social_investment=500000) if False else None
        self._add_default_talent(sub, team,
            self._talent_alloc(['NA', 'EU'], 'NA', hq_pct=0.6))

    def _team1_round3(self, team, rnd):
        """R3: EU activates. Launch product in EU. Enter SA via Export. Compliance EU: $1.5M."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=2000000)

        # Add EU product market for existing products
        for product in TeamProduct.objects.filter(team=team, status='active'):
            eu_market = self.markets['EU']
            TeamProductMarket.objects.get_or_create(
                team_product=product, market_id=eu_market,
                defaults={'first_offered_round': 3},
            )

        self._add_marketing_for_active_products(sub, team)

        # Enter SA via export
        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['LATAM'],
            entry_mode_id=self.entry_modes['export'],
            initial_investment=500000,
            action='enter',
        )

        # Compliance
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'],
            investment_amount=1500000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['NA', 'EU', 'LATAM'], 'NA', hq_pct=0.5))

    def _team1_round4(self, team, rnd):
        """R4: Acquire PioneerTech (NA). Enter WA via JV. Compliance SA+WA."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=3000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        # Acquire PioneerTech in NA
        DecisionAcquisition.objects.create(
            submission=sub,
            acquisition_target_id=self.acq_targets['NA'],
        )

        # Enter WA via JV
        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['AFR'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000,
            action='enter',
        )

        # Compliance
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            investment_amount=1000000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['AFR'],
            investment_amount=500000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['NA', 'EU', 'LATAM', 'AFR'], 'NA', hq_pct=0.44))

    def _team1_round5(self, team, rnd):
        """R5: Build plant in EU. Expand SA to JV. Gen 2 in-house. Compliance all foreign."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=5000000, mkt=3000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        # Plant in EU
        if MarketDefinition.objects.get(id=self.markets['EU']).allows_manufacturing:
            DecisionPlant.objects.create(
                submission=sub, market_id=self.markets['EU'],
                action='build', capacity_units=50000,
            )

        # Gen 2 platform development
        DecisionPlatformDevelopment.objects.create(
            submission=sub,
            platform_generation_id=self.platform_gens[2],
            method='in_house',
            committed_cost=15000000,
            platform_name='Team1 Gen2',
        )

        # Compliance all foreign
        for code in ['EU', 'LATAM', 'AFR']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code],
                investment_amount=750000,
            )

        self._add_default_talent(sub, team,
            self._talent_alloc(['NA', 'EU', 'LATAM', 'AFR'], 'NA', hq_pct=0.4))

    def _team1_round6(self, team, rnd):
        """R6: 4 markets operational. Increase dividends. Deepen localization."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=2000000)
        self._add_marketing_for_active_products(sub, team)

        # Dividends
        DecisionFinancing.objects.create(
            submission=sub, dividend_per_share=Decimal('0.50'),
        )

        # Compliance
        for code in ['EU', 'LATAM', 'AFR']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code],
                investment_amount=800000,
            )

        self._add_default_talent(sub, team,
            self._talent_alloc(['NA', 'EU', 'LATAM', 'AFR'], 'NA', hq_pct=0.35))

    def _team1_round7(self, team, rnd):
        """R7: Gen 2 products in EU and SA. Optimize pricing."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=5000000, strat=1000000)
        self._add_marketing_for_active_products(sub, team)

        # Compliance
        for code in ['EU', 'LATAM', 'AFR']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code],
                investment_amount=600000,
            )

        DecisionFinancing.objects.create(
            submission=sub, dividend_per_share=Decimal('0.60'),
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['NA', 'EU', 'LATAM', 'AFR'], 'NA', hq_pct=0.33))

    def _team1_round8(self, team, rnd):
        """R8: Final optimization. Maximize performance index. Dividend payout."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=1000000, mkt=5000000, strat=1000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionFinancing.objects.create(
            submission=sub, dividend_per_share=Decimal('0.80'),
        )

        for code in ['EU', 'LATAM', 'AFR']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code],
                investment_amount=500000,
            )

        self._add_default_talent(sub, team,
            self._talent_alloc(['NA', 'EU', 'LATAM', 'AFR'], 'NA', hq_pct=0.33))

    # ===================================================================
    # TEAM 2 — APAC HQ: "The Aggressive Licensor"
    # ===================================================================

    def _team2_round1(self, team, rnd):
        """R1: Optimize EA. R&D: 3 features via License. Enter NA via Export."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=4000000, mkt=3000000, strat=1000000)
        self._add_marketing_for_active_products(sub, team)

        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        # 3 licensed features
        for feat_code in ['processing_power', 'app_ecosystem', 'ai_features']:
            feat_id = self.features.get(feat_code)
            if feat_id:
                DecisionRDInvestment.objects.create(
                    submission=sub, team_platform=platform,
                    feature_id=feat_id,
                    method='license', amount=400000,
                )

        # Enter NA via export
        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['NA'],
            entry_mode_id=self.entry_modes['export'],
            initial_investment=500000,
            action='enter',
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['APAC', 'NA'], 'APAC', hq_pct=0.6))

    def _team2_round2(self, team, rnd):
        """R2: Enter EU via Licensing. Enter SA via JV. More licensed R&D. $0 compliance."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=4000000, mkt=4000000, strat=2000000)

        # Add NA product markets
        for product in TeamProduct.objects.filter(team=team, status='active'):
            TeamProductMarket.objects.get_or_create(
                team_product=product, market_id=self.markets['NA'],
                defaults={'first_offered_round': 2},
            )
        self._add_marketing_for_active_products(sub, team)

        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['EU'],
            entry_mode_id=self.entry_modes['licensing'],
            initial_investment=1000000,
            action='enter',
        )
        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['LATAM'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000,
            action='enter',
        )

        # More licensed R&D
        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        for feat_code in ['battery_life', 'durability']:
            DecisionRDInvestment.objects.create(
                submission=sub, team_platform=platform,
                feature_id=self.features[feat_code],
                method='license', amount=300000,
            )

        # Zero compliance
        self._add_default_talent(sub, team,
            self._talent_alloc(['APAC', 'NA', 'EU', 'LATAM'], 'APAC', hq_pct=0.5))

    def _team2_round3(self, team, rnd):
        """R3: Enter WA via JV. Products in all 5 markets. Price aggressively. Token compliance."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=3000000, mkt=5000000, strat=2000000)

        # Enter WA via JV
        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['AFR'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000,
            action='enter',
        )

        # Add product markets for all new markets
        for product in TeamProduct.objects.filter(team=team, status='active'):
            for code in ['EU', 'LATAM', 'AFR']:
                TeamProductMarket.objects.get_or_create(
                    team_product=product, market_id=self.markets[code],
                    defaults={'first_offered_round': 3},
                )
        self._add_marketing_for_active_products(sub, team)

        # Token compliance
        for code in ['NA', 'EU', 'LATAM', 'AFR']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code],
                investment_amount=200000,
            )

        self._add_default_talent(sub, team,
            self._talent_alloc(['APAC', 'NA', 'EU', 'LATAM', 'AFR'], 'APAC', hq_pct=0.42))

    def _team2_round4(self, team, rnd):
        """R4: Acquire AsiaElec (APAC, Brand Preservation). Gen 2 via License."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=5000000, mkt=4000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionAcquisition.objects.create(
            submission=sub,
            acquisition_target_id=self.acq_targets['APAC'],
        )

        # Gen 2 via license
        DecisionPlatformDevelopment.objects.create(
            submission=sub,
            platform_generation_id=self.platform_gens[2],
            method='license',
            committed_cost=35000000,
            platform_name='Team2 Gen2 Licensed',
        )

        # Token compliance
        for code in ['NA', 'EU', 'LATAM', 'AFR']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code],
                investment_amount=200000,
            )

        self._add_default_talent(sub, team,
            self._talent_alloc(['APAC', 'NA', 'EU', 'LATAM', 'AFR'], 'APAC', hq_pct=0.42))

    def _team2_round5(self, team, rnd):
        """R5: High licensed dependency. Continue expansion."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=3000000, mkt=5000000, strat=2000000)
        self._add_marketing_for_active_products(sub, team)

        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['connectivity'],
            method='license', amount=500000,
        )

        for code in ['NA', 'EU', 'LATAM', 'AFR']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code],
                investment_amount=200000,
            )

        self._add_default_talent(sub, team,
            self._talent_alloc(['APAC', 'NA', 'EU', 'LATAM', 'AFR'], 'APAC', hq_pct=0.42))

    def _team2_round6(self, team, rnd):
        """R6: Start converting licensed features to in-house."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=4000000, mkt=5000000, strat=1000000)
        self._add_marketing_for_active_products(sub, team)

        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['product_design'],
            method='in_house', amount=300000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['APAC', 'NA', 'EU', 'LATAM', 'AFR'], 'APAC', hq_pct=0.42))

    # Rounds 7-8 use default submission (continue marketing all markets)

    # ===================================================================
    # TEAM 3 — EU HQ: "The ESG Champion"
    # ===================================================================

    def _team3_round1(self, team, rnd):
        """R1: Optimize EU. Heavy ESG ($3M). R&D in-house: sustainable_materials + product_design."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=3000000, mkt=3000000, strat=1000000)
        self._add_marketing_for_active_products(sub, team)

        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['sustainable_materials'],
            method='in_house', amount=300000,
        )
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['product_design'],
            method='in_house', amount=300000,
        )

        DecisionESG.objects.create(
            submission=sub,
            environmental_investment=2000000,
            social_investment=1000000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['EU'], 'EU', hq_pct=0.6))

    def _team3_round2(self, team, rnd):
        """R2: Enter SA via JV + Local Strategic Partner. Compliance SA: $1.5M."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=3000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['LATAM'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000,
            action='enter',
        )

        # Local Strategic Partner in SA
        DecisionPartnership.objects.create(
            submission=sub,
            market_id=self.markets['LATAM'],
            strategy_option_id=self.strategy_options['local_strategic_latam'],
            annual_investment=600000,
            action='establish',
        )

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            investment_amount=1500000,
        )

        DecisionESG.objects.create(
            submission=sub,
            environmental_investment=1500000,
            social_investment=1000000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['EU', 'LATAM'], 'EU', hq_pct=0.5))

    def _team3_round3(self, team, rnd):
        """R3: Enter NA via Export. Sustainability products."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=2000000)

        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['NA'],
            entry_mode_id=self.entry_modes['export'],
            initial_investment=500000,
            action='enter',
        )

        # Add product markets for SA and NA
        for product in TeamProduct.objects.filter(team=team, status='active'):
            for code in ['LATAM', 'NA']:
                TeamProductMarket.objects.get_or_create(
                    team_product=product, market_id=self.markets[code],
                    defaults={'first_offered_round': 3},
                )
        self._add_marketing_for_active_products(sub, team)

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            investment_amount=1500000,
        )

        DecisionESG.objects.create(
            submission=sub,
            environmental_investment=1500000,
            social_investment=500000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['EU', 'LATAM', 'NA'], 'EU', hq_pct=0.44))

    def _team3_round4(self, team, rnd):
        """R4: Acquire TechSul (LATAM, Brand Preservation). Gen 2 in-house."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=5000000, mkt=4000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionAcquisition.objects.create(
            submission=sub,
            acquisition_target_id=self.acq_targets['LATAM'],
        )

        DecisionPlatformDevelopment.objects.create(
            submission=sub,
            platform_generation_id=self.platform_gens[2],
            method='in_house',
            committed_cost=15000000,
            platform_name='Team3 Gen2 Sustainable',
        )

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            investment_amount=1500000,
        )

        DecisionESG.objects.create(
            submission=sub,
            environmental_investment=1500000,
            social_investment=1000000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['EU', 'LATAM', 'NA'], 'EU', hq_pct=0.44))

    def _team3_round5(self, team, rnd):
        """R5: Enter WA via Subsidiary. Heavy compliance WA: $2M."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['AFR'],
            entry_mode_id=self.entry_modes['subsidiary'],
            initial_investment=15000000,
            action='enter',
        )

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['AFR'],
            investment_amount=2000000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            investment_amount=1000000,
        )

        DecisionESG.objects.create(
            submission=sub,
            environmental_investment=1000000,
            social_investment=500000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['EU', 'LATAM', 'NA', 'AFR'], 'EU', hq_pct=0.36))

    def _team3_round6(self, team, rnd):
        """R6: GreenHorizon buying. ESG compounding."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=5000000, strat=2000000)
        self._add_marketing_for_active_products(sub, team)

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['AFR'],
            investment_amount=1500000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            investment_amount=1000000,
        )

        DecisionESG.objects.create(
            submission=sub,
            environmental_investment=1000000,
            social_investment=500000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['EU', 'LATAM', 'NA', 'AFR'], 'EU', hq_pct=0.36))

    # Rounds 7-8 use default (continue marketing + ESG)

    # ===================================================================
    # TEAM 4 — LATAM HQ: "The Regional Champion"
    # ===================================================================

    def _team4_round1(self, team, rnd):
        """R1: Optimize SA. Build plant ($14M). R&D in-house."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=3000000, mkt=3000000, strat=2000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionPlant.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            action='build', capacity_units=55000,
        )

        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['sustainable_materials'],
            method='in_house', amount=200000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['LATAM'], 'LATAM', hq_pct=0.6))

    def _team4_round2(self, team, rnd):
        """R2: Enter EU via JV + Local Strategic Partner. Compliance EU: $1M."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=3000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['EU'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000,
            action='enter',
        )

        DecisionPartnership.objects.create(
            submission=sub,
            market_id=self.markets['EU'],
            strategy_option_id=self.strategy_options['local_strategic_eu'],
            annual_investment=900000,
            action='establish',
        )

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'],
            investment_amount=1000000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['LATAM', 'EU'], 'LATAM', hq_pct=0.5))

    def _team4_round3(self, team, rnd):
        """R3: Enter WA via JV. Compliance WA: $1M."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=2000000)

        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['AFR'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000,
            action='enter',
        )

        for product in TeamProduct.objects.filter(team=team, status='active'):
            for code in ['EU', 'AFR']:
                TeamProductMarket.objects.get_or_create(
                    team_product=product, market_id=self.markets[code],
                    defaults={'first_offered_round': 3},
                )
        self._add_marketing_for_active_products(sub, team)

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['AFR'],
            investment_amount=1000000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'],
            investment_amount=800000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['LATAM', 'EU', 'AFR'], 'LATAM', hq_pct=0.44))

    def _team4_round4(self, team, rnd):
        """R4: Attempt AfriConnect (WA, Brand Preservation). Compete with Team 5."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        # Compete for AfriConnect
        DecisionAcquisition.objects.create(
            submission=sub,
            acquisition_target_id=self.acq_targets['AFR'],
        )

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['AFR'],
            investment_amount=1000000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'],
            investment_amount=800000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['LATAM', 'EU', 'AFR'], 'LATAM', hq_pct=0.44))

    def _team4_round5(self, team, rnd):
        """R5: Enter NA via Export. Continue deepening."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=2000000)

        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['NA'],
            entry_mode_id=self.entry_modes['export'],
            initial_investment=500000,
            action='enter',
        )

        for product in TeamProduct.objects.filter(team=team, status='active'):
            TeamProductMarket.objects.get_or_create(
                team_product=product, market_id=self.markets['NA'],
                defaults={'first_offered_round': 5},
            )
        self._add_marketing_for_active_products(sub, team)

        for code in ['EU', 'AFR', 'NA']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code],
                investment_amount=800000,
            )

        self._add_default_talent(sub, team,
            self._talent_alloc(['LATAM', 'EU', 'AFR', 'NA'], 'LATAM', hq_pct=0.36))

    # Rounds 6-8 use default (continue marketing existing markets)

    # ===================================================================
    # TEAM 5 — AFR HQ: "The Underdog"
    # ===================================================================

    def _team5_round1(self, team, rnd):
        """R1: Optimize WA. ALL R&D in-house (tech sovereignty). Compliance WA: $500K."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=3000000, mkt=3000000, strat=1000000)
        self._add_marketing_for_active_products(sub, team)

        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['processing_power'],
            method='in_house', amount=300000,
        )
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['battery_life'],
            method='in_house', amount=200000,
        )

        # Compliance even at home (institutional building)
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['AFR'],
            investment_amount=500000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['AFR'], 'AFR', hq_pct=0.7))

    def _team5_round2(self, team, rnd):
        """R2: Enter SA via JV + Local Strategic Partner. Compliance SA: $2M."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=3000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['LATAM'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000,
            action='enter',
        )

        DecisionPartnership.objects.create(
            submission=sub,
            market_id=self.markets['LATAM'],
            strategy_option_id=self.strategy_options['local_strategic_latam'],
            annual_investment=600000,
            action='establish',
        )

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            investment_amount=2000000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['AFR', 'LATAM'], 'AFR', hq_pct=0.56))

    def _team5_round3(self, team, rnd):
        """R3: Enter EU via Export + Local Strategic Partner. Compliance EU: $2M."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=3000000)

        DecisionMarketEntry.objects.create(
            submission=sub,
            market_id=self.markets['EU'],
            entry_mode_id=self.entry_modes['export'],
            initial_investment=500000,
            action='enter',
        )

        DecisionPartnership.objects.create(
            submission=sub,
            market_id=self.markets['EU'],
            strategy_option_id=self.strategy_options['local_strategic_eu'],
            annual_investment=900000,
            action='establish',
        )

        for product in TeamProduct.objects.filter(team=team, status='active'):
            for code in ['LATAM', 'EU']:
                TeamProductMarket.objects.get_or_create(
                    team_product=product, market_id=self.markets[code],
                    defaults={'first_offered_round': 3},
                )
        self._add_marketing_for_active_products(sub, team)

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'],
            investment_amount=2000000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            investment_amount=1500000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['AFR', 'LATAM', 'EU'], 'AFR', hq_pct=0.44))

    def _team5_round4(self, team, rnd):
        """R4: Attempt AfriConnect (WA, Brand Preservation). Compete with Team 4."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=2000000)
        self._add_marketing_for_active_products(sub, team)

        # Compete for AfriConnect
        DecisionAcquisition.objects.create(
            submission=sub,
            acquisition_target_id=self.acq_targets['AFR'],
        )

        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['durability'],
            method='in_house', amount=200000,
        )

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'],
            investment_amount=2000000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            investment_amount=1500000,
        )

        self._add_default_talent(sub, team,
            self._talent_alloc(['AFR', 'LATAM', 'EU'], 'AFR', hq_pct=0.44))

    def _team5_round5(self, team, rnd):
        """R5: Continue building trust. Heavy compliance."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=2000000)
        self._add_marketing_for_active_products(sub, team)

        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['product_design'],
            method='in_house', amount=200000,
        )

        for code in ['EU', 'LATAM']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code],
                investment_amount=1500000,
            )

        self._add_default_talent(sub, team,
            self._talent_alloc(['AFR', 'LATAM', 'EU'], 'AFR', hq_pct=0.44))

    def _team5_round6(self, team, rnd):
        """R6: Deepen localization. Tech sovereignty = 100%."""
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=5000000, strat=2000000)
        self._add_marketing_for_active_products(sub, team)

        for code in ['EU', 'LATAM']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code],
                investment_amount=1500000,
            )

        self._add_default_talent(sub, team,
            self._talent_alloc(['AFR', 'LATAM', 'EU'], 'AFR', hq_pct=0.36))

    # Rounds 7-8 use default (continue marketing + compliance)

    # ===================================================================
    # ADVANCE ROUND
    # ===================================================================

    def _advance_round(self, round_num):
        """Advance the round through engine Phase 1."""
        self.stdout.write(f'  Advancing round {round_num}...')
        try:
            from core.engine.advance_round import _run_phase_1
            context = _run_phase_1(self.game.id)
            phase_time = context._phase_1_time
            self.stdout.write(self.style.SUCCESS(
                f'  Round {round_num} complete ({phase_time:.1f}s)'
            ))

            # Log any engine warnings
            for entry in context.log:
                if 'failed' in entry.lower() or 'error' in entry.lower():
                    self.stdout.write(self.style.WARNING(f'    LOG: {entry}'))
                    self.results['round_errors'].append(f'R{round_num}: {entry}')

            self.game.refresh_from_db()
            return True

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  FAILED: {e}'))
            self.results['round_errors'].append(f'R{round_num} FATAL: {e}')
            traceback.print_exc()
            return False

    # ===================================================================
    # DATA COLLECTION
    # ===================================================================

    def _collect_round_data(self, round_num):
        """Collect validation data after each round."""
        rd = {'round': round_num, 'teams': {}}

        for team_num, team in self.teams.items():
            td = {}

            # Financials
            fin = RoundResultFinancials.objects.filter(
                game=self.game, team=team, round_number=round_num,
            ).first()
            if fin:
                td['revenue'] = float(fin.total_revenue or 0)
                td['net_income'] = float(fin.net_income or 0)
                td['cash'] = float(fin.cash_closing or 0)
                td['share_price'] = float(fin.share_price or 0)
                td['debt_to_equity'] = float(fin.debt_to_equity or 0)
            else:
                td['revenue'] = 0
                td['net_income'] = 0
                td['cash'] = 0
                td['share_price'] = 0

            # Performance index
            perf = RoundResultPerformanceIndex.objects.filter(
                game=self.game, team=team, round_number=round_num,
            ).first()
            td['performance_index'] = float(perf.index_value) if perf else 0

            # Trust per foreign market
            td['trust'] = {}
            for tmc in TeamMarketCompliance.objects.filter(game=self.game, team=team):
                td['trust'][tmc.market.code] = {
                    'multiplier': float(tmc.current_trust_multiplier),
                    'compliance': float(tmc.compliance_level),
                    'investment': float(tmc.cumulative_investment),
                    'rounds_present': tmc.rounds_present,
                }

            # Market revenues
            td['market_revenues'] = {}
            for mr in RoundResultMarketRevenue.objects.filter(
                game=self.game, team=team, round_number=round_num,
            ).select_related('market'):
                td['market_revenues'][mr.market.code] = float(mr.home_revenue or 0)

            # IP exposure
            td['ip_exposure'] = {}
            for mp in TeamMarketPresence.objects.filter(team=team, status='active').select_related('market'):
                if float(mp.ip_exposure_cumulative or 0) > 0:
                    td['ip_exposure'][mp.market.code] = float(mp.ip_exposure_cumulative)

            # Licensed dependency
            platforms = TeamPlatform.objects.filter(team=team, status='active')
            deps = [float(p.licensed_dependency_pct or 0) for p in platforms]
            td['licensed_dependency'] = max(deps) if deps else 0

            rd['teams'][team_num] = td

        # Events
        events = EventInstance.objects.filter(
            game=self.game, round_number=round_num,
        ).select_related('event_template', 'target_market')
        rd['events'] = []
        for ev in events:
            ev_data = {
                'name': ev.event_template.name if ev.event_template else 'unknown',
                'market': ev.target_market.code if ev.target_market else None,
                'round': round_num,
            }
            rd['events'].append(ev_data)
            self.results['events'].append(ev_data)

        # Government actions
        rd['govt_actions'] = GovernmentAction.objects.filter(
            game=self.game, round__round_number=round_num,
        ).count()

        self.results['round_data'][round_num] = rd

        # Print summary
        self.stdout.write(f'\n  --- Round {round_num} Summary ---')
        for tn, td in rd['teams'].items():
            t = self.teams[tn]
            self.stdout.write(
                f'  T{tn} ({t.home_market.code}): Rev=${td["revenue"]:,.0f} '
                f'NI=${td["net_income"]:,.0f} PI={td["performance_index"]:.1f} '
                f'Cash=${td["cash"]:,.0f}'
            )
        if rd['events']:
            self.stdout.write(f'  Events: {len(rd["events"])} fired')

    # ===================================================================
    # FINAL SUMMARY
    # ===================================================================

    def _final_summary(self):
        """Print final summary and key metrics."""
        self.stdout.write(f'\n{"="*60}')
        self.stdout.write('  FINAL RESULTS')
        self.stdout.write(f'{"="*60}')

        last_round = max(self.results['round_data'].keys()) if self.results['round_data'] else 0

        if last_round == 0:
            self.stdout.write('  No rounds completed.')
            return

        rd = self.results['round_data'][last_round]

        self.stdout.write(f'\n  Performance Index (Round {last_round}):')
        indices = []
        for tn in sorted(rd['teams'].keys()):
            td = rd['teams'][tn]
            t = self.teams[tn]
            idx = td['performance_index']
            indices.append(idx)
            self.stdout.write(
                f'    T{tn} ({t.home_market.code}): PI={idx:.1f} '
                f'Rev=${td["revenue"]:,.0f} NI=${td["net_income"]:,.0f} '
                f'Share=${td.get("share_price", 0):.2f}'
            )

        if indices:
            spread = max(indices) - min(indices)
            self.stdout.write(f'\n  Spread: {spread:.1f} (target: >15)')
            self.stdout.write(f'  Highest: {max(indices):.1f} (target: >50)')
            self.stdout.write(f'  Lowest: {min(indices):.1f} (target: >25)')

        # Trust trajectories
        self.stdout.write(f'\n  Trust Trajectories:')
        for tn, team in self.teams.items():
            for rn in sorted(self.results['round_data'].keys()):
                rd_data = self.results['round_data'][rn]
                trusts = rd_data['teams'].get(tn, {}).get('trust', {})
                if trusts:
                    foreign_trusts = {k: v['multiplier'] for k, v in trusts.items()
                                      if k != team.home_market.code}
                    if foreign_trusts:
                        self.stdout.write(
                            f'    T{tn} R{rn}: {foreign_trusts}'
                        )

        # Events summary
        total_events = len(self.results['events'])
        self.stdout.write(f'\n  Total events fired: {total_events}')

        # Investor positions
        self.stdout.write(f'\n  AI Investor Positions (Round {last_round}):')
        for tn, team in self.teams.items():
            holdings = AIInvestorHolding.objects.filter(
                game=self.game, team=team, round_number=last_round,
            ).select_related('fund')
            for h in holdings:
                self.stdout.write(
                    f'    T{tn}: {h.fund.name} — {h.action} '
                    f'{h.shares_held} shares ({float(h.holding_pct)*100:.1f}%)'
                )

        # Bugs
        if self.results['bugs_found']:
            self.stdout.write(f'\n  Bugs found: {len(self.results["bugs_found"])}')
            for b in self.results['bugs_found']:
                self.stdout.write(f'    - {b}')

        if self.results['round_errors']:
            self.stdout.write(f'\n  Round errors: {len(self.results["round_errors"])}')
            for e in self.results['round_errors']:
                self.stdout.write(f'    - {e}')

        expected_rounds = self.scenario.num_rounds if hasattr(self, 'scenario') else 10
        self.stdout.write(f'\n  Rounds completed: {last_round}/{expected_rounds}')
        if last_round == expected_rounds:
            self.stdout.write(self.style.SUCCESS(f'  ALL {expected_rounds} ROUNDS COMPLETE'))
        else:
            self.stdout.write(self.style.ERROR(f'  STOPPED AT ROUND {last_round}'))

    # ===================================================================
    # HELPERS
    # ===================================================================

    def _check(self, ok, msg):
        if ok:
            self.stdout.write(self.style.SUCCESS(f'  [PASS] {msg}'))
        else:
            self.stdout.write(self.style.ERROR(f'  [FAIL] {msg}'))
