"""
CC-12: Integration Test — 10-Round Scripted Playthrough.

Runs a complete simulation from start to finish using scripted decisions
for 4 teams with distinct strategies. Validates every engine component,
financial model, and data pipeline end-to-end.

Usage: python manage.py run_integration_test [--rounds N]
"""
import time
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models.core import Game, Team, Round
from core.models.scenario import (
    Scenario, FeatureDefinition, PlatformGenerationDefinition,
    MarketDefinition, EntryModeDefinition, SegmentDefinition,
    StrategyOptionDefinition,
)
from core.models.decisions import (
    DecisionSubmission, DecisionBudgetAllocation, DecisionRDInvestment,
    DecisionMarketing, DecisionMarketEntry, DecisionFinancing,
    DecisionPlant, DecisionPartnership, DecisionESG,
    DecisionResearchAllocation, DecisionPlatformDevelopment,
    DecisionProductCreate,
)
from core.models.team_state import (
    TeamPlatform, TeamProduct, TeamProductMarket, TeamMarketPresence,
)
from core.models.results import EventInstance, RoundResultAdoption
from core.models.results_financials import (
    RoundResultFinancials, RoundResultPerformanceIndex,
    RoundResultCoherence, LeaderboardEntry,
)

D = Decimal


class Command(BaseCommand):
    help = 'Run CC-12 integration test: full 8-round simulation with 4 scripted teams'

    def add_arguments(self, parser):
        parser.add_argument(
            '--rounds', type=int, default=None,
            help='Number of rounds to run (default: all rounds in scenario)',
        )

    def handle(self, *args, **options):
        start_time = time.time()

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('CC-12 INTEGRATION TEST — Full Simulation Playthrough')
        self.stdout.write('=' * 70)

        # Step 1: Initialize
        game, teams = self._initialize_game()
        max_rounds = options['rounds'] or game.scenario.num_rounds
        strategies = ['aggressive', 'steady', 'green', 'cost_leader']

        # Cache scenario objects
        self.scenario = game.scenario
        self.markets = {m.code: m for m in MarketDefinition.objects.filter(scenario=self.scenario)}
        self.features = {f.code: f for f in FeatureDefinition.objects.filter(scenario=self.scenario)}
        self.entry_modes = {e.code: e for e in EntryModeDefinition.objects.filter(scenario=self.scenario)}
        self.strategy_options = {s.code: s for s in StrategyOptionDefinition.objects.filter(scenario=self.scenario)}
        self.generations = {
            g.generation_order: g
            for g in PlatformGenerationDefinition.objects.filter(scenario=self.scenario)
        }

        results_log = []
        all_valid = True

        # Step 3: Run rounds
        for round_num in range(1, max_rounds + 1):
            self.stdout.write(f'\n{"=" * 60}')
            self.stdout.write(f'ROUND {round_num}')
            self.stdout.write(f'{"=" * 60}')

            # Open round
            round_obj = Round.objects.get(game=game, round_number=round_num)
            if round_obj.status == 'pending':
                round_obj.status = 'open'
                round_obj.opened_at = timezone.now()
                round_obj.save()

            # Generate decisions
            for team, strategy in zip(teams, strategies):
                self.stdout.write(f'  Generating decisions for {team.name} ({strategy})...')
                self._generate_round_decisions(team, round_num, strategy, game)

            # Advance
            self.stdout.write(f'\n  Advancing round {round_num}...')
            round_start = time.time()
            from core.engine.advance_round import advance_round
            context = advance_round(game.id)
            round_elapsed = time.time() - round_start
            self.stdout.write(f'  Round {round_num} processed in {round_elapsed:.1f}s')

            # Print engine log highlights
            for entry in context.log:
                self.stdout.write(f'    {entry}')

            # Collect & print results
            round_results = self._collect_round_results(game, round_num, teams)
            round_results['elapsed'] = round_elapsed
            results_log.append(round_results)
            self._print_round_summary(round_results, teams)

            # Validate
            valid = self._validate_round(game, round_num, teams)
            if not valid:
                all_valid = False

            # Refresh game
            game.refresh_from_db()

        # Final game outcome checks
        self.stdout.write(f'\n{"=" * 60}')
        self.stdout.write('GAME OUTCOME VALIDATION')
        self.stdout.write(f'{"=" * 60}')
        self._validate_game_outcomes(game, teams, strategies)

        # Generate report
        total_time = time.time() - start_time
        report = self._generate_report(game, teams, strategies, results_log, all_valid, total_time)
        report_path = '/home/ubuntu/projects/globalstrat/specs/cc-12-integration-test-report.md'
        with open(report_path, 'w') as f:
            f.write(report)
        self.stdout.write(f'\nReport saved to: {report_path}')
        self.stdout.write(f'Total test time: {total_time:.1f}s')

        if all_valid:
            self.stdout.write(self.style.SUCCESS('\nALL VALIDATION CHECKS PASSED'))
        else:
            self.stdout.write(self.style.ERROR('\nSOME VALIDATION CHECKS FAILED — see report'))

    # =========================================================================
    # Step 1: Initialize
    # =========================================================================

    def _initialize_game(self):
        """Create a fresh game with 4 teams."""
        from django.contrib.auth.models import User as AuthUser
        from django.core.management import call_command

        # Ensure scenario exists
        scenario = Scenario.objects.filter(name='Consumer Electronics 2026').first()
        if not scenario:
            self.stdout.write('Loading scenario...')
            call_command('load_scenario', 'electronics')
            scenario = Scenario.objects.get(name='Consumer Electronics 2026')

        # Ensure admin user
        admin = AuthUser.objects.filter(is_superuser=True).first()
        if not admin:
            admin = AuthUser.objects.create_superuser('admin', 'admin@test.com', 'admin')

        # Create game
        self.stdout.write('Initializing game...')
        call_command(
            'initialize_game',
            '--scenario', str(scenario.pk),
            '--teams', '4',
            '--name', 'CC-12 Integration Test',
        )

        game = Game.objects.filter(name='CC-12 Integration Test').order_by('-created_at').first()
        teams = list(Team.objects.filter(game=game).order_by('id'))

        self.stdout.write(f'Game ID: {game.id}')
        for i, team in enumerate(teams):
            self.stdout.write(
                f'  {team.name} — Profile: {team.firm_starter_profile.profile_name}, '
                f'Cash: ${float(team.cash_on_hand):,.0f}'
            )

        # Activate game
        game.status = 'active'
        game.save()

        return game, teams

    # =========================================================================
    # Step 2: Decision Generation
    # =========================================================================

    def _generate_round_decisions(self, team, round_number, strategy, game):
        """Generate and lock a complete decision set for one team."""
        round_obj = Round.objects.get(game=game, round_number=round_number)

        # Create or get submission
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=round_obj,
            defaults={'status': 'draft'},
        )

        na = self.markets['NA']
        apac = self.markets['APAC']
        eu = self.markets['EU']

        # Get team's active platform
        active_platform = TeamPlatform.objects.filter(
            team=team, status='active',
        ).order_by('-platform_generation__generation_order').first()

        # Get team's active products in each market
        active_products = list(TeamProduct.objects.filter(
            team=team, status='active',
        ))

        # Get team's market presences
        presences = {
            p.market.code: p
            for p in TeamMarketPresence.objects.filter(team=team, status='active')
        }

        # ---------- Budget allocation ----------
        budgets = self._get_budgets(strategy, round_number, team)
        DecisionBudgetAllocation.objects.create(
            submission=submission,
            rd_budget=budgets['rd'],
            marketing_budget=budgets['marketing'],
            strategy_budget=budgets['strategy'],
        )

        # ---------- R&D investments ----------
        self._generate_rd(submission, team, active_platform, strategy, round_number, budgets)

        # ---------- Platform development ----------
        self._generate_platform_dev(submission, team, strategy, round_number)

        # ---------- Market entry ----------
        self._generate_market_entry(submission, team, strategy, round_number, presences)

        # ---------- Marketing decisions ----------
        # Refresh presences after potential new entries
        presences = {
            p.market.code: p
            for p in TeamMarketPresence.objects.filter(team=team, status='active')
        }
        self._generate_marketing(
            submission, team, active_products, strategy, round_number, presences, na,
        )

        # ---------- Financing ----------
        self._generate_financing(submission, team, strategy, round_number)

        # ---------- ESG ----------
        self._generate_esg(submission, strategy, round_number)

        # ---------- Research allocation ----------
        self._generate_research(submission, strategy, round_number, presences)

        # Lock
        submission.status = 'locked'
        submission.locked_at = timezone.now()
        submission.save()

    def _get_budgets(self, strategy, rnd, team):
        """Return budget allocations based on strategy and round."""
        cash = float(team.cash_on_hand)
        # Keep some cash reserve
        available = max(cash * 0.6, 5000000)

        if strategy == 'aggressive':
            return {
                'rd': D(str(int(available * 0.35))),
                'marketing': D(str(int(available * 0.40))),
                'strategy': D(str(int(available * 0.25))),
            }
        elif strategy == 'steady':
            return {
                'rd': D(str(int(available * 0.30))),
                'marketing': D(str(int(available * 0.40))),
                'strategy': D(str(int(available * 0.30))),
            }
        elif strategy == 'green':
            return {
                'rd': D(str(int(available * 0.40))),
                'marketing': D(str(int(available * 0.30))),
                'strategy': D(str(int(available * 0.30))),
            }
        else:  # cost_leader
            return {
                'rd': D(str(int(available * 0.20))),
                'marketing': D(str(int(available * 0.50))),
                'strategy': D(str(int(available * 0.30))),
            }

    def _generate_rd(self, submission, team, platform, strategy, rnd, budgets):
        """Generate R&D investment decisions."""
        if not platform:
            return

        rd_budget = float(budgets['rd'])
        # Pick features to invest in based on strategy
        if strategy == 'aggressive':
            features = ['processor_battery', 'apps_cloud_ai', 'connectivity_iot']
        elif strategy == 'steady':
            features = ['durability_weather', 'design_premium']
        elif strategy == 'green':
            features = ['recycled_energy', 'durability_weather', 'design_premium']
        else:  # cost_leader
            features = ['processor_battery', 'durability_weather']

        per_feature = rd_budget / max(len(features), 1)
        for feat_code in features:
            feat = self.features.get(feat_code)
            if feat and feat.layer == 'platform':
                amount = min(per_feature, rd_budget / len(features))
                if amount > 100000:
                    DecisionRDInvestment.objects.create(
                        submission=submission,
                        team_platform=platform,
                        feature=feat,
                        method='in_house',
                        amount=D(str(int(amount))),
                    )

    def _generate_platform_dev(self, submission, team, strategy, rnd):
        """Start platform development if timing is right."""
        # Gen 2: aggressive starts round 2, steady round 3, green round 3, cost_leader round 5
        gen2_start = {'aggressive': 2, 'steady': 3, 'green': 3, 'cost_leader': 5}
        gen3_start = {'aggressive': 6, 'steady': 7, 'green': 5, 'cost_leader': 8}

        gen2 = self.generations.get(2)
        gen3 = self.generations.get(3)

        if gen2 and rnd == gen2_start.get(strategy):
            # Check not already developing
            existing = TeamPlatform.objects.filter(
                team=team, platform_generation=gen2,
            ).exists()
            if not existing:
                method = 'license' if strategy == 'cost_leader' else 'in_house'
                cost = gen2.license_cost if method == 'license' else gen2.development_cost
                DecisionPlatformDevelopment.objects.create(
                    submission=submission,
                    platform_generation=gen2,
                    method=method,
                    committed_cost=cost,
                )

        if gen3 and rnd == gen3_start.get(strategy):
            existing = TeamPlatform.objects.filter(
                team=team, platform_generation=gen3,
            ).exists()
            if not existing:
                DecisionPlatformDevelopment.objects.create(
                    submission=submission,
                    platform_generation=gen3,
                    method='in_house',
                    committed_cost=gen3.development_cost,
                )

    def _generate_market_entry(self, submission, team, strategy, rnd, presences):
        """Generate market entry decisions."""
        apac = self.markets['APAC']
        eu = self.markets['EU']

        # Aggressive: APAC round 1 (JV), EU round 3 (export)
        # Steady: APAC round 3 (licensing), EU round 5 (export)
        # Green: EU round 2 (subsidiary), APAC round 6 (export)
        # Cost leader: APAC round 2 (export), EU round 5 (export)

        entries = {
            'aggressive': [
                (1, apac, 'joint_venture'),
                (3, eu, 'export'),
            ],
            'steady': [
                (3, apac, 'licensing'),
                (5, eu, 'export'),
            ],
            'green': [
                (2, eu, 'subsidiary'),
                (6, apac, 'export'),
            ],
            'cost_leader': [
                (2, apac, 'export'),
                (5, eu, 'export'),
            ],
        }

        for entry_round, market, mode_code in entries.get(strategy, []):
            if rnd == entry_round and market.code not in presences:
                mode = self.entry_modes[mode_code]
                DecisionMarketEntry.objects.create(
                    submission=submission,
                    market=market,
                    entry_mode=mode,
                    initial_investment=mode.capital_requirement + market.entry_cost_base,
                    action='enter',
                )

    def _generate_marketing(self, submission, team, products, strategy, rnd, presences, na):
        """Generate marketing decisions for all active products in all active markets."""
        for product in products:
            # Get markets where this product is offered
            product_markets = list(TeamProductMarket.objects.filter(
                team_product=product, is_active=True,
            ).select_related('market'))

            for tpm in product_markets:
                market = tpm.market
                if market.code not in presences:
                    continue

                price, promo, dist_strategy, volume = self._get_marketing_params(
                    product, market, strategy, rnd,
                )

                # Pick 2 campaign focus features (platform features only)
                platform_features = FeatureDefinition.objects.filter(
                    scenario=self.scenario, layer='platform',
                ).order_by('id')[:2]

                DecisionMarketing.objects.create(
                    submission=submission,
                    team_product=product,
                    market=market,
                    retail_price=D(str(price)),
                    promotion_budget=D(str(int(promo))),
                    campaign_focus_feature_ids=[f.id for f in platform_features],
                    channel_digital_pct=D('0.4000'),
                    channel_traditional_pct=D('0.3500'),
                    channel_trade_pct=D('0.2500'),
                    distribution_strategy=dist_strategy,
                    distribution_investment=D('500000'),
                    production_volume=volume,
                    production_source_market=na,
                    demand_estimate=int(volume * 0.8),
                )

            # Marketing for markets entered in previous rounds (presence already active)
            for mkt_code, presence in presences.items():
                if mkt_code == 'NA':
                    continue  # Already handled above
                if presence.setup_rounds_remaining > 0:
                    continue  # Market not yet operational

                market = presence.market
                already_done = DecisionMarketing.objects.filter(
                    submission=submission, team_product=product, market=market,
                ).exists()
                if already_done:
                    continue

                # Ensure product is offered in this market
                tpm, _ = TeamProductMarket.objects.get_or_create(
                    team_product=product,
                    market=market,
                    defaults={'first_offered_round': rnd},
                )

                price, promo, dist_strategy, volume = self._get_marketing_params(
                    product, market, strategy, rnd,
                )
                # Lower volume for non-home markets
                volume = max(int(volume * 0.5), 5000)

                platform_features = FeatureDefinition.objects.filter(
                    scenario=self.scenario, layer='platform',
                ).order_by('id')[:2]

                DecisionMarketing.objects.create(
                    submission=submission,
                    team_product=product,
                    market=market,
                    retail_price=D(str(price)),
                    promotion_budget=D(str(int(promo * 0.5))),
                    campaign_focus_feature_ids=[f.id for f in platform_features],
                    channel_digital_pct=D('0.4000'),
                    channel_traditional_pct=D('0.3500'),
                    channel_trade_pct=D('0.2500'),
                    distribution_strategy=dist_strategy,
                    distribution_investment=D('300000'),
                    production_volume=volume,
                    production_source_market=na,
                    demand_estimate=int(volume * 0.7),
                )

    def _get_marketing_params(self, product, market, strategy, rnd):
        """Return (price, promo_budget, distribution_strategy, volume)."""
        positioning = product.positioning

        # Base prices by positioning
        base_prices = {
            'budget': 220, 'mainstream': 420, 'premium': 750, 'ultra_premium': 1100,
        }
        price = base_prices.get(positioning, 400)

        # Market adjustments
        if market.code == 'APAC':
            price *= 0.85  # Cheaper in APAC
        elif market.code == 'EU':
            price *= 1.10  # Premium in EU

        # Strategy adjustments
        if strategy == 'cost_leader':
            price *= 0.90
            promo = 800000
            dist_strategy = 'mass_retail'
            volume = 40000 if positioning == 'budget' else 25000
        elif strategy == 'aggressive':
            price *= 1.00
            promo = 1500000
            dist_strategy = 'hybrid'
            volume = 30000 if positioning == 'budget' else 20000
        elif strategy == 'steady':
            price *= 1.00
            promo = 1000000
            dist_strategy = 'selective_retail'
            volume = 25000 if positioning == 'budget' else 18000
        elif strategy == 'green':
            price *= 1.05
            promo = 900000
            dist_strategy = 'selective_retail'
            volume = 20000 if positioning == 'budget' else 15000
        else:
            promo = 1000000
            dist_strategy = 'hybrid'
            volume = 25000

        # Scale up production over time
        volume = int(volume * (1 + 0.05 * (rnd - 1)))

        return round(price, 2), promo, dist_strategy, volume

    def _generate_financing(self, submission, team, strategy, rnd):
        """Generate financing decisions."""
        if strategy == 'aggressive':
            new_debt = D('5000000') if rnd <= 4 else D('0')
            repayment = D('0') if rnd <= 6 else D('2000000')
            dividend = D('0.50') if rnd >= 5 else D('0')
        elif strategy == 'steady':
            new_debt = D('2000000') if rnd <= 2 else D('0')
            repayment = D('1000000') if rnd >= 3 else D('0')
            dividend = D('1.00') if rnd >= 3 else D('0.50')
        elif strategy == 'green':
            new_debt = D('3000000') if rnd <= 3 else D('0')
            repayment = D('0')
            dividend = D('0.25') if rnd >= 5 else D('0')
        else:  # cost_leader
            new_debt = D('0')
            repayment = D('500000') if rnd >= 2 else D('0')
            dividend = D('0')

        DecisionFinancing.objects.create(
            submission=submission,
            new_debt=new_debt,
            debt_repayment=repayment,
            new_equity=D('0'),
            dividend_per_share=dividend,
        )

    def _generate_esg(self, submission, strategy, rnd):
        """Generate ESG decisions."""
        if strategy == 'green':
            env = D('1000000') if rnd <= 4 else D('1500000')
            social = D('500000')
        elif strategy == 'steady':
            env = D('300000')
            social = D('200000')
        elif strategy == 'aggressive':
            env = D('100000')
            social = D('100000')
        else:
            env = D('50000')
            social = D('50000')

        DecisionESG.objects.create(
            submission=submission,
            environmental_investment=env,
            social_investment=social,
        )

    def _generate_research(self, submission, strategy, rnd, presences):
        """Research budget removed — this is now a no-op."""
        pass

    # =========================================================================
    # Results Collection & Validation
    # =========================================================================

    def _collect_round_results(self, game, round_num, teams):
        """Collect key metrics for a round."""
        results = {'round': round_num, 'teams': {}}
        events = EventInstance.objects.filter(game=game, round_number=round_num)
        results['events'] = [
            {'name': e.event_template.name, 'market': e.target_market.name if e.target_market else 'Global'}
            for e in events
        ]

        for team in teams:
            fin = RoundResultFinancials.objects.filter(
                game=game, round_number=round_num, team=team,
            ).first()
            pi = RoundResultPerformanceIndex.objects.filter(
                game=game, round_number=round_num, team=team,
            ).first()
            coh = RoundResultCoherence.objects.filter(
                game=game, round_number=round_num, team=team,
            ).first()

            team_data = {}
            if fin:
                team_data['revenue'] = float(fin.total_revenue)
                team_data['net_income'] = float(fin.net_income)
                team_data['cash'] = float(fin.cash_closing)
                team_data['debt'] = float(fin.total_debt)
                team_data['equity'] = float(fin.total_equity)
                team_data['assets'] = float(fin.total_assets)
                team_data['roe'] = float(fin.roe)
                team_data['gross_margin'] = float(fin.gross_margin_pct)
                team_data['cash_opening'] = float(fin.cash_opening)
                team_data['ocf'] = float(fin.operating_cash_flow)
                team_data['icf'] = float(fin.investing_cash_flow)
                team_data['fcf'] = float(fin.financing_cash_flow)
            if pi:
                team_data['index'] = float(pi.index_value)
                team_data['index_change'] = float(pi.index_change)
            if coh:
                team_data['coherence_formula'] = float(coh.formula_score)
                team_data['coherence_rag'] = float(coh.rag_score) if coh.rag_score else None
                team_data['coherence_blended'] = float(coh.blended_score)

            results['teams'][team.name] = team_data

        return results

    def _print_round_summary(self, results, teams):
        """Print summary table for a round."""
        self.stdout.write(f'\n  Events: {len(results["events"])}')
        for evt in results['events']:
            self.stdout.write(f'    - {evt["name"]} ({evt["market"]})')

        self.stdout.write(f'\n  {"Team":<12} {"Revenue":>12} {"Net Inc":>12} {"Cash":>12} {"Index":>8} {"Coherence":>10}')
        self.stdout.write(f'  {"-"*12} {"-"*12} {"-"*12} {"-"*12} {"-"*8} {"-"*10}')
        for team in teams:
            td = results['teams'].get(team.name, {})
            rev = f"${td.get('revenue', 0):,.0f}"
            ni = f"${td.get('net_income', 0):,.0f}"
            cash = f"${td.get('cash', 0):,.0f}"
            idx = f"{td.get('index', 0):.2f}"
            coh = f"{td.get('coherence_blended', 0):.1f}"
            self.stdout.write(f'  {team.name:<12} {rev:>12} {ni:>12} {cash:>12} {idx:>8} {coh:>10}')

    def _validate_round(self, game, round_num, teams):
        """Validate data integrity for a round. Returns True if all pass."""
        errors = []

        for team in teams:
            # 1. RoundResultFinancials exists
            fin = RoundResultFinancials.objects.filter(
                game=game, round_number=round_num, team=team,
            ).first()
            if not fin:
                errors.append(f'Missing financials for {team.name}')
                continue

            # 2. Balance sheet balances
            balance_diff = abs(fin.total_assets - (fin.total_debt + fin.total_equity))
            if balance_diff > D('1.00'):
                errors.append(
                    f'Balance sheet imbalance for {team.name}: '
                    f'assets={fin.total_assets}, debt+equity={fin.total_debt + fin.total_equity}, '
                    f'diff={balance_diff}'
                )

            # 3. Cash flow reconciles
            cf_sum = fin.operating_cash_flow + fin.investing_cash_flow + fin.financing_cash_flow
            cash_diff = abs(fin.cash_closing - fin.cash_opening - cf_sum)
            if cash_diff > D('1.00'):
                errors.append(
                    f'Cash flow mismatch for {team.name}: '
                    f'open={fin.cash_opening}, close={fin.cash_closing}, cf_sum={cf_sum}'
                )

            # 4. No negative revenue
            if fin.total_revenue < 0:
                errors.append(f'Negative revenue for {team.name}: {fin.total_revenue}')

            # 5. Performance index exists
            pi = RoundResultPerformanceIndex.objects.filter(
                game=game, round_number=round_num, team=team,
            ).first()
            if not pi:
                errors.append(f'Missing performance index for {team.name}')
            elif pi.index_value < 0:
                errors.append(f'Negative index for {team.name}: {pi.index_value}')

            # 6. Coherence score exists
            coh = RoundResultCoherence.objects.filter(
                game=game, round_number=round_num, team=team,
            ).first()
            if not coh:
                errors.append(f'Missing coherence for {team.name}')

        # 7. Leaderboard
        lb_count = LeaderboardEntry.objects.filter(game=game, round_number=round_num).count()
        if lb_count != len(teams):
            errors.append(f'Leaderboard entries: expected {len(teams)}, got {lb_count}')

        # 8. Round status
        round_obj = Round.objects.get(game=game, round_number=round_num)
        if round_obj.status != 'processed':
            errors.append(f'Round {round_num} status is {round_obj.status}, expected processed')

        if errors:
            self.stdout.write(self.style.ERROR(f'\n  VALIDATION ERRORS (Round {round_num}):'))
            for e in errors:
                self.stdout.write(f'    - {e}')
            return False
        else:
            self.stdout.write(self.style.SUCCESS(f'  Round {round_num} validation passed'))
            return True

    def _validate_game_outcomes(self, game, teams, strategies):
        """Check that strategies produce differentiated outcomes."""
        game.refresh_from_db()

        self.stdout.write('\nFinal standings:')
        results = {}
        for team, strategy in zip(teams, strategies):
            fin = RoundResultFinancials.objects.filter(
                game=game, team=team,
            ).order_by('-round_number').first()
            pi = RoundResultPerformanceIndex.objects.filter(
                game=game, team=team,
            ).order_by('-round_number').first()

            if fin and pi:
                results[strategy] = {
                    'revenue': float(fin.total_revenue),
                    'net_income': float(fin.net_income),
                    'cash': float(fin.cash_closing),
                    'debt': float(fin.total_debt),
                    'index': float(pi.index_value),
                    'roe': float(fin.roe),
                }
                self.stdout.write(
                    f'  {team.name} ({strategy}): '
                    f'Rev=${fin.total_revenue:,.0f} '
                    f'NI=${fin.net_income:,.0f} '
                    f'Cash=${fin.cash_closing:,.0f} '
                    f'Debt=${fin.total_debt:,.0f} '
                    f'Index={pi.index_value:.2f}'
                )

        # Differentiation check
        if results:
            indices = [r['index'] for r in results.values()]
            if len(set(f'{v:.2f}' for v in indices)) < len(indices):
                self.stdout.write(self.style.WARNING(
                    '  WARNING: Some teams have identical performance indices'
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    '  All teams have differentiated performance indices'
                ))

            for strategy, r in results.items():
                if r['revenue'] <= 0:
                    self.stdout.write(self.style.WARNING(
                        f'  WARNING: {strategy} has zero/negative revenue'
                    ))

        if game.status == 'completed':
            self.stdout.write(self.style.SUCCESS('  Game status is completed'))
        else:
            self.stdout.write(self.style.WARNING(
                f'  Game status is {game.status}, expected completed'
            ))

    # =========================================================================
    # Report Generation
    # =========================================================================

    def _generate_report(self, game, teams, strategies, results_log, all_valid, total_time):
        """Generate the markdown report."""
        lines = []
        lines.append('# GlobalStrat Integration Test — Game Summary\n')
        lines.append(f'**Game:** {game.name} (ID: {game.id})')
        lines.append(f'**Scenario:** {game.scenario.name}')
        lines.append(f'**Rounds played:** {len(results_log)}')
        lines.append(f'**Teams:** {len(teams)}')
        lines.append(f'**Total runtime:** {total_time:.1f}s')
        lines.append(f'**All validations passed:** {"Yes" if all_valid else "No"}')
        lines.append('')

        # Team assignments
        lines.append('## 1. Test Setup\n')
        lines.append('| Team | Profile | Strategy |')
        lines.append('|------|---------|----------|')
        for team, strategy in zip(teams, strategies):
            lines.append(f'| {team.name} | {team.firm_starter_profile.profile_name} | {strategy} |')
        lines.append('')

        # Round-by-round summary
        lines.append('## 2. Round-by-Round Summary\n')
        header = '| Round | Events |'
        divider = '|-------|--------|'
        for team in teams:
            header += f' {team.name} Index |'
            divider += '-------------|'
        lines.append(header)
        lines.append(divider)

        for rr in results_log:
            row = f'| {rr["round"]} | {len(rr["events"])} |'
            for team in teams:
                td = rr['teams'].get(team.name, {})
                idx = td.get('index', 0)
                row += f' {idx:.2f} |'
            lines.append(row)
        lines.append('')

        # Validation results
        lines.append('## 3. Validation Results\n')
        lines.append('Per-round data integrity checks:\n')
        for rr in results_log:
            rnd = rr['round']
            # Re-validate silently
            has_errors = False
            for team in teams:
                fin = RoundResultFinancials.objects.filter(
                    game=game, round_number=rnd, team=team,
                ).first()
                if not fin:
                    has_errors = True
                    break
                bd = abs(fin.total_assets - (fin.total_debt + fin.total_equity))
                if bd > D('1.00'):
                    has_errors = True
                cd = abs(fin.cash_closing - fin.cash_opening - (
                    fin.operating_cash_flow + fin.investing_cash_flow + fin.financing_cash_flow))
                if cd > D('1.00'):
                    has_errors = True

            status = 'FAIL' if has_errors else 'PASS'
            lines.append(f'- Round {rnd}: {status}')
        lines.append('')

        # Gameplay sensibility
        lines.append('## 4. Gameplay Sensibility\n')
        for team, strategy in zip(teams, strategies):
            fin = RoundResultFinancials.objects.filter(
                game=game, team=team,
            ).order_by('-round_number').first()
            pi = RoundResultPerformanceIndex.objects.filter(
                game=game, team=team,
            ).order_by('-round_number').first()
            if fin and pi:
                lines.append(
                    f'**{team.name} ({strategy}):** '
                    f'Revenue=${float(fin.total_revenue):,.0f}, '
                    f'Net Income=${float(fin.net_income):,.0f}, '
                    f'Cash=${float(fin.cash_closing):,.0f}, '
                    f'Debt=${float(fin.total_debt):,.0f}, '
                    f'Index={float(pi.index_value):.2f}'
                )
        lines.append('')

        # Final standings
        lines.append('## 5. Final Standings\n')
        last_round = results_log[-1]['round'] if results_log else 0
        final_lb = LeaderboardEntry.objects.filter(
            game=game, round_number=last_round,
        ).order_by('rank')
        for entry in final_lb:
            team = entry.team
            strategy = strategies[teams.index(team)]
            lines.append(f'**#{entry.rank} {team.name} ({strategy})**')
            lines.append(f'- Performance Index: {float(entry.performance_index):.2f}')
            lines.append(f'- Revenue: ${float(entry.total_revenue):,.0f}')
            lines.append(f'- Net Income: ${float(entry.net_income):,.0f}')
            lines.append(f'- Shareholder Return: {float(entry.shareholder_return):.2%}')
            lines.append('')

        # Financial trajectories
        lines.append('## 6. Financial Trajectories\n')
        for team, strategy in zip(teams, strategies):
            lines.append(f'### {team.name} ({strategy})\n')
            lines.append('| Round | Revenue | Net Income | Cash | Debt | ROE |')
            lines.append('|-------|---------|-----------|------|------|-----|')
            financials = RoundResultFinancials.objects.filter(
                game=game, team=team,
            ).order_by('round_number')
            for f in financials:
                lines.append(
                    f'| {f.round_number} | ${float(f.total_revenue):,.0f} | '
                    f'${float(f.net_income):,.0f} | ${float(f.cash_closing):,.0f} | '
                    f'${float(f.total_debt):,.0f} | {float(f.roe):.2%} |'
                )
            lines.append('')

        # Events summary
        lines.append('## 7. Events Summary\n')
        all_events = EventInstance.objects.filter(game=game).order_by('round_number')
        if all_events:
            lines.append('| Round | Event | Market |')
            lines.append('|-------|-------|--------|')
            for evt in all_events:
                mkt = evt.target_market.name if evt.target_market else 'Global'
                lines.append(f'| {evt.round_number} | {evt.event_template.name} | {mkt} |')
        else:
            lines.append('No events fired during the simulation.')
        lines.append('')

        # Coherence scores
        lines.append('## 8. Coherence Scores\n')
        lines.append('| Round |', )
        header = '| Round |'
        div = '|-------|'
        for team in teams:
            header += f' {team.name} |'
            div += '------|'
        lines.append(header)
        lines.append(div)
        for rr in results_log:
            row = f'| {rr["round"]} |'
            for team in teams:
                td = rr['teams'].get(team.name, {})
                coh = td.get('coherence_blended', 0)
                row += f' {coh:.1f} |'
            lines.append(row)
        lines.append('')

        # RAG integration
        lines.append('## 9. RAG Integration\n')
        from core.models.rag import ResearchQueryLog
        query_count = ResearchQueryLog.objects.filter(team__game=game).count()
        lines.append(f'Research queries logged: {query_count}')
        rag_coherence_count = RoundResultCoherence.objects.filter(
            game=game, rag_score__isnull=False,
        ).count()
        lines.append(f'RAG coherence scores generated: {rag_coherence_count}')
        lines.append('')

        # Bugs and fixes
        lines.append('## 10. Bugs Found and Fixed\n')
        lines.append('See console output for any errors encountered during the test run.')
        lines.append('')

        # Frontend verification
        lines.append('## 11. Frontend Verification\n')
        lines.append('Manual verification required — see CC-12 spec Step 5.')
        lines.append('')

        # Performance
        lines.append('## 12. Performance\n')
        total_round_time = sum(r.get('elapsed', 0) for r in results_log)
        avg_round_time = total_round_time / len(results_log) if results_log else 0
        lines.append(f'- Total simulation time: {total_time:.1f}s')
        lines.append(f'- Total engine time: {total_round_time:.1f}s')
        lines.append(f'- Average time per round: {avg_round_time:.1f}s')
        lines.append('')

        # Recommendations
        lines.append('## 13. Recommendations\n')
        lines.append('- Review event probabilities — may need tuning if too few/many fire')
        lines.append('- Monitor balance sheet drift over rounds for signs of systematic error')
        lines.append('- Consider tuning Bass model parameters if adoption rates are too uniform')
        lines.append('')

        return '\n'.join(lines)
