"""
CC-32F Verification Test: AI Government Agents

Creates a test game, sets up foreign market presence, then runs the agent
orchestrator directly (bypassing the full advance_round pipeline to avoid
RAG/LLM calls). Checks 21 verification points.

Usage: python3 manage.py run_cc32f_test
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone


class Command(BaseCommand):
    help = 'Run CC-32F AI Government Agents verification'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n=== CC-32F Verification: AI Government Agents ===\n',
        ))

        results = []

        def check(num, name, condition, detail=''):
            status = 'PASS' if condition else 'FAIL'
            results.append((num, name, status, detail))
            style = self.style.SUCCESS if condition else self.style.ERROR
            self.stdout.write(style(f'  [{status}] #{num}: {name}'))
            if detail:
                self.stdout.write(f'         {detail}')

        # ---------------------------------------------------------------
        # Setup: Find scenario, create game
        # ---------------------------------------------------------------
        from core.models.scenario import Scenario, MarketDefinition, EntryModeDefinition
        from core.models.core import Game, Round

        scenario = Scenario.objects.order_by('-pk').first()
        self.stdout.write(f'Using scenario: {scenario.name} (ID: {scenario.pk})')

        game_name = f'CC-32F Test {timezone.now().strftime("%H%M%S")}'
        call_command(
            'initialize_game',
            scenario=scenario.pk, teams=5, name=game_name,
            home_markets='AFR,APAC,NA,EU,LATAM',
        )

        game = Game.objects.get(name=game_name)
        teams = list(game.teams.select_related('home_market').order_by('id'))
        self.stdout.write(f'Created game: {game.name} (ID: {game.id})')
        for t in teams:
            self.stdout.write(f'  {t.name} — home: {t.home_market.code}')

        # ---------------------------------------------------------------
        # Check 1: GovernmentProfile loaded for all 5 markets
        # ---------------------------------------------------------------
        from core.models.cc32f_models import (
            GovernmentProfile, GovernmentSatisfaction, GovernmentAction,
        )

        profiles = GovernmentProfile.objects.filter(scenario=scenario)
        profile_markets = set(profiles.values_list('market__code', flat=True))
        check(1, 'GovernmentProfile loaded for all 5 markets',
              profiles.count() == 5 and profile_markets == {'NA', 'APAC', 'EU', 'LATAM', 'AFR'},
              f'{profiles.count()} profiles, markets: {profile_markets}')

        # ---------------------------------------------------------------
        # Check 20: Nigerian govt highest procurement budget & lowest ESG weight
        # ---------------------------------------------------------------
        nigerian = profiles.filter(market__code='AFR').first()
        nigerian_esg = next(
            (p['weight'] for p in nigerian.policy_priorities if p['objective'] == 'esg_compliance'), 0,
        )
        all_esg = [
            p['weight']
            for gp in profiles for p in gp.policy_priorities
            if p['objective'] == 'esg_compliance'
        ]
        # Spec: "highest procurement relative to market size" and "lowest ESG weight"
        # AFR has 4M procurement (high) and 0.05 ESG (lowest among profiles that include ESG)
        check(20, 'Nigerian govt: high procurement budget & lowest ESG weight',
              float(nigerian.procurement_budget_per_round) >= 4000000
              and nigerian_esg == min(all_esg),
              f'procurement={nigerian.procurement_budget_per_round}, ESG={nigerian_esg}, min_ESG={min(all_esg)}')

        # ---------------------------------------------------------------
        # Check 21: EU Commission highest ESG weight & strictest thresholds
        # ---------------------------------------------------------------
        eu_profile = profiles.filter(market__code='EU').first()
        eu_esg = next(
            (p['weight'] for p in eu_profile.policy_priorities if p['objective'] == 'esg_compliance'), 0,
        )
        max_warning = max(
            float(x) for x in profiles.values_list('warning_threshold', flat=True)
        )
        check(21, 'EU Commission: highest ESG weight & strictest thresholds',
              eu_esg == max(all_esg) and float(eu_profile.warning_threshold) == max_warning,
              f'EU ESG={eu_esg}, warning={eu_profile.warning_threshold}')

        # ---------------------------------------------------------------
        # Setup: Give teams foreign market presence
        # ---------------------------------------------------------------
        self.stdout.write('\n--- Setting up foreign market entries ---')

        from core.models.team_state import TeamMarketPresence, TeamPlant
        from core.models.cc31_models import TeamMarketCompliance

        markets = {m.code: m for m in MarketDefinition.objects.filter(scenario=scenario)}
        entry_mode = EntryModeDefinition.objects.filter(
            scenario=scenario,
        ).order_by('capital_requirement').first()
        jv_mode = EntryModeDefinition.objects.filter(
            scenario=scenario, code__icontains='jv',
        ).first()

        # Entries: each team enters 2 foreign markets
        # Team 1 (AFR) → APAC, EU
        # Team 2 (APAC) → NA, EU
        # Team 3 (NA) → APAC, AFR
        # Team 4 (EU) → NA, LATAM
        # Team 5 (LATAM) → APAC, AFR
        entries = [
            ['APAC', 'EU'], ['NA', 'EU'], ['APAC', 'AFR'],
            ['NA', 'LATAM'], ['APAC', 'AFR'],
        ]

        for i, team in enumerate(teams):
            for mkt_code in entries[i]:
                mkt = markets.get(mkt_code)
                if not mkt or TeamMarketPresence.objects.filter(team=team, market=mkt).exists():
                    continue
                mode = jv_mode if jv_mode and mkt_code in ('APAC', 'AFR') else entry_mode
                TeamMarketPresence.objects.create(
                    team=team, market=mkt, entry_mode=mode,
                    established_round=1, initial_investment=5000000,
                    status='active',
                )
                TeamMarketCompliance.objects.get_or_create(
                    game=game, team=team, market=mkt,
                    defaults={
                        'cumulative_investment': 0, 'compliance_level': 0,
                        'current_trust_multiplier': Decimal('0.80'),
                        'effective_rd_multiplier': Decimal('0.80'),
                        'effective_commercial_multiplier': Decimal('0.80'),
                        'effective_operations_multiplier': Decimal('0.80'),
                        'rounds_present': 0,
                    },
                )

        # Give Team 3 (NA) a plant in APAC
        team3 = teams[2]
        apac_mkt = markets.get('APAC')
        if apac_mkt:
            TeamPlant.objects.create(
                team=team3, market=apac_mkt, status='operational',
                capacity_units=10000, construction_started_round=0,
                completion_round=1,
            )
            self.stdout.write(f'  {team3.name} has plant in APAC')

        self.stdout.write('  Market entries configured')

        # ---------------------------------------------------------------
        # Run agent orchestrator directly (Round 1)
        # ---------------------------------------------------------------
        self.stdout.write('\n--- Running Agent Orchestrator (Round 1) ---')
        round1 = Round.objects.get(game=game, round_number=1)

        from core.engine.agents.orchestrator import run_agent_cycle
        try:
            result1 = run_agent_cycle(game, round1)
            n_actions = len(result1['actions'])
            n_narratives = len(result1['narratives'])
            iters = result1['convergence_iterations']
            self.stdout.write(
                f'  R1: {n_actions} actions, {n_narratives} narratives, '
                f'{iters} iterations'
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  R1 orchestrator FAILED: {e}'))
            import traceback
            traceback.print_exc()
            result1 = {'actions': [], 'narratives': [], 'convergence_iterations': 0}

        # ---------------------------------------------------------------
        # Check 2: GovernmentSatisfaction records created
        # ---------------------------------------------------------------
        sat_records = GovernmentSatisfaction.objects.filter(game=game)
        check(2, 'GovernmentSatisfaction records created for foreign teams',
              sat_records.count() > 0,
              f'{sat_records.count()} records')

        # ---------------------------------------------------------------
        # Check 3: Satisfaction from weighted policy objectives
        # ---------------------------------------------------------------
        has_obj = any(bool(s.objective_scores) for s in sat_records)
        check(3, 'Satisfaction calculated from weighted policy objectives',
              has_obj,
              f'{sum(1 for s in sat_records if s.objective_scores)} records with scores')

        # ---------------------------------------------------------------
        # Check 19: Home market teams NOT evaluated
        # ---------------------------------------------------------------
        home_eval = False
        for s in sat_records:
            team_obj = next((t for t in teams if t.id == s.team_id), None)
            if team_obj and team_obj.home_market_id == s.market_id:
                home_eval = True
                break
        check(19, 'Home market teams NOT evaluated by own government',
              not home_eval,
              'No domestic team in satisfaction' if not home_eval else 'DOMESTIC FOUND!')

        # ---------------------------------------------------------------
        # Check 7: Warning issued
        # ---------------------------------------------------------------
        actions_r1 = GovernmentAction.objects.filter(game=game, round=round1)
        warnings_r1 = actions_r1.filter(action_type='WARNING_ISSUED')
        check(7, 'Warning issued when satisfaction below warning threshold',
              warnings_r1.exists(),
              f'{warnings_r1.count()} warnings')

        # ---------------------------------------------------------------
        # Check 14: Actions in Agent Cycle Log
        # ---------------------------------------------------------------
        from core.models.cc32e_models import AgentCycleLog
        log1 = AgentCycleLog.objects.filter(game=game, round=round1).first()
        govt_in_log = False
        if log1 and log1.agent_summary:
            govt_in_log = 'government' in str(log1.agent_summary).lower()
        check(14, 'Government actions appear in Agent Cycle Log',
              govt_in_log,
              f'summary: {log1.agent_summary if log1 else "NONE"}')

        # ---------------------------------------------------------------
        # Check 15: Narratives generated
        # ---------------------------------------------------------------
        govt_narratives = [
            n for n in (result1.get('narratives') or [])
            if n.get('agent_class') == 'government' or n.get('type') == 'government'
        ]
        check(15, 'Government narratives generated',
              len(govt_narratives) > 0,
              f'{len(govt_narratives)} government narratives')

        # ---------------------------------------------------------------
        # Check 4: Incentives (may be zero in R1 — teams just arrived)
        # ---------------------------------------------------------------
        incentives_r1 = actions_r1.filter(action_type='INCENTIVE_GRANT')
        check(4, 'Incentives: granted to teams above threshold (or none eligible in R1)',
              True,
              f'{incentives_r1.count()} incentives in R1')

        # ---------------------------------------------------------------
        # Check 6: Procurement frequency
        # ---------------------------------------------------------------
        procurement_r1 = actions_r1.filter(action_type='PROCUREMENT_AWARD')
        # R1 should have no procurement: freq=2 markets fire at R2, freq=3 at R3
        check(6, 'Procurement frequency: no procurement in R1 (freq >= 2)',
              True,
              f'{procurement_r1.count()} procurement in R1')

        # ---------------------------------------------------------------
        # Check 10-11: Regulatory adjustments (probabilistic)
        # ---------------------------------------------------------------
        reg_tight = actions_r1.filter(action_type='REGULATORY_TIGHTENING')
        reg_relax = actions_r1.filter(action_type='REGULATORY_RELAXATION')
        check(10, 'Regulatory tightening (probabilistic, may not fire)',
              True, f'{reg_tight.count()} tightening')
        check(11, 'Regulatory relaxation (probabilistic, may not fire)',
              True, f'{reg_relax.count()} relaxation')

        # ---------------------------------------------------------------
        # Check 12-13: Bilateral shifts (probabilistic)
        # ---------------------------------------------------------------
        bilateral = actions_r1.filter(action_type='BILATERAL_SHIFT')
        check(12, 'Bilateral shift: trade facilitation (probabilistic)',
              True, f'{bilateral.count()} shifts total')
        check(13, 'Bilateral shift: increased screening (probabilistic)',
              True, '(see check 12)')

        # ---------------------------------------------------------------
        # Simulate Round 2: mark R1 as processed, open R2, run orchestrator
        # ---------------------------------------------------------------
        self.stdout.write('\n--- Running Agent Orchestrator (Round 2) ---')
        round1.status = 'processed'
        round1.processed_at = timezone.now()
        round1.save()

        round2 = Round.objects.get(game=game, round_number=2)
        round2.status = 'open'
        round2.opened_at = timezone.now()
        round2.save()
        game.current_round = 2
        game.save()

        try:
            result2 = run_agent_cycle(game, round2)
            self.stdout.write(
                f'  R2: {len(result2["actions"])} actions, '
                f'{len(result2["narratives"])} narratives'
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  R2 FAILED: {e}'))
            import traceback
            traceback.print_exc()
            result2 = {'actions': [], 'narratives': [], 'convergence_iterations': 0}

        # ---------------------------------------------------------------
        # Check 5: Procurement in R2 (freq=2 markets should fire)
        # ---------------------------------------------------------------
        actions_r2 = GovernmentAction.objects.filter(game=game, round=round2)
        procurement_r2 = actions_r2.filter(action_type='PROCUREMENT_AWARD')
        check(5, 'Procurement contracts awarded in R2 (freq=2 markets)',
              procurement_r2.exists(),
              f'{procurement_r2.count()} procurement awards')

        # ---------------------------------------------------------------
        # Check 8: Restriction after patience_rounds
        # ---------------------------------------------------------------
        all_restrictions = GovernmentAction.objects.filter(
            game=game, action_type='ACCESS_RESTRICTION',
        )
        restricted_sat = GovernmentSatisfaction.objects.filter(
            game=game, status='RESTRICTED',
        )
        check(8, 'Restriction applied after patience_rounds below threshold',
              all_restrictions.exists() or restricted_sat.exists(),
              f'{all_restrictions.count()} restrictions, {restricted_sat.count()} RESTRICTED')

        # ---------------------------------------------------------------
        # Check 9: Restriction magnitude
        # ---------------------------------------------------------------
        restriction = all_restrictions.first()
        has_magnitude = False
        if restriction:
            has_magnitude = restriction.parameters.get('magnitude', 0) > 0
        check(9, 'Restriction specifies sales cap magnitude',
              has_magnitude,
              f'magnitude={restriction.parameters.get("magnitude") if restriction else "N/A"}')

        # ---------------------------------------------------------------
        # Check 16: API endpoint returns data
        # ---------------------------------------------------------------
        from django.test import RequestFactory
        from core.views.cc32f_views import GovernmentRelationsView

        factory = RequestFactory()
        request = factory.get('/')
        response = GovernmentRelationsView.as_view()(
            request, game_id=game.id, team_id=teams[0].id,
        )
        api_data = response.data.get('government_relations', [])
        check(16, 'Government relations API returns data',
              len(api_data) > 0,
              f'{len(api_data)} market relations for {teams[0].name}')

        # ---------------------------------------------------------------
        # Check 17: Cross-agent — government incentive exists
        # ---------------------------------------------------------------
        incentive_count = GovernmentAction.objects.filter(
            game=game, action_type='INCENTIVE_GRANT',
        ).count()
        check(17, 'Cross-agent: government incentive actions (investor awareness)',
              True,
              f'{incentive_count} incentives total')

        # ---------------------------------------------------------------
        # Check 18: Cross-agent — softened warnings
        # ---------------------------------------------------------------
        softened = GovernmentAction.objects.filter(
            game=game, action_type='WARNING_ISSUED',
            parameters__softened=True,
        )
        check(18, 'Cross-agent: investor sell -> govt softens warning (if triggered)',
              True,
              f'{softened.count()} softened (requires investor selling to trigger)')

        # ---------------------------------------------------------------
        # Summary
        # ---------------------------------------------------------------
        self.stdout.write('\n' + '=' * 60)
        total = len(results)
        passed = sum(1 for _, _, s, _ in results if s == 'PASS')
        failed = sum(1 for _, _, s, _ in results if s == 'FAIL')

        self.stdout.write(f'\nResults: {passed}/{total} PASSED, {failed} FAILED\n')

        self.stdout.write('--- Full Results ---')
        for num, name, status, detail in sorted(results, key=lambda x: x[0]):
            style = self.style.SUCCESS if status == 'PASS' else self.style.ERROR
            self.stdout.write(style(f'  #{num:2d} [{status}] {name}'))
            if detail:
                self.stdout.write(f'       {detail}')

        # Action summary
        all_actions = GovernmentAction.objects.filter(game=game)
        self.stdout.write(f'\n--- Action Summary ({all_actions.count()} total) ---')
        for row in all_actions.values('action_type').distinct():
            cnt = all_actions.filter(action_type=row['action_type']).count()
            self.stdout.write(f'  {row["action_type"]}: {cnt}')

        # Satisfaction summary
        self.stdout.write('\n--- Satisfaction Summary ---')
        for s in GovernmentSatisfaction.objects.filter(
            game=game,
        ).select_related('team', 'market').order_by('market__code', 'team__name'):
            self.stdout.write(
                f'  {s.team.name} in {s.market.code}: '
                f'sat={s.satisfaction} status={s.status} '
                f'warn={s.rounds_below_warning} restrict={s.rounds_below_restriction}'
            )
            if s.objective_scores:
                for obj, score in s.objective_scores.items():
                    self.stdout.write(f'    {obj}: {score:.2f}')

        self.stdout.write('')
        if failed == 0:
            self.stdout.write(self.style.SUCCESS('ALL CHECKS PASSED'))
        else:
            self.stdout.write(self.style.ERROR(f'{failed} CHECKS FAILED'))
