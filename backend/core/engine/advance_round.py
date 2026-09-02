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

from django.db import transaction
from django.utils import timezone

from core.models.core import Game, Team, Round
from core.models.decisions import DecisionSubmission
from core.engine.utils import RoundContext

logger = logging.getLogger('engine')

# Distinct, greppable/alertable marker for supply-chain engine failures (W6).
SC_FAILURE_MARKER = '[SC-ENGINE-FAILURE]'


class RoundNotReadyError(ValueError):
    """A precondition for processing is unmet (operator-fixable), e.g. a team's
    decisions are not locked. Distinct from an engine failure so callers can
    report it as an actionable 400 rather than a 500."""


class EquityExceedsFundingNeedError(RoundNotReadyError):
    """A stored financing row raises more equity than the round needs.

    V2-024. Equity may finance a genuine current-round funding shortfall; it
    may not create surplus cash or fund a dividend. Refused rather than
    clamped, and refused before the first competitive write, because a
    persisted row can arrive from admin, a shell or a restore without ever
    passing the serializer.
    """


class InvalidScenarioConfigurationError(RoundNotReadyError):
    """The scenario is missing a value scoring cannot proceed without.

    A subclass of `RoundNotReadyError` for the same reason as its sibling
    below: an operator fixes the scenario and retries, so it is an actionable
    400 rather than an engine failure.

    Checked before any competitive write. The V2-023 disposition requires
    configuration to fail closed rather than fall back to a team or cohort
    price, and a fallback discovered halfway through resolution would already
    have mutated state.
    """


class InvalidPersistedDecisionError(RoundNotReadyError):
    """A stored decision row holds a value the decision rules forbid.

    Separate from `RoundNotReadyError` so it can be recognised, and a subclass
    of it so existing callers keep reporting it as an actionable 400: like an
    unlocked team, it is something an operator fixes and retries.

    The engine refuses rather than correcting the value. A negative investment
    that scoring clamps to zero is a team's decision quietly replaced with a
    different one, and the result looks ordinary. Refusing is louder and
    truthful.
    """


def _run_sc_step(step_name, fn, context):
    """Run a supply-chain step and fail the atomic resolution on error."""
    try:
        fn(context)
    except Exception as e:
        game_id = getattr(getattr(context, 'game', None), 'id', '?')
        round_number = getattr(context, 'round_number', '?')
        logger.error(
            '%s step=%s game=%s round=%s: %s',
            SC_FAILURE_MARKER, step_name, game_id, round_number, e,
            exc_info=True,
        )
        context.log.append(f'{SC_FAILURE_MARKER} {step_name} failed: {e}')
        raise


def get_current_round(game):
    """The Round the game is currently sitting on, whatever its status."""
    return Round.objects.filter(
        game=game, round_number=game.current_round,
    ).first()


@transaction.atomic
def close_round(game_id, reason='manual'):
    """
    Stop accepting decisions for the current round.

    This is the deadline action: it locks students out but computes nothing.
    Processing is a separate, instructor-triggered step (process_round).
    Idempotent — closing an already-closed round is a no-op.
    """
    from core.services.competition_locks import lock_game_for_lifecycle
    # Step 1 of the documented lock order. It lets already-active decision
    # transactions commit, then holds subsequent writes — and every other
    # operator action — behind close until this transaction ends.
    lock_game_for_lifecycle(game_id)
    game = Game.objects.select_for_update().get(id=game_id)
    round_obj = Round.objects.select_for_update().filter(
        game=game, round_number=game.current_round).first()
    if not round_obj:
        raise ValueError(f'Game "{game.name}" has no round {game.current_round}.')

    if round_obj.status in ('closed', 'processed'):
        return {'changed': False, 'round': round_obj.round_number,
                'status': round_obj.status}

    round_obj.status = 'closed'
    round_obj.closed_at = timezone.now()
    round_obj.close_reason = reason
    # `decisions_locked` is a projection of round status, not a second source
    # of truth. The student write path reads it directly, so a round that is
    # closed while the flag says otherwise would let a team keep writing. It is
    # only ever set here and cleared by reopen.
    round_obj.decisions_locked = True
    round_obj.lock_reason = reason[:64]
    round_obj.save(update_fields=['status', 'closed_at', 'close_reason',
                                  'decisions_locked', 'lock_reason'])

    # Freeze whatever each team had at the moment of close, so late edits
    # can't slip in and so processing sees a stable snapshot.
    locked = _lock_all_submissions(game, round_obj)

    logger.info(
        'Closed round %s of game %s (reason=%s, %s submissions locked)',
        round_obj.round_number, game_id, reason, locked,
    )
    return {'changed': True, 'round': round_obj.round_number,
            'status': 'closed', 'submissions_locked': locked,
            'reason': reason}


def _lock_all_submissions(game, round_obj):
    """Lock every team's submission for this round, creating empty ones."""
    count = 0
    for team in Team.objects.filter(game=game, participation_status='active').order_by('id'):
        submission = DecisionSubmission.objects.filter(
            team=team, round=round_obj,
        ).first()
        if not submission:
            submission = DecisionSubmission.objects.create(
                team=team, round=round_obj,
                status='locked', locked_at=timezone.now(),
            )
            action = 'missing_submission_defaulted'
            count += 1
        elif submission.status != 'locked':
            submission.status = 'locked'
            submission.locked_at = timezone.now()
            submission.save(update_fields=['status', 'locked_at'])
            action = 'deadline_lock'
            count += 1
        else:
            continue
        from core.models import DecisionAuditEvent
        from core.serializers.decisions import DecisionSubmissionSerializer
        DecisionAuditEvent.objects.create(
            game=game, team=team, round=round_obj, user=None, action=action,
            endpoint='engine:close_round',
            payload=DecisionSubmissionSerializer(submission).data,
        )
    return count


def process_round(game_id, dry_run=False):
    """
    Run end-of-round scoring for the current round. Does NOT advance the game.

    Phase 1 (deterministic maths) runs synchronously; Phase 2 (LLM narratives)
    is dispatched to a background thread. Afterwards the round is 'processed'
    and results are visible, but the game stays on this round until an
    instructor calls advance_to_next_round().
    """
    from django.db import transaction

    # Checked before the transaction opens, so a misconfigured stack fails
    # without taking a backup or a lock.
    from core.services.narrative_jobs import require_safe_rag_configuration
    require_safe_rag_configuration()

    try:
        # One transaction owns the resolution claim, recovery snapshot,
        # manifests, and deterministic mutations. A concurrent caller waits
        # here, then observes `processed` before it can take another snapshot.
        with transaction.atomic():
            from core.services.competition_locks import lock_game_for_lifecycle
            # Step 1 of the documented lock order, before any row lock. A
            # caller that already holds it (an operator view) re-acquires it
            # harmlessly; a caller that does not — a management command, the
            # deadline scheduler — gets the same serialisation.
            lock_game_for_lifecycle(game_id)
            game_for_backup = Game.objects.select_for_update().get(id=game_id)
            round_for_backup = Round.objects.select_for_update().filter(
                game=game_for_backup,
                round_number=game_for_backup.current_round,
            ).first()
            if not round_for_backup:
                raise ValueError(
                    f'No round {game_for_backup.current_round} found for game '
                    f'"{game_for_backup.name}".')
            if round_for_backup.status == 'processed':
                raise ValueError(
                    f'Round {round_for_backup.round_number} has already been processed.')

            from core.services.competition_backup import backup_before_resolution
            backup_path = backup_before_resolution(game_id, round_for_backup.round_number)
            from core.services.resolution_manifest import prepare_manifest
            prepare_manifest(game_for_backup, round_for_backup, backup_path)
            context = _run_phase_1(game_id)
            phase_1_time = context._phase_1_time

            if dry_run:
                transaction.set_rollback(True)
                return {'phase_1_time': phase_1_time,
                        'phase_2_status': 'skipped_dry_run'}

            from core.services.resolution_manifest import complete_manifest
            complete_manifest(round_for_backup)
            # Enqueued in the transaction that commits Phase 1: if the numbers
            # are durable, the outstanding narrative work is durable with them.
            # Before this, a worker restart between dispatch and completion
            # abandoned the work with nothing recording that it was owed.
            from core.services.narrative_jobs import enqueue_round
            enqueue_round(game_for_backup, round_for_backup)

        # Phase 2: background LLM calls, dispatched only once the resolution
        # is durable. on_commit fires after the *outermost* transaction
        # commits, so an operator view that wraps this call cannot have the
        # narrative thread reading a round the database has not accepted yet.
        game = Game.objects.get(id=game_id)
        round_obj = Round.objects.filter(
            game=game, round_number=context._round_number,
        ).first()

        if round_obj:
            # The thread is now a convenience, not the mechanism: it drains the
            # queue promptly on a single-process deployment. The jobs are
            # already durable, so if it never starts — or dies mid-call — a
            # worker picks the same rows up.
            def _dispatch_phase_2(game_id=game.id, round_id=round_obj.id):
                thread = threading.Thread(
                    target=_run_phase_2, args=(game_id, round_id), daemon=True)
                thread.start()
                logger.info('Phase 2 dispatched to background thread')

            transaction.on_commit(_dispatch_phase_2)

        return {
            'processed_round': context._round_number,
            'phase_1_time': phase_1_time,
            'phase_2_status': 'dispatched',
        }

    except Exception:
        _mark_failed(game_id)
        raise


def _mark_failed(game_id):
    """Best-effort: flag the round FAILED so the console can show it."""
    try:
        game = Game.objects.get(id=game_id)
        round_obj = get_current_round(game)
        if round_obj and round_obj.status != 'processed':
            round_obj.processing_status = 'FAILED'
            round_obj.save(update_fields=['processing_status'])
    except Exception:
        pass


@transaction.atomic
def advance_to_next_round(game_id, force=False):
    """
    Open the next round. Requires the current round to be processed first,
    so results always exist before the game moves on (pass force=True to
    override).
    """
    from core.services.competition_locks import lock_game_for_lifecycle
    lock_game_for_lifecycle(game_id)
    game = Game.objects.select_for_update().get(id=game_id)
    round_obj = Round.objects.select_for_update().filter(
        game=game, round_number=game.current_round).first()
    if not round_obj:
        raise ValueError(f'Game "{game.name}" has no round {game.current_round}.')

    if round_obj.status != 'processed' and not force:
        raise ValueError(
            f'Round {round_obj.round_number} is "{round_obj.status}", not '
            f'"processed". Run post-round processing first, or force=True.'
        )

    current = round_obj.round_number
    total = game.scenario.num_rounds if game.scenario else current
    next_round_num = current + 1

    if next_round_num > total:
        game.status = 'completed'
        game.save(update_fields=['status'])
        logger.info('Game %s completed after round %s', game_id, current)
        return {'completed_round': current, 'next_round': None,
                'game_status': 'completed'}

    next_round, created = Round.objects.get_or_create(
        game=game, round_number=next_round_num,
        defaults={'status': 'open', 'opened_at': timezone.now()},
    )
    if not created and next_round.status in ('pending', 'closed'):
        next_round.status = 'open'
        next_round.opened_at = timezone.now()
        next_round.save(update_fields=['status', 'opened_at'])

    game.current_round = next_round_num
    game.save(update_fields=['current_round'])

    logger.info('Game %s advanced: round %s -> %s', game_id, current, next_round_num)
    return {'completed_round': current, 'next_round': next_round_num,
            'game_status': game.status,
            'next_deadline': next_round.deadline.isoformat()
                             if next_round.deadline else None}


def advance_round(game_id, dry_run=False):
    """
    Back-compat entry point: process the current round AND advance in one go.

    Prefer process_round() then advance_to_next_round(), which is the flow the
    instructor console drives.
    """
    result = process_round(game_id, dry_run=dry_run)
    if dry_run:
        return result

    advance = advance_to_next_round(game_id)
    result.update(advance)
    return result


@transaction.atomic
def _run_phase_1(game_id):
    """Phase 1: All deterministic calculations. No LLM calls."""
    start = time.time()

    game = Game.objects.select_for_update().get(id=game_id)

    # Process the round the game is actually on. This used to look up
    # status='open', which broke once a deadline could close a round before
    # processing.
    current_round_obj = Round.objects.select_for_update().filter(
        game=game, round_number=game.current_round).first()

    if not current_round_obj:
        raise ValueError(f'No round {game.current_round} found for game "{game.name}" (ID: {game_id})')

    if current_round_obj.status == 'processed':
        raise ValueError(
            f'Round {current_round_obj.round_number} has already been processed.'
        )
    if current_round_obj.status not in ('open', 'closed'):
        raise ValueError(
            f'Round {current_round_obj.round_number} is "{current_round_obj.status}" '
            f'and cannot be processed.'
        )

    current_round = current_round_obj.round_number

    # Verify all teams have locked decisions before any processing starts.
    # InstructorAdvanceRoundView can expose an explicit force path, but the
    # engine entry point itself must not silently create or lock submissions.
    teams = Team.objects.filter(
        game=game, participation_status='active',
    ).order_by('id')
    for team in teams:
        submission = DecisionSubmission.objects.filter(
            team=team,
            round=current_round_obj,
        ).first()
        if not submission or submission.status != 'locked':
            raise RoundNotReadyError(
                f'Team "{team.name}" has not locked decisions for round {current_round}. '
                f'Re-lock the team (or close the round) before processing.'
            )

    # The decision rules, asked of what is actually stored. The serializers
    # refuse a negative investment at both write paths, but the engine scores
    # rows, and rows can also arrive from a data migration, an import, the
    # admin, `manage.py shell` or a restore. V2-018: a negative value flows
    # into `strategy_expense` as income, and a negative headcount multiplied by
    # a salary band was worth fifty billion.
    from core.serializers.decision_limits import (describe_violations,
                                                  persisted_violations)
    violations = persisted_violations(game, current_round_obj)
    if violations:
        raise InvalidPersistedDecisionError(
            f'Round {current_round} cannot be scored: '
            f'{len(violations)} stored decision value(s) are negative where the '
            f'decision rules require zero or more. Correct the row(s) and '
            f'retry. {describe_violations(violations)}'
        )

    # V2-037: the authored price of R&D, asked of what is actually stored.
    # The write surfaces now set the price themselves, but rows reach this
    # table by other routes too, and the failure this guards is the one Stage 1
    # measured -- a $15,000,000 platform stored at committed_cost 0, activated,
    # and charged nothing. Refuse before any competitive mutation and name the
    # row: do not clamp and do not reinterpret, because a decision quietly
    # replaced with a different one looks ordinary afterwards.
    from core.services.rd_costs import (describe_cost_violations,
                                        persisted_cost_violations)
    cost_violations = persisted_cost_violations(game, current_round_obj)
    if cost_violations:
        raise InvalidPersistedDecisionError(
            f'Round {current_round} cannot be scored: '
            f'{len(cost_violations)} stored R&D cost(s) disagree with the '
            f'price this scenario authors. Correct the row(s) and retry. '
            f'{describe_cost_violations(cost_violations)}'
        )

    # V2-039: a stored development for a generation this round has not
    # unlocked. Same reason the cost guard runs here: the write surfaces now
    # refuse it, and rows arrive by other routes.
    from core.services.rd_costs import (describe_unlock_violations,
                                        persisted_unlock_violations)
    unlock_violations = persisted_unlock_violations(game, current_round_obj)
    if unlock_violations:
        raise InvalidPersistedDecisionError(
            f'Round {current_round} cannot be scored: '
            f'{len(unlock_violations)} stored platform development(s) name a '
            f'generation this round has not unlocked. Correct the row(s) and '
            f'retry. {describe_unlock_violations(unlock_violations)}'
        )

    # V2-044: a stored R&D investment naming another team's platform. The
    # write surfaces refuse it now; this is the boundary for rows that arrive
    # any other way, and for the default-close path that carried one into the
    # engine during Stage 1.
    from core.services.rd_costs import (describe_ownership_violations,
                                        persisted_ownership_violations)
    ownership_violations = persisted_ownership_violations(game,
                                                          current_round_obj)
    if ownership_violations:
        raise InvalidPersistedDecisionError(
            f'Round {current_round} cannot be scored: '
            f'{len(ownership_violations)} stored R&D investment(s) name a '
            f'platform the submitting team does not own. Correct the row(s) '
            f'and retry. {describe_ownership_violations(ownership_violations)}'
        )

    # An over-cap persisted feature set. Refused, not truncated: activation
    # used to slice it, producing a platform that disagreed with the decision
    # stored beside it.
    from core.services.rd_costs import (describe_feature_cap_violations,
                                        persisted_feature_cap_violations)
    cap_violations = persisted_feature_cap_violations(game, current_round_obj)
    if cap_violations:
        raise InvalidPersistedDecisionError(
            f'Round {current_round} cannot be scored: '
            f'{len(cap_violations)} stored platform development(s) name more '
            f'features than a platform may carry. Correct the row(s) and '
            f'retry. {describe_feature_cap_violations(cap_violations)}'
        )

    # V2-046: one generation requested twice in a submission. Refused rather
    # than de-duplicated: discarding a row would leave the stored decision and
    # the resolved decision disagreeing.
    from core.services.rd_costs import (
        describe_duplicate_generation_violations,
        persisted_duplicate_generation_violations)
    duplicate_violations = persisted_duplicate_generation_violations(
        game, current_round_obj)
    if duplicate_violations:
        raise InvalidPersistedDecisionError(
            f'Round {current_round} cannot be scored: '
            f'{len(duplicate_violations)} stored platform development(s) '
            f'request a generation their submission already names. Correct the '
            f'row(s) and retry. '
            f'{describe_duplicate_generation_violations(duplicate_violations)}'
        )

    # V2-024: equity raises are checked against the round's funding shortfall
    # before any competitive write, for the same reason the decision-limit
    # check above runs here -- a persisted row that never passed the
    # serializer is exactly the bypass the rule has to survive.
    from core.services import funding_need
    equity_violations = funding_need.violations(game, current_round_obj)
    if equity_violations:
        detail = '; '.join(
            funding_need.describe(v['assessment'], v['team'])
            for v in equity_violations)
        raise EquityExceedsFundingNeedError(
            f'Round {current_round} cannot be scored: '
            f'{len(equity_violations)} equity raise(s) exceed the funding '
            f'shortfall they claim to finance. Correct the row(s) and retry. '
            f'{detail}')

    # Scenario configuration is validated here, before the first competitive
    # write, so a missing or unusable value cannot be discovered halfway
    # through a round that has already mutated state (V2-023).
    from core.engine.utils import (InvalidScenarioConfiguration,
                                   scenario_high_price_elasticity,
                                   scenario_optimal_headcounts,
                                   scenario_reference_prices)
    try:
        scenario_reference_prices(game.scenario)
        scenario_high_price_elasticity(game.scenario)
        scenario_optimal_headcounts(game.scenario)
    except InvalidScenarioConfiguration as exc:
        raise InvalidScenarioConfigurationError(
            f'Round {current_round} cannot be scored: {exc} Set the value in '
            f'scenario configuration and retry.'
        ) from exc

    # Mark processing started only after preconditions pass.
    current_round_obj.processing_status = 'PROCESSING'
    current_round_obj.save(update_fields=['processing_status'])

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

    # CC-19B: Generate SC disruption state (fire SC events, carry recovery forward)
    # and compute each team's production capacity factor BEFORE revenue, so
    # Channel-1 lost sales throttle units in calculate_revenue.
    from core.engine.sc_engine import run_sc_state
    _run_sc_step('run_sc_state', run_sc_state, context)

    # CC-18: compliance enforcement — evaluate regimes, fire detentions, and set
    # market-access freezes BEFORE revenue so a frozen market blocks this round's
    # sales. Books remediation/penalty cost into context.compliance_costs.
    from core.engine.compliance_engine import enforce_compliance
    _run_sc_step('enforce_compliance', enforce_compliance, context)

    from core.engine.rd_processing import process_rd
    process_rd(context)

    from core.engine.strategy_effects import apply_strategy_effects
    apply_strategy_effects(context)

    # Step 4.5: Talent processing (CC-16)
    from core.engine.talent import process_talent
    process_talent(context)

    # Step 4.55: Organizational structure modifiers (CC-32B)
    from core.engine.org_structure import apply_org_structure_modifiers
    apply_org_structure_modifiers(context)

    # Step 4.6: Acquisition processing (CC-20)
    from core.engine.acquisitions import process_acquisitions
    process_acquisitions(context)

    # Step 4.7: Alliance satisfaction processing (CC-32D)
    from core.engine.alliance_engine import process_alliances
    process_alliances(context)

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
    calculate_org_structure_costs(context)
    calculate_operating_expenses(context)
    calculate_interest(context)
    calculate_tax(context)
    calculate_repatriation_costs(context)  # CC-31A B6: after tax, uses market_profit
    # CC-32C: Tax structure maintenance + audit rolls (after tax & repatriation)
    process_tax_structure_costs(context)
    calculate_inventory_costs(context)
    calculate_retirement_costs(context)

    # CC-19B Channel 2: supply-chain disruption costs (freight surcharge +
    # mitigation premiums) — a real operating expense booked in operating_income
    # by generate_financial_statements. Must run before financials.
    from core.engine.sc_engine import calculate_sc_disruption_costs
    _run_sc_step('calculate_sc_disruption_costs', calculate_sc_disruption_costs, context)

    # CC-20: FX hedge lifecycle (open -> mark-to-market -> settle). Books realized
    # P&L into pre-tax income via context.sc_fx_hedge_pnl. Needs revenue (exposure),
    # must run before financials.
    from core.engine.fx_engine import process_fx_hedges
    _run_sc_step('process_fx_hedges', process_fx_hedges, context)

    # Step 12: Financial statements
    from core.engine.financials import generate_financial_statements
    generate_financial_statements(context)

    # Step 12.5: CC-24 — Record strategic investment economic impacts
    from core.engine.strategic_economics import (
        record_esg_impacts, record_talent_impacts, record_partnership_impacts,
    )
    record_esg_impacts(context)
    record_talent_impacts(context)
    record_partnership_impacts(context)

    # Step 12.7: CC-25 — Calculate derived features from financial outcomes
    from core.engine.derived_features import calculate_derived_features
    calculate_derived_features(context)

    # Step 12.8: CC-26 — AI Capital Markets (investor trading + share price)
    from core.engine.capital_markets import process_capital_markets
    process_capital_markets(context)

    # Step 13: Performance index
    from core.engine.performance import calculate_performance_index
    calculate_performance_index(context)

    # Step 14: Strategic coherence (formula only — RAG deferred to Phase 2)
    from core.engine.coherence import calculate_coherence
    calculate_coherence(context, skip_rag=True)

    # Step 14.5: CC-32E — Agent Orchestrator (deterministic actions + template narratives)
    from core.engine.agents.orchestrator import run_agent_cycle
    agent_results = run_agent_cycle(game, current_round_obj, context)
    context.log.append(
        f'CC-32E: Agent cycle complete — {len(agent_results["actions"])} actions, '
        f'{len(agent_results["narratives"])} narratives, '
        f'{agent_results["convergence_iterations"]} iterations'
    )

    # Score supply-chain resilience before ranking because the published final
    # tie-break uses this round's resilience score.
    from core.engine.sc_engine import score_sc_resilience
    _run_sc_step('score_sc_resilience', score_sc_resilience, context)

    # Step 15: Leaderboard
    from core.engine.leaderboard import update_leaderboard
    update_leaderboard(context)

    # Step 16: Instructor alerts (deterministic — no RAG enhancement)
    from core.engine.instructor_alerts import generate_post_round_alerts
    alert_count = generate_post_round_alerts(game, current_round)
    context.log.append(f'Generated {alert_count} instructor alerts')

    # Step 17: Mark the round processed. Opening the next round is a separate,
    # instructor-triggered step — see advance_to_next_round().
    current_round_obj.status = 'processed'
    current_round_obj.processed_at = timezone.now()
    current_round_obj.processing_status = 'RESULTS_AVAILABLE'
    phase_1_time = time.time() - start
    current_round_obj.phase_1_duration = phase_1_time
    current_round_obj.save()

    logger.info(f'Phase 1 complete: {phase_1_time:.1f}s')
    context.log.append(f'Round {current_round} processed (Phase 1: {phase_1_time:.1f}s)')

    # Stash timing on context for caller
    context._phase_1_time = phase_1_time
    context._round_number = current_round

    return context


def _run_phase_2(game_id, round_id):
    """Drain this round's narrative jobs in-process.

    Kept for single-process deployments, where the alternative is an operator
    having to run a worker by hand. It claims through the same durable path a
    standalone worker uses, so the two cannot double-run a job, and it no
    longer *is* the mechanism: the rows outlive this thread.
    """
    from django.db import connection
    from core.services.narrative_jobs import drain
    connection.ensure_connection()

    start = time.time()
    try:
        drain(game_id=game_id)
        update_round_narrative_status(round_id, time.time() - start)
    except Exception as e:
        logger.error(f'Phase 2 drain failed: {e}')
    finally:
        connection.close()


def update_round_narrative_status(round_id, duration=None):
    """Project this round's job states onto the fields the console reads.

    The console has always shown `processing_status` / `narrative_error`, so
    those keep working — but they are now a *view* of the job rows rather than
    the only record, which is what makes an abrupt process death survivable.
    """
    from core.models.narrative_jobs import NarrativeJob
    round_obj = Round.objects.filter(id=round_id).first()
    if round_obj is None:
        return None
    jobs = list(NarrativeJob.objects.filter(round_id=round_id)
                .order_by('narrative_type', 'template_version'))
    if not jobs:
        return round_obj

    failed = [job for job in jobs if job.state == NarrativeJob.FAILED]
    outstanding = [job for job in jobs
                   if job.state in (NarrativeJob.PENDING, NarrativeJob.CLAIMED)]

    fields = ['narrative_generated', 'narrative_error']
    round_obj.narrative_generated = not outstanding and not failed
    round_obj.narrative_error = (
        '; '.join(f'{job.narrative_type}: {job.last_error}'
                  for job in failed)[:500] if failed else '')
    if not outstanding:
        # Never downgrade from a resolved state: the numbers stay valid whether
        # or not the prose arrived.
        round_obj.processing_status = (
            'FULLY_COMPLETE' if not failed else 'RESULTS_AVAILABLE')
        fields.append('processing_status')
    if duration is not None:
        round_obj.phase_2_duration = duration
        fields.append('phase_2_duration')
    round_obj.save(update_fields=fields)
    return round_obj
