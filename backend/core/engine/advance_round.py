"""
Engine Orchestrator: Runs the FULL pipeline in two phases.

Phase 1 (synchronous): Deterministic engine math — Steps 1-14.5 + leaderboard.
  No LLM calls. Completes in <10s. Students see numbers immediately.

Phase 2 (background thread): Concurrent LLM calls for narratives, briefings,
  coherence RAG, coaching alerts, and market outlooks. Fires after Phase 1.

CC-32H: Restructured from single synchronous pipeline to two-phase design.
"""
import logging
import time
import threading

from django.utils import timezone

from core.models.core import Game, Team, Round
from core.models.decisions import DecisionSubmission
from core.engine.utils import RoundContext

logger = logging.getLogger('engine')


def advance_round(game_id, dry_run=False):
    """
    Main entry point. Runs Phase 1 synchronously, fires Phase 2 in background.

    Args:
        game_id: The game to advance.
        dry_run: If True, wraps everything in a transaction that gets
                 rolled back at the end. Phase 2 is skipped in dry_run mode.

    Returns:
        dict with phase_1_time and phase_2_status.
    """
    from django.db import transaction

    if dry_run:
        sid = transaction.savepoint()

    try:
        context = _run_phase_1(game_id)
        phase_1_time = context._phase_1_time

        if dry_run:
            transaction.savepoint_rollback(sid)
            return {'phase_1_time': phase_1_time, 'phase_2_status': 'skipped_dry_run'}

        # Phase 2: background LLM calls
        game = Game.objects.get(id=game_id)
        round_obj = Round.objects.filter(
            game=game, round_number=context.round_number,
        ).first()

        if round_obj:
            thread = threading.Thread(
                target=_run_phase_2,
                args=(game.id, round_obj.id),
                daemon=True,
            )
            thread.start()
            logger.info("Phase 2 dispatched to background thread")

        return {'phase_1_time': phase_1_time, 'phase_2_status': 'dispatched'}

    except Exception:
        if dry_run:
            transaction.savepoint_rollback(sid)
        raise


def _run_phase_1(game_id):
    """Phase 1: All deterministic calculations. No LLM calls."""
    start = time.time()

    game = Game.objects.get(id=game_id)

    # Determine current round
    current_round_obj = Round.objects.filter(
        game=game, status='open',
    ).order_by('round_number').first()

    if not current_round_obj:
        raise ValueError(f'No open round found for game "{game.name}" (ID: {game_id})')

    current_round = current_round_obj.round_number

    # Mark processing started
    current_round_obj.processing_status = 'PROCESSING'
    current_round_obj.save(update_fields=['processing_status'])

    # Verify all teams have locked decisions (auto-lock empty submissions)
    teams = Team.objects.filter(game=game)
    for team in teams:
        submission = DecisionSubmission.objects.filter(
            team=team,
            round=current_round_obj,
        ).first()
        if not submission:
            submission = DecisionSubmission.objects.create(
                team=team,
                round=current_round_obj,
                status='locked',
                locked_at=timezone.now(),
            )
        elif submission.status != 'locked':
            submission.status = 'locked'
            submission.locked_at = timezone.now()
            submission.save(update_fields=['status', 'locked_at'])

    # Build context
    context = RoundContext(game, current_round)

    # CC-32H: Skip RAG calls in Phase 1 — deferred to Phase 2
    context.skip_rag = True

    # === CC-5 Steps (1-9) ===

    from core.engine.events import fire_events, update_market_conditions, process_event_responses
    fire_events(context)
    update_market_conditions(context)

    # Step 2.5: Process event responses (CC-7)
    process_event_responses(context)

    from core.engine.rd_processing import process_rd
    process_rd(context)

    from core.engine.strategy_effects import apply_strategy_effects
    apply_strategy_effects(context)

    # Step 4.5: Talent processing (CC-16)
    from core.engine.talent import process_talent
    process_talent(context)

    # Step 4.55: Organizational structure modifiers (CC-32B)
    from core.engine.org_structure import apply_org_structure_modifiers
    try:
        apply_org_structure_modifiers(context)
    except Exception as e:
        context.log.append(f'CC-32B org structure failed: {e}')

    # Step 4.6: Acquisition processing (CC-20)
    from core.engine.acquisitions import process_acquisitions
    process_acquisitions(context)

    # Step 4.7: Alliance satisfaction processing (CC-32D)
    from core.engine.alliance_engine import process_alliances
    try:
        process_alliances(context)
    except Exception as e:
        context.log.append(f'CC-32D alliance processing failed: {e}')

    from core.engine.preference_engine import calculate_fit_scores
    calculate_fit_scores(context)

    from core.engine.campaign_engine import apply_campaign_multipliers
    apply_campaign_multipliers(context)

    from core.engine.readiness_engine import apply_readiness_gating
    apply_readiness_gating(context)

    from core.engine.bass_engine import run_bass_adoption
    run_bass_adoption(context)

    # === CC-6 Steps (10-17) ===

    # Step 10: Revenue
    from core.engine.revenue import calculate_revenue
    calculate_revenue(context)

    # Step 11: Costs
    from core.engine.costs import (
        calculate_cogs, calculate_logistics_tariffs,
        calculate_operating_expenses, calculate_interest,
        calculate_tax, calculate_inventory_costs, calculate_retirement_costs,
        calculate_repatriation_costs, calculate_entry_mode_overhead,
        process_tax_structure_costs,
    )
    calculate_cogs(context)
    calculate_logistics_tariffs(context)
    calculate_entry_mode_overhead(context)  # CC-31A B7: before opex
    # CC-32B: Org structure overhead
    from core.engine.org_structure import calculate_org_structure_costs
    try:
        calculate_org_structure_costs(context)
    except Exception as e:
        context.log.append(f'CC-32B org structure costs failed: {e}')
    calculate_operating_expenses(context)
    calculate_interest(context)
    calculate_tax(context)
    calculate_repatriation_costs(context)  # CC-31A B6: after tax, uses market_profit
    # CC-32C: Tax structure maintenance + audit rolls (after tax & repatriation)
    try:
        process_tax_structure_costs(context)
    except Exception as e:
        context.log.append(f'CC-32C tax structure processing failed: {e}')
    calculate_inventory_costs(context)
    calculate_retirement_costs(context)

    # Step 12: Financial statements
    from core.engine.financials import generate_financial_statements
    generate_financial_statements(context)

    # Step 12.5: CC-24 — Record strategic investment economic impacts
    from core.engine.strategic_economics import (
        record_esg_impacts, record_talent_impacts, record_partnership_impacts,
    )
    try:
        record_esg_impacts(context)
        record_talent_impacts(context)
        record_partnership_impacts(context)
    except Exception as e:
        context.log.append(f'CC-24 impact recording failed: {e}')

    # Step 12.7: CC-25 — Calculate derived features from financial outcomes
    from core.engine.derived_features import calculate_derived_features
    try:
        calculate_derived_features(context)
    except Exception as e:
        context.log.append(f'CC-25 derived features failed: {e}')

    # Step 12.8: CC-26 — AI Capital Markets (investor trading + share price)
    from core.engine.capital_markets import process_capital_markets
    try:
        process_capital_markets(context)
    except Exception as e:
        context.log.append(f'CC-26 capital markets failed: {e}')

    # Step 13: Performance index
    from core.engine.performance import calculate_performance_index
    calculate_performance_index(context)

    # Step 14: Strategic coherence (formula only — RAG deferred to Phase 2)
    from core.engine.coherence import calculate_coherence
    calculate_coherence(context, skip_rag=True)

    # Step 14.5: CC-32E — Agent Orchestrator (deterministic actions + template narratives)
    agent_results = {'actions': [], 'narratives': [], 'convergence_iterations': 0}
    try:
        from core.engine.agents.orchestrator import run_agent_cycle
        agent_results = run_agent_cycle(game, current_round_obj, context)
        context.log.append(
            f'CC-32E: Agent cycle complete — {len(agent_results["actions"])} actions, '
            f'{len(agent_results["narratives"])} narratives, '
            f'{agent_results["convergence_iterations"]} iterations'
        )
    except Exception as e:
        context.log.append(f'CC-32E agent orchestrator failed: {e}')

    # Step 15: Leaderboard
    from core.engine.leaderboard import update_leaderboard
    update_leaderboard(context)

    # Step 16: Instructor alerts (deterministic — no RAG enhancement)
    try:
        from core.engine.instructor_alerts import generate_post_round_alerts
        alert_count = generate_post_round_alerts(game, current_round)
        context.log.append(f'Generated {alert_count} instructor alerts')
    except Exception as e:
        context.log.append(f'Instructor alert generation failed: {e}')

    # Step 17: Advance round
    current_round_obj.status = 'processed'
    current_round_obj.processed_at = timezone.now()
    current_round_obj.processing_status = 'RESULTS_AVAILABLE'
    phase_1_time = time.time() - start
    current_round_obj.phase_1_duration = phase_1_time
    current_round_obj.save()

    next_round_num = current_round + 1
    if next_round_num <= game.scenario.num_rounds:
        next_round, created = Round.objects.get_or_create(
            game=game, round_number=next_round_num,
            defaults={'status': 'open', 'opened_at': timezone.now()},
        )
        if not created and next_round.status == 'pending':
            next_round.status = 'open'
            next_round.opened_at = timezone.now()
            next_round.save()
        game.current_round = next_round_num
    else:
        game.status = 'completed'

    game.save()

    logger.info(f'Phase 1 complete: {phase_1_time:.1f}s')
    context.log.append(f'Round {current_round} processed (Phase 1: {phase_1_time:.1f}s)')

    # Stash timing on context for caller
    context._phase_1_time = phase_1_time
    context._round_number = current_round

    return context


def _run_phase_2(game_id, round_id):
    """
    Phase 2: All LLM calls, run concurrently in background thread.
    Called from a daemon thread after Phase 1 completes.
    """
    from django.db import connection
    connection.ensure_connection()

    start = time.time()

    try:
        game = Game.objects.get(id=game_id)
        round_obj = Round.objects.get(id=round_id)

        from core.engine.narratives import generate_round_narratives
        generate_round_narratives(game, round_obj)

        phase_2_time = time.time() - start
        logger.info(f'Phase 2 complete: {phase_2_time:.1f}s')

        round_obj.processing_status = 'FULLY_COMPLETE'
        round_obj.narrative_generated = True
        round_obj.phase_2_duration = phase_2_time
        round_obj.narrative_error = ''
        round_obj.save(update_fields=[
            'processing_status', 'narrative_generated',
            'phase_2_duration', 'narrative_error',
        ])

    except Exception as e:
        logger.error(f'Phase 2 failed: {e}')
        try:
            round_obj = Round.objects.get(id=round_id)
            # Don't downgrade — numbers are still valid
            round_obj.narrative_error = str(e)[:500]
            round_obj.save(update_fields=['narrative_error'])
        except Exception:
            pass
    finally:
        connection.close()
