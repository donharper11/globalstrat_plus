"""Which platform a product was based on, in a given round.

`TeamProduct.team_platform` is a single live pointer. Every consumer in the
engine reads it directly, so it answers "what is this product based on now" and
nothing else. That is adequate only while a product's platform never changes.

Stage 4 lets a team re-base a product onto another of its ready platforms, and
that turns the live pointer into a history-rewriting hazard. Replaying a round
resolved before the switch would read features from the platform the team moved
to afterwards, changing the competitive hash of a round already resolved and
published — the determinism boundary GSP-CRV2-01 certified.

BECSR hit the neighbouring version of this and recorded it as defect B: its
demand side resolved platforms as of the round while its supply side resolved
them as of now, so a re-based program's demand reconciled to nothing. No sale,
no lost sale, no inventory row, and **no error**, because the standing
`demand - sold - lost == 0` check summed only the rows that existed. It
measured zero units purely because no cohort had used the feature yet.

Two rules follow, and this module exists to make them cheap to obey:

* `platform_as_of_round` is the only way the engine resolves a product's
  platform, so demand and supply cannot drift apart;
* the reconciliation in `missing_platform_resolutions` fails on a **missing**
  row rather than summing what is present.
"""
from django.db import transaction

# The association is written lazily: a product created before re-basing existed
# has no history row, and its live pointer is the truth for every round up to
# the first switch. `platform_as_of_round` therefore falls back to the pointer
# rather than refusing, and the first switch seeds the prior association so
# earlier rounds keep resolving to the platform they were actually scored
# against.


def platform_as_of_round(product, round_number):
    """The platform this product was based on during `round_number`.

    Returns the most recent association effective at or before that round,
    falling back to the live pointer when the product has no history — which is
    every product until the first time its team re-bases it.
    """
    from core.models.team_state import TeamProductPlatformHistory

    if round_number is None:
        return product.team_platform
    row = (TeamProductPlatformHistory.objects
           .filter(team_product=product, effective_from_round__lte=round_number)
           .select_related('team_platform')
           .order_by('-effective_from_round', '-id')
           .first())
    return row.team_platform if row else product.team_platform


def platform_ids_as_of_round(products, round_number):
    """`{product_id: team_platform_id}` for a set of products, in one round.

    Batched, because the per-product form inside a scoring loop is how an
    as-of-round lookup becomes too slow to keep and gets quietly replaced by
    the live pointer again.
    """
    from core.models.team_state import TeamProductPlatformHistory

    product_ids = [p.id for p in products]
    resolved = {p.id: p.team_platform_id for p in products}
    if round_number is None or not product_ids:
        return resolved

    rows = (TeamProductPlatformHistory.objects
            .filter(team_product_id__in=product_ids,
                    effective_from_round__lte=round_number)
            .order_by('team_product_id', 'effective_from_round', 'id')
            .values_list('team_product_id', 'team_platform_id'))
    for product_id, platform_id in rows:
        resolved[product_id] = platform_id      # later rows win
    return resolved


def record_association(product, platform, round_number):
    """Write the round-versioned association, idempotently."""
    from core.models.team_state import TeamProductPlatformHistory

    row, _created = TeamProductPlatformHistory.objects.update_or_create(
        team_product=product, effective_from_round=round_number,
        defaults={'team_platform': platform})
    return row


def seed_prior_association(product, round_number):
    """Record the association that held *before* a switch, once.

    Without this the pre-switch rounds have no row, so `platform_as_of_round`
    falls back to the live pointer — which the switch is about to change — and
    every earlier round silently re-attributes to the platform the team moved
    to. BECSR shipped exactly that bug by reading a round id as a round number,
    and its guarantee that "past rounds stay frozen on the platform they were
    scored against" was false for every seeded portfolio.
    """
    from core.models.team_state import TeamProductPlatformHistory

    if TeamProductPlatformHistory.objects.filter(team_product=product).exists():
        return None
    first_round = product.created_round if product.created_round is not None else 0
    if first_round > round_number:
        # Created later than the switch round is corrupt ordering; anchor at
        # the switch round rather than writing history after it, where
        # `platform_as_of_round` could never see it.
        first_round = round_number
    return record_association(product, product.team_platform, first_round)


def missing_platform_resolutions(game, round_number):
    """Products whose platform cannot be resolved for this round.

    The check defect B needed and did not have. A reconciliation that sums the
    rows it finds cannot see a row that is absent: BECSR's
    `demand - sold - lost == 0` balanced perfectly while an entire product's
    demand went unreconciled, because the missing side contributed nothing to
    either total.

    So this asks the opposite question. Every active product in the game must
    resolve to exactly one platform for the round, that platform must belong to
    the same team, and it must exist. Anything else is named.
    """
    from core.models.team_state import TeamProduct

    products = list(TeamProduct.objects
                    .filter(team__game=game, status='active')
                    .select_related('team', 'team_platform'))
    resolved = platform_ids_as_of_round(products, round_number)

    from core.models.team_state import TeamPlatform
    platform_owner = dict(
        TeamPlatform.objects
        .filter(id__in=[pid for pid in resolved.values() if pid])
        .values_list('id', 'team_id'))

    problems = []
    for product in products:
        platform_id = resolved.get(product.id)
        if platform_id is None:
            problems.append({
                'product': product.id, 'name': product.name,
                'team': product.team.name, 'round': round_number,
                'detail': (f'{product.name} resolves to no platform in round '
                           f'{round_number}; its demand would reconcile to '
                           f'nothing')})
            continue
        owner = platform_owner.get(platform_id)
        if owner is None:
            problems.append({
                'product': product.id, 'name': product.name,
                'team': product.team.name, 'round': round_number,
                'detail': (f'{product.name} resolves to platform '
                           f'#{platform_id} in round {round_number}, which no '
                           f'longer exists')})
        elif owner != product.team_id:
            problems.append({
                'product': product.id, 'name': product.name,
                'team': product.team.name, 'round': round_number,
                'detail': (f'{product.name} resolves to platform '
                           f'#{platform_id} in round {round_number}, owned by '
                           f'another team')})
    return problems


def describe_missing_resolutions(problems, limit=5):
    lines = [item['detail'] for item in problems[:limit]]
    if len(problems) > limit:
        lines.append(f'... and {len(problems) - limit} more')
    return ' | '.join(lines)
