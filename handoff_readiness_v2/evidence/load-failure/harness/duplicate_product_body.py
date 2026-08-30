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

    The decision rows are unique, so this round resolves. Phase 1 then creates
    a second TeamProduct sharing (team_id, name) with the first, and the
    team_product section keys on exactly that pair -- so the *next* round is
    the one that cannot be resolved, for every team in the game.
    """
    from core.engine.advance_round import advance_to_next_round
    from core.models.team_state import TeamProduct

    rnd = _round(game)
    _lock_core_only(game, rnd)
    creating_error = _attempt(game)
    rnd.refresh_from_db()
    created_ok = rnd.status == 'processed'
    duplicates = _duplicate_names(game)

    result = {
        'round_creating_the_duplicate_error': creating_error,
        'round_creating_the_duplicate_resolves': created_ok,
        'duplicate_products_created': duplicates,
    }
    if not created_ok:
        result['next_round_blocked'] = None
        return result

    advance_to_next_round(game.id)
    nxt = _round(game)
    _lock_core_only(game, nxt)
    blocked = _attempt(game)
    retry = _attempt(game)
    nxt.refresh_from_db()

    # Recovery needs a rename on a table the product exposes no writable name
    # field for. Confirm the rename is what unblocks it.
    dupe = duplicates[0] if duplicates else None
    fixed_error = None
    if dupe:
        rows = list(TeamProduct.objects
                    .filter(team_id=dupe['team_id'], name=dupe['name'])
                    .order_by('id').values_list('id', flat=True))
        TeamProduct.objects.filter(id=rows[-1]).update(name=dupe['name'] + ' (2)')
        fixed_error = _attempt(game)
        nxt.refresh_from_db()

    result.update({
        'next_round_error': blocked,
        'next_round_retry_error': retry,
        'next_round_blocked': bool(blocked),
        'still_blocked_on_retry': bool(retry),
        'affects_whole_cohort': True,
        'recovery': 'rename one TeamProduct row directly in the database',
        'recovery_error': fixed_error,
        'resolves_after_recovery': nxt.status == 'processed',
    })
    return result
