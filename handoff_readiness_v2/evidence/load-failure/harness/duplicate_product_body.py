"""Engine-side half of the duplicate-product-name probe.

Locks with the core decisions only. The optional baseline rows rewrite a
submission's product_creates wholesale, which would erase the very rows the
student wrote through the API -- and those rows are the point of this probe.
"""
from django.utils import timezone


def platform_for(game, team_id):
    """The team's own platform and markets, so a product create is well formed."""
    from core.models import Team
    from core.models.team_state import TeamMarketPresence, TeamPlatform, TeamProduct
    team = Team.objects.get(id=team_id)
    platform = TeamPlatform.objects.filter(team=team).order_by('id').first()
    markets = list(TeamMarketPresence.objects
                   .filter(team=team, status='active')
                   .values_list('market_id', flat=True))
    existing = TeamProduct.objects.filter(team=team, status='active').first()
    return {
        'team_platform_id': platform.id if platform else None,
        'positioning': existing.positioning if existing else 'mainstream',
        'market_ids': markets[:1] or list(
            TeamMarketPresence.objects.filter(team=team)
            .values_list('market_id', flat=True)[:1]),
    }


def _lock_core_only(game, rnd):
    import baseline as BASE
    from core.models import DecisionSubmission, Team
    for team in Team.objects.filter(game=game, participation_status='active'):
        submission, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=rnd, defaults={'status': 'draft'})
        BASE.build(submission, team)
        submission.status = 'locked'
        submission.locked_at = timezone.now()
        submission.save(update_fields=['status', 'locked_at'])


def _duplicate_names(game):
    from collections import Counter
    from core.models.team_state import TeamProduct
    counts = Counter(TeamProduct.objects.filter(team__game=game)
                     .values_list('team_id', 'name'))
    return [{'team_id': t, 'name': n, 'rows': c}
            for (t, n), c in counts.items() if c > 1]


def _attempt(game):
    from core.engine.advance_round import process_round
    try:
        process_round(game.id)
        return None
    except Exception as exc:
        return f'{type(exc).__name__}: {str(exc)[:220]}'


def _round(game):
    from core.models import Round
    game.refresh_from_db()
    return Round.objects.get(game=game, round_number=game.current_round)


def variant_a_same_name_twice(game, team_id):
    """Two creates with the same name in one submission.

    The manifest's decision_product_create section keys on
    (submission_id, product_name), so this is refused at prepare_manifest --
    before Phase 1, in the round the student submitted it for.
    """
    from core.engine.advance_round import advance_to_next_round
    from core.models.decisions import DecisionProductCreate

    rnd = _round(game)
    _lock_core_only(game, rnd)
    first = _attempt(game)
    retry = _attempt(game)
    rnd.refresh_from_db()

    # Recovery: drop one of the two rows. There is no operator-facing action
    # for this -- it is a direct database edit -- so record what it takes.
    blocked_status = rnd.status
    rows = list(DecisionProductCreate.objects
                .filter(submission__team_id=team_id, submission__round=rnd)
                .order_by('id').values_list('id', flat=True))
    if len(rows) > 1:
        DecisionProductCreate.objects.filter(id=rows[-1]).delete()
    after_fix = _attempt(game)
    rnd.refresh_from_db()
    resolved = rnd.status == 'processed'
    if resolved:
        advance_to_next_round(game.id)
        game.refresh_from_db()   # advance bumps the row, not this instance
    return {
        'blocked_error': first,
        'retry_error': retry,
        'blocked_round_status': blocked_status,
        'blocked': bool(first) and blocked_status != 'processed',
        'still_blocked_on_retry': bool(retry),
        'recovery': 'delete one duplicate decision row directly in the database',
        'recovery_error': after_fix,
        'resolves_after_recovery': resolved,
        'next_round_number': game.current_round if resolved else None,
    }


def variant_b_name_of_existing_product(game, team_id):
    """One create whose name matches a product the team already owns.

    This does not block where I first predicted. The decision rows are
    unique, so prepare_manifest passes and Phase 1 runs and creates the second
    TeamProduct. complete_manifest then snapshots the *output* state, trips the
    team_product key (team_id, name), and the whole resolution rolls back --
    complete_manifest is inside the same transaction as Phase 1
    (advance_round.py:230).

    That is a better outcome than a game left permanently unresolvable: no
    duplicate is ever persisted, and Phase 1's work is discarded with it. It
    is still a round an instructor cannot close, from a student write the API
    accepted with a 200.
    """
    from core.models.decisions import DecisionProductCreate
    from core.models.team_state import TeamProduct

    rnd = _round(game)
    products_before = TeamProduct.objects.filter(team_id=team_id).count()
    _lock_core_only(game, rnd)
    blocked = _attempt(game)
    retry = _attempt(game)
    rnd.refresh_from_db()

    result = {
        'blocked_error': blocked,
        'retry_error': retry,
        'blocked_round_status': rnd.status,
        'blocked': bool(blocked) and rnd.status != 'processed',
        'still_blocked_on_retry': bool(retry),
        'fails_at': 'complete_manifest, after Phase 1, inside the same '
                    'transaction (advance_round.py:230)',
        'duplicate_products_persisted': _duplicate_names(game),
        'phase_1_work_rolled_back':
            TeamProduct.objects.filter(team_id=team_id).count() == products_before,
    }

    # Recovery: remove the offending decision row. Same shape as variant A,
    # and same absence of any operator-facing way to do it.
    DecisionProductCreate.objects.filter(
        submission__team_id=team_id, submission__round=rnd,
        product_name='Vanguard One').delete()
    result['recovery'] = 'delete the offending decision row directly in the database'
    result['recovery_error'] = _attempt(game)
    rnd.refresh_from_db()
    result['resolves_after_recovery'] = rnd.status == 'processed'
    return result
