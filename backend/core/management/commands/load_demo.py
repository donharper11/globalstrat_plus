"""
Load a permanent demo game for globalstrat.camdani.com/demo.

Creates demo users, a 5-team game with 4 rounds of scripted decisions,
and advances the engine so the demo showcases a mid-game state.

Usage:
    python manage.py load_demo              # Create demo (idempotent)
    python manage.py load_demo --flush      # Wipe old demo first
"""
import hashlib
import traceback
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.utils import timezone

from core.models.core import User, Game, Team, Round
from core.models.course import Course, Section, SimulationInstance, Enrollment
from core.models.scenario import (
    Scenario, MarketDefinition, EntryModeDefinition,
    PlatformGenerationDefinition, FeatureDefinition,
    StrategyOptionDefinition, AcquisitionTarget,
)
from core.models.decisions import (
    DecisionSubmission, DecisionBudgetAllocation,
    DecisionRDInvestment, DecisionPlatformDevelopment,
    DecisionMarketing, DecisionMarketEntry,
    DecisionFinancing, DecisionPlant, DecisionPartnership,
    DecisionAcquisition, DecisionESG,
)
from core.models.talent import DecisionTalent
from core.models.cc31_models import (
    TalentAllocation, ComplianceInvestment,
)
from core.models.team_state import (
    TeamPlatform, TeamPlatformFeatureLevel,
    TeamProduct, TeamProductMarket,
    TeamMarketPresence,
)


DEMO_GAME_NAME = 'GlobalStrat Demo Game'
DEMO_COURSE_CODE = 'DEMO-GS'

DEMO_INSTRUCTOR = ('demo_instructor', 'demopass', 'Demo Instructor')
DEMO_STUDENTS = [
    ('demo_student1', 'demo1', 'Demo Student 1'),
    ('demo_student2', 'demo2', 'Demo Student 2'),
    ('demo_student3', 'demo3', 'Demo Student 3'),
    ('demo_student4', 'demo4', 'Demo Student 4'),
    ('demo_student5', 'demo5', 'Demo Student 5'),
]


def _hash(plain):
    return hashlib.sha256(plain.encode()).hexdigest()


class Command(BaseCommand):
    help = 'Load a permanent demo game with 4 rounds of scripted play'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush', action='store_true',
            help='Delete existing demo data before creating',
        )

    def handle(self, *args, **options):
        if options['flush']:
            self._flush_demo()

        # Check if demo already exists
        existing = Game.objects.filter(name=DEMO_GAME_NAME).first()
        if existing:
            self.stdout.write(self.style.WARNING(
                f'Demo game already exists (ID: {existing.id}). Use --flush to recreate.'
            ))
            return

        try:
            self._create_demo()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'FATAL: {e}'))
            traceback.print_exc()

    # ==================================================================
    # FLUSH
    # ==================================================================

    def _flush_demo(self):
        self.stdout.write('Flushing old demo data...')
        # Reuse _cleanup_orphans which handles all FK chains properly
        self._cleanup_orphans()
        SimulationInstance.objects.filter(
            section__course__course_code=DEMO_COURSE_CODE,
        ).delete()
        Section.objects.filter(course__course_code=DEMO_COURSE_CODE).delete()
        Course.objects.filter(course_code=DEMO_COURSE_CODE).delete()
        for username, _, _ in DEMO_STUDENTS + [DEMO_INSTRUCTOR]:
            User.objects.filter(username=username).delete()
        self.stdout.write(self.style.SUCCESS('  Demo data flushed.'))

    # ==================================================================
    # ORPHAN CLEANUP
    # ==================================================================

    def _cleanup_orphans(self):
        """Remove all game-related data from the database (all games)."""
        from django.db import connection, transaction

        def _safe(sql, params=None):
            try:
                sid = transaction.savepoint()
                with connection.cursor() as c:
                    c.execute(sql, params or [])
                transaction.savepoint_commit(sid)
            except Exception:
                transaction.savepoint_rollback(sid)

        # Delete ALL game data — we're creating a fresh demo
        all_game_ids = list(Game.objects.values_list('id', flat=True))
        all_team_ids = list(Team.objects.values_list('id', flat=True))

        if all_team_ids:
            ph = ','.join(['%s'] * len(all_team_ids))
            # Get all platform IDs
            plat_ids = []
            try:
                with connection.cursor() as c:
                    c.execute(f'SELECT id FROM team_platform WHERE team_id IN ({ph})', all_team_ids)
                    plat_ids = [r[0] for r in c.fetchall()]
            except Exception:
                pass
            if plat_ids:
                pph = ','.join(['%s'] * len(plat_ids))
                _safe(f'DELETE FROM pending_feature_gain WHERE team_platform_id IN ({pph})', plat_ids)
                _safe(f'DELETE FROM team_platform_feature_level WHERE team_platform_id IN ({pph})', plat_ids)

            # Get product IDs
            prod_ids = []
            try:
                with connection.cursor() as c:
                    c.execute(f'SELECT id FROM team_product WHERE team_id IN ({ph})', all_team_ids)
                    prod_ids = [r[0] for r in c.fetchall()]
            except Exception:
                pass
            if prod_ids:
                prph = ','.join(['%s'] * len(prod_ids))
                _safe(f'DELETE FROM team_product_market WHERE team_product_id IN ({prph})', prod_ids)

            # Get submission IDs
            sub_ids = []
            try:
                with connection.cursor() as c:
                    c.execute(f'SELECT id FROM decision_submission WHERE team_id IN ({ph})', all_team_ids)
                    sub_ids = [r[0] for r in c.fetchall()]
            except Exception:
                pass
            if sub_ids:
                sph = ','.join(['%s'] * len(sub_ids))
                for t in ['talent_allocation', 'decision_talent', 'compliance_investment',
                           'decision_marketing', 'decision_rd_investment',
                           'decision_platform_development', 'decision_market_entry',
                           'decision_financing', 'decision_plant', 'decision_partnership',
                           'decision_acquisition', 'decision_esg', 'decision_event_response',
                           'decision_budget_allocation', 'decision_research_allocation',
                           'decision_product_create', 'decision_product_retire']:
                    _safe(f'DELETE FROM {t} WHERE submission_id IN ({sph})', sub_ids)

            # Delete team-FK tables (complete list from pg_constraint)
            for t in ['decision_submission', 'team_product', 'team_platform',
                       'team_market_presence', 'team_partnership', 'team_plant',
                       'team_acquisition', 'team_talent_state', 'team_strategy_feature_level',
                       'team_member', 'team_framework_analysis', 'team_market_modifier',
                       'market_intelligence_brief', 'research_query_log',
                       'forecast_scenario', 'decision_change_log',
                       'instructor_alert', 'strategic_briefing',
                       'esg_economic_impact', 'talent_economic_impact',
                       'partnership_economic_impact',
                       'team_governance_commitment', 'team_communication',
                       'core_teamorganizationalstructure', 'team_alliance_state',
                       'team_tax_structure']:
                _safe(f'DELETE FROM {t} WHERE team_id IN ({ph})', all_team_ids)

        if all_game_ids:
            gph = ','.join(['%s'] * len(all_game_ids))
            for t in ['government_action', 'government_satisfaction',
                       'ai_investor_holding', 'ai_investor_decision',
                       'event_instance', 'active_modifier',
                       'round_result_adoption', 'round_result_market_revenue',
                       'round_result_financials', 'round_result_performance_index',
                       'round_result_product_market', 'round_result_coherence',
                       'leaderboard_entry', 'share_price_history',
                       'team_market_compliance',
                       'team_governance_commitment', 'team_communication',
                       'core_teamorganizationalstructure', 'team_alliance_state',
                       'team_tax_structure', 'core_agentcyclelog']:
                _safe(f'DELETE FROM {t} WHERE game_id IN ({gph})', all_game_ids)

        # Delete all rounds, teams, games
        if all_game_ids:
            gph = ','.join(['%s'] * len(all_game_ids))
            _safe(f'DELETE FROM core_agentcyclelog WHERE game_id IN ({gph})', all_game_ids)
            _safe(f'DELETE FROM team_communication WHERE game_id IN ({gph})', all_game_ids)
            _safe(f'DELETE FROM round WHERE game_id IN ({gph})', all_game_ids)
            _safe(f'DELETE FROM team WHERE game_id IN ({gph})', all_game_ids)
            _safe(f'DELETE FROM game WHERE id IN ({gph})', all_game_ids)

        # Also clean any truly orphaned records
        _safe('DELETE FROM team_platform_feature_level WHERE team_platform_id NOT IN (SELECT id FROM team_platform)')
        _safe('DELETE FROM team_product_market WHERE team_product_id NOT IN (SELECT id FROM team_product)')
        _safe('DELETE FROM team_platform WHERE team_id NOT IN (SELECT id FROM team)')
        _safe('DELETE FROM team_product WHERE team_id NOT IN (SELECT id FROM team)')

        self.stdout.write('  Orphan data cleaned.')

    # ==================================================================
    # MAIN
    # ==================================================================

    def _create_demo(self):
        self.stdout.write('\n=== Creating GlobalStrat Demo ===\n')

        # 1. Clean up ALL orphan game data then reload scenario
        self._cleanup_orphans()
        self.stdout.write('  Reloading scenario...')
        call_command('load_scenario', '--preset', 'electronics', '--flush', '--markets', '5', verbosity=0)
        self.scenario = Scenario.objects.filter(
            name__icontains='Consumer Electronics',
        ).order_by('-id').first()
        if not self.scenario:
            raise CommandError(
                'No Consumer Electronics scenario. Run: python manage.py load_scenario electronics'
            )
        self.stdout.write(f'  Scenario: {self.scenario.name} (ID: {self.scenario.id})')

        # 2. Create game
        call_command(
            'initialize_game',
            '--scenario', str(self.scenario.id),
            '--teams', '5',
            '--name', DEMO_GAME_NAME,
            '--home_markets', 'NA,APAC,EU,LATAM,AFR',
        )
        self.game = Game.objects.filter(
            name=DEMO_GAME_NAME,
        ).order_by('-id').first()
        if not self.game:
            raise CommandError('Game creation failed.')
        self.stdout.write(f'  Game created (ID: {self.game.id})')

        # 3. Cache scenario lookups
        self._cache_lookups()

        # 4. Create demo users
        instructor = self._ensure_user(*DEMO_INSTRUCTOR, 'instructor')
        students = []
        for username, password, display in DEMO_STUDENTS:
            students.append(self._ensure_user(username, password, display, 'student'))

        # 5. Assign students to teams
        teams = list(Team.objects.filter(game=self.game).order_by('id'))
        for i, student in enumerate(students):
            team = teams[i % len(teams)]
            student.team_id = team.id
            student.display_name = f'{DEMO_STUDENTS[i][2]} ({team.name})'
            student.save()

        # 6. Create course/section/enrollment
        course, _ = Course.objects.get_or_create(
            course_code=DEMO_COURSE_CODE,
            defaults={
                'course_name': 'GlobalStrat Demo Course',
                'instructor_id': instructor.user_id,
                'academic_year': '2026',
                'semester': 'Demo',
                'is_active': True,
                'created_at': timezone.now(),
            },
        )
        course.instructor_id = instructor.user_id
        course.is_active = True
        course.save()

        section, _ = Section.objects.get_or_create(
            course=course,
            section_code='DEMO-01',
            defaults={
                'section_name': 'Demo Section',
                'is_active': True,
                'created_at': timezone.now(),
            },
        )
        section.is_active = True
        section.save()

        instance, _ = SimulationInstance.objects.get_or_create(
            section=section,
            defaults={
                'game_id': self.game.id,
                'current_round': self.game.current_round,
                'total_rounds': self.scenario.num_rounds,
                'status': 'active',
                'started_at': timezone.now(),
                'created_at': timezone.now(),
            },
        )
        instance.game_id = self.game.id
        instance.status = 'active'
        instance.save()

        for i, student in enumerate(students):
            team = teams[i % len(teams)]
            Enrollment.objects.update_or_create(
                user_id=student.user_id,
                section=section,
                defaults={
                    'team_id': team.id,
                    'enrolled_at': timezone.now(),
                    'is_active': True,
                    'onboarding_completed': False,
                },
            )

        self.stdout.write('  Users & enrollments created')

        # 7. Game stays at round 1 — demo students start fresh
        self.stdout.write('  Game at Round 1 — ready for demo students')

        # 8. Print summary
        self._print_summary(teams)

    # ==================================================================
    # CACHE LOOKUPS
    # ==================================================================

    def _cache_lookups(self):
        s = self.scenario
        self.markets = {m.code: m.id for m in MarketDefinition.objects.filter(scenario=s)}
        self.entry_modes = {e.code: e.id for e in EntryModeDefinition.objects.filter(scenario=s)}
        self.platform_gens = {
            p.generation_order: p.id
            for p in PlatformGenerationDefinition.objects.filter(scenario=s)
        }
        self.features = {
            f.code: f.id
            for f in FeatureDefinition.objects.filter(scenario=s, layer='platform')
        }
        self.strategy_options = {
            so.code: so.id
            for so in StrategyOptionDefinition.objects.filter(scenario=s)
        }
        self.acq_targets = {
            at.market.code: at.id
            for at in AcquisitionTarget.objects.filter(scenario=s).select_related('market')
        }
        self.teams = {}
        for t in Team.objects.filter(game=self.game).order_by('id'):
            num = int(t.name.split()[-1])
            self.teams[num] = t

        self.stdout.write(f'  Markets: {list(self.markets.keys())}')
        self.stdout.write(f'  Teams: {[(n, t.home_market.code) for n, t in self.teams.items()]}')

    # ==================================================================
    # DECISION SCRIPTING
    # ==================================================================

    def _script_round(self, round_num):
        round_obj = Round.objects.get(game=self.game, round_number=round_num)
        for team_num in range(1, 6):
            team = self.teams[team_num]
            method = getattr(self, f'_team{team_num}_round{round_num}', None)
            if method:
                try:
                    method(team, round_obj)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(
                        f'    T{team_num} R{round_num} decisions failed: {e}'
                    ))
                    self._create_default_submission(team, round_obj)
            else:
                self._create_default_submission(team, round_obj)

    def _advance_round(self, round_num):
        from core.engine.advance_round import _run_phase_1
        try:
            context = _run_phase_1(self.game.id)
            self.stdout.write(self.style.SUCCESS(
                f'    Round {round_num} advanced ({context._phase_1_time:.1f}s)'
            ))
            self.game.refresh_from_db()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'    Round {round_num} FAILED: {e}'))
            traceback.print_exc()

    # ==================================================================
    # HELPERS (from CC-31I)
    # ==================================================================

    def _ensure_user(self, username, password, display_name, role):
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'password_hash': _hash(password),
                'role': role,
                'display_name': display_name,
            },
        )
        if not created:
            user.password_hash = _hash(password)
            user.role = role
            user.display_name = display_name
            user.save()
        return user

    def _create_submission(self, team, round_obj):
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=round_obj,
            defaults={'status': 'draft'},
        )
        return sub

    def _create_default_submission(self, team, round_obj):
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

    def _add_marketing_for_active_products(self, sub, team):
        home = team.home_market
        active_market_ids = set(
            TeamMarketPresence.objects.filter(
                team=team, status='active',
            ).values_list('market_id', flat=True)
        )
        for product in TeamProduct.objects.filter(team=team, status='active'):
            for tpm in TeamProductMarket.objects.filter(
                team_product=product, is_active=True,
            ):
                if tpm.market_id not in active_market_ids:
                    continue
                self._add_marketing_decision(
                    sub, product, tpm.market_id, home.id,
                    product.positioning,
                )

    def _add_marketing_decision(self, sub, product, market_id, source_market_id,
                                 positioning, price_override=None, volume_override=None,
                                 promo_override=None):
        prices = {'budget': 250, 'mainstream': 420, 'premium': 700, 'ultra_premium': 1000}
        volumes = {'budget': 25000, 'mainstream': 20000, 'premium': 12000, 'ultra_premium': 8000}
        promos = {'budget': 200000, 'mainstream': 300000, 'premium': 400000, 'ultra_premium': 500000}

        price = price_override or prices.get(positioning, 400)
        volume = volume_override or volumes.get(positioning, 20000)
        promo = promo_override or promos.get(positioning, 300000)

        platform = product.team_platform
        top_features = TeamPlatformFeatureLevel.objects.filter(
            team_platform=platform, current_level__gt=0,
        ).order_by('-current_level')[:3]
        focus_ids = [fl.feature_id for fl in top_features]

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
        home_code = team.home_market.code
        active_markets = list(
            TeamMarketPresence.objects.filter(
                team=team, status='active',
            ).values_list('market__code', flat=True)
        )
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

        TalentAllocation.objects.filter(submission=sub).delete()
        for pool, hq, alloc in market_allocs:
            TalentAllocation.objects.create(
                submission=sub,
                talent_pool=pool,
                hq_count=hq,
                market_allocation=alloc,
            )

    def _auto_talent_alloc(self, active_markets, home_code, rd=50, com=30, ops=40):
        result = []
        for pool, total in [('rd', rd), ('commercial', com), ('operations', ops)]:
            hq = max(int(total * 0.4), int(total * 0.2) + 1)
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

    def _talent_alloc(self, active_markets, home_code, rd=50, com=30, ops=40, hq_pct=0.5):
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

    # ==================================================================
    # TEAM 1 — NA HQ: "The Methodical Globalizer"
    # ==================================================================

    def _team1_round1(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=3000000, mkt=3000000, strat=1000000)
        self._add_marketing_for_active_products(sub, team)

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
        DecisionESG.objects.create(
            submission=sub, environmental_investment=600000, social_investment=400000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['NA'], 'NA', hq_pct=0.7))

    def _team1_round2(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=3000000, strat=2000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['EU'],
            entry_mode_id=self.entry_modes['subsidiary'],
            initial_investment=15000000, action='enter',
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'], investment_amount=1000000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['NA', 'EU'], 'NA', hq_pct=0.6))

    def _team1_round3(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=2000000)

        for product in TeamProduct.objects.filter(team=team, status='active'):
            TeamProductMarket.objects.get_or_create(
                team_product=product, market_id=self.markets['EU'],
                defaults={'first_offered_round': 3},
            )
        self._add_marketing_for_active_products(sub, team)

        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            entry_mode_id=self.entry_modes['export'],
            initial_investment=500000, action='enter',
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'], investment_amount=1500000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['NA', 'EU', 'LATAM'], 'NA', hq_pct=0.5))

    def _team1_round4(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=3000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionAcquisition.objects.create(
            submission=sub, acquisition_target_id=self.acq_targets['NA'],
        )
        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['AFR'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000, action='enter',
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'], investment_amount=1000000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['AFR'], investment_amount=500000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['NA', 'EU', 'LATAM', 'AFR'], 'NA', hq_pct=0.44))

    # ==================================================================
    # TEAM 2 — APAC HQ: "The Aggressive Licensor"
    # ==================================================================

    def _team2_round1(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=4000000, mkt=3000000, strat=1000000)
        self._add_marketing_for_active_products(sub, team)

        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        for feat_code in ['processing_power', 'app_ecosystem', 'ai_features']:
            feat_id = self.features.get(feat_code)
            if feat_id:
                DecisionRDInvestment.objects.create(
                    submission=sub, team_platform=platform,
                    feature_id=feat_id, method='license', amount=400000,
                )
        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['NA'],
            entry_mode_id=self.entry_modes['export'],
            initial_investment=500000, action='enter',
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['APAC', 'NA'], 'APAC', hq_pct=0.6))

    def _team2_round2(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=4000000, mkt=4000000, strat=2000000)

        for product in TeamProduct.objects.filter(team=team, status='active'):
            TeamProductMarket.objects.get_or_create(
                team_product=product, market_id=self.markets['NA'],
                defaults={'first_offered_round': 2},
            )
        self._add_marketing_for_active_products(sub, team)

        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['EU'],
            entry_mode_id=self.entry_modes['licensing'],
            initial_investment=1000000, action='enter',
        )
        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000, action='enter',
        )

        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        for feat_code in ['battery_life', 'durability']:
            DecisionRDInvestment.objects.create(
                submission=sub, team_platform=platform,
                feature_id=self.features[feat_code], method='license', amount=300000,
            )
        self._add_default_talent(sub, team,
            self._talent_alloc(['APAC', 'NA', 'EU', 'LATAM'], 'APAC', hq_pct=0.5))

    def _team2_round3(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=3000000, mkt=5000000, strat=2000000)

        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['AFR'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000, action='enter',
        )
        for product in TeamProduct.objects.filter(team=team, status='active'):
            for code in ['EU', 'LATAM', 'AFR']:
                TeamProductMarket.objects.get_or_create(
                    team_product=product, market_id=self.markets[code],
                    defaults={'first_offered_round': 3},
                )
        self._add_marketing_for_active_products(sub, team)

        for code in ['NA', 'EU', 'LATAM', 'AFR']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code], investment_amount=200000,
            )
        self._add_default_talent(sub, team,
            self._talent_alloc(['APAC', 'NA', 'EU', 'LATAM', 'AFR'], 'APAC', hq_pct=0.42))

    def _team2_round4(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=5000000, mkt=4000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionAcquisition.objects.create(
            submission=sub, acquisition_target_id=self.acq_targets['APAC'],
        )
        DecisionPlatformDevelopment.objects.create(
            submission=sub, platform_generation_id=self.platform_gens[2],
            method='license', committed_cost=35000000,
            platform_name='Team2 Gen2 Licensed',
        )
        for code in ['NA', 'EU', 'LATAM', 'AFR']:
            ComplianceInvestment.objects.create(
                submission=sub, market_id=self.markets[code], investment_amount=200000,
            )
        self._add_default_talent(sub, team,
            self._talent_alloc(['APAC', 'NA', 'EU', 'LATAM', 'AFR'], 'APAC', hq_pct=0.42))

    # ==================================================================
    # TEAM 3 — EU HQ: "The ESG Champion"
    # ==================================================================

    def _team3_round1(self, team, rnd):
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
            submission=sub, environmental_investment=2000000, social_investment=1000000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['EU'], 'EU', hq_pct=0.6))

    def _team3_round2(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=3000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000, action='enter',
        )
        DecisionPartnership.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            strategy_option_id=self.strategy_options['local_strategic_latam'],
            annual_investment=600000, action='establish',
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'], investment_amount=1500000,
        )
        DecisionESG.objects.create(
            submission=sub, environmental_investment=1500000, social_investment=1000000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['EU', 'LATAM'], 'EU', hq_pct=0.5))

    def _team3_round3(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=2000000)

        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['NA'],
            entry_mode_id=self.entry_modes['export'],
            initial_investment=500000, action='enter',
        )
        for product in TeamProduct.objects.filter(team=team, status='active'):
            for code in ['LATAM', 'NA']:
                TeamProductMarket.objects.get_or_create(
                    team_product=product, market_id=self.markets[code],
                    defaults={'first_offered_round': 3},
                )
        self._add_marketing_for_active_products(sub, team)

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'], investment_amount=1500000,
        )
        DecisionESG.objects.create(
            submission=sub, environmental_investment=1500000, social_investment=500000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['EU', 'LATAM', 'NA'], 'EU', hq_pct=0.44))

    def _team3_round4(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=5000000, mkt=4000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionAcquisition.objects.create(
            submission=sub, acquisition_target_id=self.acq_targets['LATAM'],
        )
        DecisionPlatformDevelopment.objects.create(
            submission=sub, platform_generation_id=self.platform_gens[2],
            method='in_house', committed_cost=15000000,
            platform_name='Team3 Gen2 Sustainable',
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'], investment_amount=1500000,
        )
        DecisionESG.objects.create(
            submission=sub, environmental_investment=1500000, social_investment=1000000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['EU', 'LATAM', 'NA'], 'EU', hq_pct=0.44))

    # ==================================================================
    # TEAM 4 — LATAM HQ: "The Regional Champion"
    # ==================================================================

    def _team4_round1(self, team, rnd):
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
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=3000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['EU'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000, action='enter',
        )
        DecisionPartnership.objects.create(
            submission=sub, market_id=self.markets['EU'],
            strategy_option_id=self.strategy_options['local_strategic_eu'],
            annual_investment=900000, action='establish',
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'], investment_amount=1000000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['LATAM', 'EU'], 'LATAM', hq_pct=0.5))

    def _team4_round3(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=2000000)

        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['AFR'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000, action='enter',
        )
        for product in TeamProduct.objects.filter(team=team, status='active'):
            for code in ['EU', 'AFR']:
                TeamProductMarket.objects.get_or_create(
                    team_product=product, market_id=self.markets[code],
                    defaults={'first_offered_round': 3},
                )
        self._add_marketing_for_active_products(sub, team)

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['AFR'], investment_amount=1000000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'], investment_amount=800000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['LATAM', 'EU', 'AFR'], 'LATAM', hq_pct=0.44))

    def _team4_round4(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionAcquisition.objects.create(
            submission=sub, acquisition_target_id=self.acq_targets['AFR'],
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['AFR'], investment_amount=1000000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'], investment_amount=800000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['LATAM', 'EU', 'AFR'], 'LATAM', hq_pct=0.44))

    # ==================================================================
    # TEAM 5 — AFR HQ: "The Underdog"
    # ==================================================================

    def _team5_round1(self, team, rnd):
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
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['AFR'], investment_amount=500000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['AFR'], 'AFR', hq_pct=0.7))

    def _team5_round2(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=3000000, strat=3000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            entry_mode_id=self.entry_modes['joint_venture'],
            initial_investment=8000000, action='enter',
        )
        DecisionPartnership.objects.create(
            submission=sub, market_id=self.markets['LATAM'],
            strategy_option_id=self.strategy_options['local_strategic_latam'],
            annual_investment=600000, action='establish',
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'], investment_amount=2000000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['AFR', 'LATAM'], 'AFR', hq_pct=0.56))

    def _team5_round3(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=3000000)

        DecisionMarketEntry.objects.create(
            submission=sub, market_id=self.markets['EU'],
            entry_mode_id=self.entry_modes['export'],
            initial_investment=500000, action='enter',
        )
        DecisionPartnership.objects.create(
            submission=sub, market_id=self.markets['EU'],
            strategy_option_id=self.strategy_options['local_strategic_eu'],
            annual_investment=900000, action='establish',
        )
        for product in TeamProduct.objects.filter(team=team, status='active'):
            for code in ['LATAM', 'EU']:
                TeamProductMarket.objects.get_or_create(
                    team_product=product, market_id=self.markets[code],
                    defaults={'first_offered_round': 3},
                )
        self._add_marketing_for_active_products(sub, team)

        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'], investment_amount=2000000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'], investment_amount=1500000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['AFR', 'LATAM', 'EU'], 'AFR', hq_pct=0.44))

    def _team5_round4(self, team, rnd):
        sub = self._create_submission(team, rnd)
        self._add_budget(sub, rd=2000000, mkt=4000000, strat=2000000)
        self._add_marketing_for_active_products(sub, team)

        DecisionAcquisition.objects.create(
            submission=sub, acquisition_target_id=self.acq_targets['AFR'],
        )
        platform = TeamPlatform.objects.filter(team=team, status='active').first()
        DecisionRDInvestment.objects.create(
            submission=sub, team_platform=platform,
            feature_id=self.features['durability'],
            method='in_house', amount=200000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['EU'], investment_amount=2000000,
        )
        ComplianceInvestment.objects.create(
            submission=sub, market_id=self.markets['LATAM'], investment_amount=1500000,
        )
        self._add_default_talent(sub, team,
            self._talent_alloc(['AFR', 'LATAM', 'EU'], 'AFR', hq_pct=0.44))

    # ==================================================================
    # SUMMARY
    # ==================================================================

    def _print_summary(self, teams):
        self.stdout.write(f'\n{"="*60}')
        self.stdout.write('  DEMO GAME READY')
        self.stdout.write(f'{"="*60}')
        self.stdout.write(f'\n  Game: {self.game.name} (ID: {self.game.id})')
        self.stdout.write(f'  Round: {self.game.current_round}')
        self.stdout.write(f'\n  Demo login credentials:')
        self.stdout.write(f'  {"─"*50}')
        self.stdout.write(f'  {DEMO_INSTRUCTOR[0]} / {DEMO_INSTRUCTOR[1]} (Instructor)')
        for i, (username, password, display) in enumerate(DEMO_STUDENTS):
            team = teams[i % len(teams)]
            self.stdout.write(f'  {username} / {password} → {team.name}')
        self.stdout.write(f'\n  URL: https://globalstrat.camdani.com/demo')
        self.stdout.write(f'{"="*60}\n')
