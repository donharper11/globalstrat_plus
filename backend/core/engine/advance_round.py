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

    # Ruling 2: the deadline is where an out-of-band or missing price becomes
    # a legal one. Deliberately before the freeze below, so the submission
    # snapshot each lock event records already holds the price that will
    # actually be scored.
    _apply_price_band(game, round_obj)

    # Decision 14: the deadline may not spend what the lock would refuse.
    # Deliberately before the freeze below and after the price band, for the
    # same reason the band is: the submission snapshot each lock event records
    # has to be the submission the round will actually be resolved from.
    # Only a draft is touched -- a team that locked its own submission passed
    # this same check at the lock.
    from core.services.deadline_affordability import (
        bring_draft_within_available_funds)
    trimmed = bring_draft_within_available_funds(game, round_obj)

    # Freeze whatever each team had at the moment of close, so late edits
    # can't slip in and so processing sees a stable snapshot.
    locked = _lock_all_submissions(game, round_obj)

    logger.info(
        'Closed round %s of game %s (reason=%s, %s submissions locked, '
        '%s drafts brought within available funds)',
        round_obj.round_number, game_id, reason, locked, len(trimmed),
    )
    return {'changed': True, 'round': round_obj.round_number,
            'status': 'closed', 'submissions_locked': locked,
            'unaffordable_drafts_trimmed': trimmed,
            'reason': reason}


def _apply_price_band(game, round_obj, *, scenario=None):
    """Bring every out-of-band and every missing price inside the legal range.

    Stage 5, Ruling 2. Two cases, and the difference between them is the whole
    rule:

      * a price OUTSIDE the band is moved to the NEARER edge -- the smallest
        change that makes the team's own decision legal;
      * a product-market with NO marketing decision at all is priced at the
        band FLOOR. In GlobalStrat a missing row is how "blank" manifests: the
        serializer refuses a price of zero and the pricing screen drops an
        unpriced row from its payload, so there is no row to correct and one
        has to be written.

    Every change writes a ``DecisionAuditEvent`` with ``user=None`` -- actor
    ``system`` on the instructor drill-down -- carrying the submitted value,
    the applied value and the rule. Without that record the substitution would
    make dispute 2 unanswerable, which is the objection BECSR avoids by
    refusing instead of substituting.

    Runs over every active team's submission REGARDLESS of lock state. A team
    that locked early is still subject to the deadline rule, and
    ``_lock_all_submissions`` deliberately skips an already-locked submission,
    so folding this into that loop would exempt precisely the teams that
    submitted on time.
    """
    from decimal import Decimal
    from core.models import DecisionAuditEvent
    from core.models.decisions import DecisionMarketing
    from core.models.team_state import TeamProductMarket
    from core.services import price_band as band_rules

    scenario = scenario or game.scenario
    zero = Decimal('0')
    changed = 0

    for team in Team.objects.filter(
        game=game, participation_status='active',
    ).order_by('id'):
        submission = DecisionSubmission.objects.filter(
            team=team, round=round_obj,
        ).first()
        if not submission:
            # A team with no submission gets one from _lock_all_submissions;
            # it has no products priced and nothing to bring into band.
            continue

        for md in (DecisionMarketing.objects
                   .filter(submission=submission)
                   .select_related('team_product', 'market')
                   .order_by('id')):
            band = band_rules.price_band(
                scenario, team, md.team_product, md.market,
                round_obj.round_number)

            if md.retail_price is None:
                # The blank branch, and only for a product the team is
                # actually selling: `blank_price` returns a floor only when
                # the anchor is a real prior-round price. A blank on a product
                # that has never sold here is left blank, refused at lock by
                # `_full_validate` and again by the engine precondition.
                floor = band_rules.blank_price(band)
                if floor is None:
                    # NOT FOR SALE this round (owner's ruling, 2026-09-12).
                    # Nothing sold here last round, so there is no floor to
                    # fall back on and no price the system may invent. The
                    # round must still resolve -- there is no supported
                    # operator surface that could supply the missing price, so
                    # refusing would stall a whole heat over one team's
                    # oversight. The row is left unpriced and is excluded from
                    # the offer map at source in `bass_engine`, so the product
                    # takes no demand and displaces no rival. The team's row is
                    # NOT deleted: it is their decision record, and this
                    # receipt is what tells them on their results screen why
                    # the product did not sell.
                    DecisionAuditEvent.objects.create(
                        game=game, team=team, round=round_obj, user=None,
                        action=band_rules.ACTION_NOT_OFFERED,
                        endpoint='engine:close_round',
                        payload=band_rules.audit_payload(
                            team_product=md.team_product, market=md.market,
                            band=band, submitted=None, applied=None,
                            rule=band_rules.RULE_NOT_OFFERED))
                    changed += 1
                    continue
                applied, rule, action = (floor, band_rules.RULE_BLANK,
                                         band_rules.ACTION_BLANK_DEFAULTED)
            else:
                applied, status = band_rules.adjusted_price(
                    md.retail_price, band)
                if status in (band_rules.IN_BAND, band_rules.NO_ANCHOR):
                    continue
                rule, action = (band_rules.RULE_OUT_OF_BAND,
                                band_rules.ACTION_ADJUSTED)

            payload = band_rules.audit_payload(
                team_product=md.team_product, market=md.market, band=band,
                submitted=md.retail_price, applied=applied, rule=rule)
            md.retail_price = applied
            md.save(update_fields=['retail_price'])
            DecisionAuditEvent.objects.create(
                game=game, team=team, round=round_obj, user=None,
                action=action, endpoint='engine:close_round', payload=payload)
            changed += 1

    if changed:
        logger.info('Price band applied to %s decision(s) in game %s round %s',
                    changed, game.id, round_obj.round_number)
    return changed


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

    # R10 / V2-053: feature-level R&D investment is retired, so any stored row
    # is refused rather than ignored -- an ignored row is a team's decision
    # silently not happening while they are charged for the rest of the same
    # submission. Ruling 1's narrower "ready platforms are frozen" rule is
    # subsumed: a row naming a ready platform is refused a fortiori.
    from core.services.rd_costs import persisted_retired_rd_violations
    frozen_violations = persisted_retired_rd_violations(
        game, current_round_obj)
    if frozen_violations:
        detail = '; '.join(
            f"{v['model']} row {v['row']} ({v['team']}) targets "
            f"\"{v['platform']}\" [{v['platform_status']}]"
            for v in frozen_violations)
        raise InvalidPersistedDecisionError(
            f'Round {current_round} cannot be scored: '
            f'{len(frozen_violations)} stored R&D investment(s) remain, and '
            f'feature-level R&D investment is retired (R10). Develop a new '
            f'platform and re-base the product onto it. '
            f'{detail}'
        )

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

    # Existing platform state that already violates one-per-generation. This
    # is state rather than a decision: runtime f39b853 could create it from a
    # supported duplicate submission, so an upgrade from that revision can
    # carry it in. Refused, never repaired -- deleting, retiring or merging a
    # row would silently discard competition state.
    from core.services.rd_costs import (describe_state_conflicts,
                                        duplicate_platform_state,
                                        persisted_held_generation_violations)
    state_conflicts = duplicate_platform_state(game)
    if state_conflicts:
        raise InvalidPersistedDecisionError(
            f'Round {current_round} cannot be scored: '
            f'{len(state_conflicts)} team/generation pair(s) hold more than one '
            f'non-retired platform. Correct the rows and retry. '
            f'{describe_state_conflicts(state_conflicts)}'
        )

    # V2-047: a stored request for a generation the team already holds. The
    # engine would skip it and book nothing, replacing the stored decision with
    # no decision at all.
    held_violations = persisted_held_generation_violations(game,
                                                           current_round_obj)
    if held_violations:
        raise InvalidPersistedDecisionError(
            f'Round {current_round} cannot be scored: '
            f'{len(held_violations)} stored platform development(s) request a '
            f'generation the team already holds. Correct the row(s) and retry. '
            f'{describe_state_conflicts(held_violations)}'
        )

    # Every active product must resolve to exactly one platform it owns, for
    # this round. The check defect B needed and did not have: a reconciliation
    # that sums the rows it finds cannot see a row that is absent, so BECSR's
    # demand-sold-lost balance stayed at zero while a whole product's demand
    # went unreconciled.
    from core.services.product_platform import (describe_missing_resolutions,
                                                missing_platform_resolutions)
    unresolved = missing_platform_resolutions(game, current_round)
    if unresolved:
        raise InvalidPersistedDecisionError(
            f'Round {current_round} cannot be scored: '
            f'{len(unresolved)} active product(s) do not resolve to a platform '
            f'this team owns for this round. Correct the rows and retry. '
            f'{describe_missing_resolutions(unresolved)}'
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

    # Stage 5: a price the deadline could not resolve must never reach the
    # demand path. `bass_engine` calls float() on `retail_price` when it builds
    # its price map, so a null would raise partway through a round that had
    # already moved. Refused here, before the first competitive write, naming
    # the rows to correct — the fail-closed shape V2-018 uses. Reachable when a
    # round is processed without ever being closed, and when a team leaves the
    # price out on a product that has never sold in that market (no prior-round
    # price, so the blank floor deliberately does not apply).
    from core.models.decisions import DecisionMarketing as _UnpricedCheck
    from core.services import price_band as _band_rules
    unresolved = []
    for row in (_UnpricedCheck.objects
                .filter(submission__round=current_round_obj,
                        retail_price__isnull=True)
                .select_related('team_product', 'market', 'submission__team')
                .order_by('submission__team_id', 'team_product_id',
                          'market_id')):
        band = _band_rules.price_band(
            game.scenario, row.submission.team, row.team_product, row.market,
            current_round)
        # Only a row the DEADLINE SHOULD HAVE RESOLVED. A row with a
        # prior-round price that is still null means `close_round` never ran
        # over this round, which is the skipped-deadline case this guard
        # exists for. A row with no prior-round price is legitimately unpriced
        # and not for sale, and must NOT stop the round -- that was the defect
        # in the first version of this precondition.
        if _band_rules.blank_price(band) is not None:
            unresolved.append(row)
    if unresolved:
        detail = '; '.join(
            f'{row.submission.team.name}: {row.team_product.name} in '
            f'{row.market.name}' for row in unresolved[:10])
        raise RoundNotReadyError(
            f'Round {current_round} cannot be scored: {len(unresolved)} '
            f'product-market decision(s) carry no unit price although a '
            f'previous price exists to resolve them from, which means the '
            f'round was never closed. Close the round, or set a price on '
            f'each, and retry. {detail}')

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

    # Step 16.5: R18 — a product retired `end_of_round` sold through this
    # round and retires now that the round has resolved. Deliberately the last
    # deterministic mutation of Phase 1: everything above -- adoption, revenue,
    # costs, financials, the performance index, coherence and the leaderboard
    # -- saw the product as it was all round, which is what "sells through that
    # round" means. From the next round it is retired and off sale.
    #
    # `immediate` is unaffected: it is applied in `process_rd`, before
    # adoption, and stops sales at once. The two timings now differ in market
    # timing as well as in fire-sale recovery, so neither dominates (V2-070).
    #
    # Inside the hashed envelope: `complete_manifest` runs after this returns,
    # so the round's snapshot carries the retired state. No manifest section
    # and no field changes, so MANIFEST_SCHEMA_VERSION does not move.
    from core.engine.rd_processing import apply_end_of_round_retirements
    apply_end_of_round_retirements(context)

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
