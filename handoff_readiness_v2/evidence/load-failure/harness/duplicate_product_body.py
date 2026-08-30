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


def resolve_twice(game):
    """Resolve the round carrying the duplicate, then try the next one."""
    from core.engine.advance_round import advance_to_next_round
    from core.models import Round

    game.refresh_from_db()
    first = Round.objects.get(game=game, round_number=game.current_round)
    _lock_core_only(game, first)
    first_error = _attempt(game)
    first.refresh_from_db()
    duplicates = _duplicate_names(game)

    second_error = retry_error = None
    second_status = None
    if first.status == 'processed':
        advance_to_next_round(game.id)
        game.refresh_from_db()
        second = Round.objects.get(game=game, round_number=game.current_round)
        _lock_core_only(game, second)
        second_error = _attempt(game)
        # A blocked round that clears on a retry is a transient fault, not a
        # dead end. Ask twice before calling it permanent.
        retry_error = _attempt(game)
        second.refresh_from_db()
        second_status = second.status

    return {
        'first_round_error': first_error,
        'first_round_processed': first.status == 'processed',
        'duplicate_products_created': duplicates,
        'second_round_error': second_error,
        'second_round_retry_error': retry_error,
        'second_round_status': second_status,
        'second_round_blocked': bool(second_error) and second_status != 'processed',
        'retry_also_blocked': bool(retry_error) and second_status != 'processed',
    }
