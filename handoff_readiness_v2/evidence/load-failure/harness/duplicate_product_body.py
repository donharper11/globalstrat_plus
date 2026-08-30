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


def decision_names(game, team_id):
    """The product-create names actually persisted for the open round."""
    from core.models.decisions import DecisionProductCreate
    rnd = _round(game)
    return sorted(DecisionProductCreate.objects.filter(
        submission__team_id=team_id, submission__round=rnd)
        .values_list('product_name', flat=True))


def product_names(game, team_id):
    from core.models.team_state import TeamProduct
    return sorted(TeamProduct.objects.filter(team_id=team_id)
                  .values_list('name', flat=True))


def lock_and_resolve(game, team_id):
    """Resolve the open round, then open the next one."""
    from core.engine.advance_round import advance_to_next_round

    rnd = _round(game)
    _lock_core_only(game, rnd)
    error = _attempt(game)
    rnd.refresh_from_db()
    resolved = rnd.status == 'processed'
    if resolved:
        advance_to_next_round(game.id)
        game.refresh_from_db()
    return {
        'error': error,
        'resolved': resolved,
        'products_owned': product_names(game, team_id),
        'next_round_number': game.current_round if resolved else None,
    }
