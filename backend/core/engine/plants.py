"""One plant row per team, market and construction start (W-CE2-01).

`manifest_sections` declares `('team_id', 'market_id',
'construction_started_round')` the natural key of the hashed `team_plant`
section, so two rows sharing that triple make the round unsnapshotable and
post-round processing 500s with the round stuck at `closed / FAILED`. Two
engine steps create plants in the same round -- `strategy_effects._process_plants`
for a build the team decided, `acquisitions.process_acquisitions` for a plant
an acquired target brings -- and neither looked for the other's row.

Both go through `record_plant` now. A second plant started by one team, in one
market, in one round is not a second row: the capacities add, the earlier
completion wins, and a plant that is operational stays operational. That is
the reconciliation the read side already assumes -- `decisions.py` sums
`capacity_units` per market for the production-capacity warning, and
`costs.py` asks only whether *a* plant exists in the source market and reads
one row's learning curve -- and it is what lets a game that already carries
the collision be resolved at all, since no screen can withdraw either
decision after the fact.

The collision is refused at the decision boundary as well
(`serializers.decisions.validate_plant_decisions` and the lock validator), so
a new game cannot create one. This function exists for the game that already
has.
"""
from core.models.team_state import TeamPlant

OPERATIONAL = 'operational'


def record_plant(team, market, *, capacity_units, status,
                 construction_started_round, completion_round):
    """Create the team's plant in this market, or merge into the one there.

    Returns the row that now holds the capacity. Deterministic: the merge
    reads and writes one row chosen by the natural key itself, so it does not
    depend on the order the two engine steps ran in.
    """
    existing = TeamPlant.objects.filter(
        team=team, market=market,
        construction_started_round=construction_started_round,
    ).order_by('id').first()

    if existing is None:
        return TeamPlant.objects.create(
            team=team, market=market, status=status,
            capacity_units=capacity_units or 0,
            construction_started_round=construction_started_round,
            completion_round=completion_round,
        )

    existing.capacity_units = (existing.capacity_units or 0) + (capacity_units or 0)
    if OPERATIONAL in (existing.status, status):
        existing.status = OPERATIONAL
    existing.completion_round = min(existing.completion_round, completion_round)
    existing.save(update_fields=['capacity_units', 'status',
                                 'completion_round'])
    return existing


def plant_collisions(submission, language='en'):
    """Every reason this submission would start two plants in one market.

    Returned as finished sentences in the reader's language, each naming the
    market, because the same three surfaces have to say the same thing: the
    plant save, the acquisition save and the lock validator. Judged on the
    rows actually stored, so the two writes cannot be ordered to slip past it
    and a draft assembled before this rule existed is refused at the lock.

    Two collisions, both of which stop a round:

    * a **build** in a market where the team has also queued the acquisition
      of a target that brings a plant there -- two `team_plant` rows with one
      natural key, which is what W-CE2-01 recorded;
    * **two build rows** in one market -- two `decision_plant` rows with one
      natural key, which breaks the *input* snapshot before Phase 1 starts.
      The screen offered this: the Build Plant button stayed on the card
      after the first click because the card reads plants the team owns, not
      plants it has queued.
    """
    from core.models.team_state import TeamAcquisition
    from core.utils.localization import get_localized_field
    from core.utils.participant_messages import participant_message

    problems = []
    builds = [row for row in submission.plant_decisions
              .select_related('market').order_by('id')
              if row.action == 'build']
    if not builds:
        return problems

    seen = set()
    for row in builds:
        if row.market_id in seen:
            problems.append(participant_message(
                'plant_already_queued', language=language,
                market=get_localized_field(row.market, 'name', language)))
        seen.add(row.market_id)

    build_markets = {row.market_id: row.market for row in builds}
    for decision in (submission.acquisitions
                     .select_related('acquisition_target__market')
                     .order_by('acquisition_target__target_name')):
        target = decision.acquisition_target
        if not (target.includes_plant and target.plant_capacity > 0):
            continue
        if target.market_id not in build_markets:
            continue
        # A target another team already owns brings this team nothing, so it
        # cannot collide with anything: `process_acquisitions` skips it.
        if TeamAcquisition.objects.filter(acquisition_target=target).exists():
            continue
        problems.append(participant_message(
            'plant_and_acquired_plant', language=language,
            market=get_localized_field(
                build_markets[target.market_id], 'name', language),
            target=get_localized_field(target, 'target_name', language)))
    return problems
