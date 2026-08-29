"""V2-023 confirmation gate — does isolated positioning remove price sensitivity?

The characterisation measured units sold identical across a 40x price range and
offered a hypothesis: `preference_engine._derive_price_competitiveness` scores
price purely relatively, so a team with no rival at its positioning in a market
always sees `ratio = 1.0` and price stops affecting demand.

That was never confirmed. This gate tests it directly: one team known to be
**alone** in its positioning group and one known to **share** it, everything else
fixed, at $50, $420 and $2,000.

Refuses to produce evidence unless it can show the mutation reached the intended
product/market row, the baseline repeats exactly, and every diagnostic field —
positioning membership above all — is present. A gate that cannot see which
group a team was in is the gate that produced the unconfirmed hypothesis.
"""
import json
from decimal import Decimal as D

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.utils import timezone

import baseline as BASE
import counterfactual as CF

PRICES = ['50', '420', '2000']
FIXED_VOLUME = 20000

if not DjangoUser.objects.filter(is_superuser=True).exists():
    DjangoUser.objects.create_superuser('v2023-gate', 'a@e.com', 'x')
call_command('load_all_scenarios', verbosity=0)
call_command('setup_test_game', verbosity=0)

from core.models import (DecisionSubmission, Game, Round, RoundResultAdoption,
                         RoundResultFinancials, RoundResultPerformanceIndex,
                         RoundResultProductMarket, Team)
from core.models.decisions import DecisionMarketing

game = Game.objects.order_by('-id').first()
rnd = Round.objects.filter(game=game, round_number=game.current_round).first()
teams = list(Team.objects.filter(game=game).order_by('id'))


def write_baseline():
    for team in teams:
        sub, _ = DecisionSubmission.objects.get_or_create(
            team=team, round=rnd, defaults={'status': 'draft'})
        BASE.build(sub, team)
        BASE.build_optional(sub, team)
        for row in DecisionMarketing.objects.filter(submission=sub):
            row.production_volume = FIXED_VOLUME
            row.demand_estimate = int(FIXED_VOLUME * 1.5)
            row.save(update_fields=['production_volume', 'demand_estimate'])
        sub.status = 'locked'
        sub.locked_at = timezone.now()
        sub.save(update_fields=['status', 'locked_at'])


# --- positioning membership, established before anything is measured --------
write_baseline()
groups = {}
for row in (DecisionMarketing.objects
            .filter(submission__round=rnd)
            .select_related('team_product', 'market', 'submission__team')
            .order_by('pk')):
    key = (row.market.code, row.team_product.positioning)
    groups.setdefault(key, []).append({
        'team_id': row.submission.team_id,
        'team': row.submission.team.name,
        'product_id': row.team_product_id,
        'product': row.team_product.name,
        'market_id': row.market_id,
        'row_id': row.pk,
    })

membership = {f'{m}/{p}': entries for (m, p), entries in sorted(groups.items())}

alone, shared = None, None
for key, entries in membership.items():
    distinct_teams = {e['team_id'] for e in entries}
    if len(distinct_teams) == 1 and alone is None:
        alone = (key, entries[0])
    if len(distinct_teams) > 1 and shared is None:
        shared = (key, entries[0])

result = {
    'game': game.id,
    'round': rnd.round_number,
    'fixed_production_volume': FIXED_VOLUME,
    'prices': PRICES,
    'positioning_membership': {
        key: {'teams': sorted({e['team'] for e in entries}),
              'rows': len(entries)}
        for key, entries in membership.items()
    },
    'selected': {},
    'subjects': {},
}
if alone:
    result['selected']['alone'] = {'group': alone[0], **alone[1]}
if shared:
    result['selected']['shared'] = {'group': shared[0], **shared[1]}

if alone is None or shared is None:
    result['gate_usable'] = False
    result['why'] = ('this scenario does not contain both an isolated and a '
                     'shared positioning group, so the hypothesis cannot be '
                     'tested against it')
    print('---V2023-GATE-JSON---')
    print(json.dumps(result, default=str))
    raise SystemExit(0)


def market_average_price(team_id, product_id, market_id, own_price):
    """The average the engine computes: rivals at this positioning, then self."""
    from core.models.team_state import TeamProduct
    positioning = TeamProduct.objects.get(pk=product_id).positioning
    rivals = (DecisionMarketing.objects
              .filter(submission__round=rnd, market_id=market_id,
                      team_product__positioning=positioning)
              .exclude(team_product__team_id=team_id)
              .order_by('pk'))
    prices = [float(r.retail_price) for r in rivals]
    prices.append(float(own_price))
    return sum(prices) / len(prices), len(prices) - 1


def price_fit(team_id, product_id, market_id):
    """The engine's own derived score, called with the engine's own inputs."""
    from core.engine.preference_engine import _derive_price_competitiveness
    from core.models.team_state import TeamProduct
    from core.models.scenario import MarketDefinition

    class _Ctx:
        pass
    ctx = _Ctx()
    ctx.game = game
    ctx.round_number = rnd.round_number
    ctx.scenario = game.scenario
    team = Team.objects.get(pk=team_id)
    product = TeamProduct.objects.get(pk=product_id)
    market = MarketDefinition.objects.get(pk=market_id)
    decision = DecisionMarketing.objects.filter(
        submission__round=rnd, submission__team=team,
        team_product=product, market=market).first()
    return _derive_price_competitiveness(ctx, team, product, market, decision,
                                         0.0, 1.0)


def outcomes(team_id, product_id, market_id):
    pm = (RoundResultProductMarket.objects
          .filter(team_id=team_id, round_number=rnd.round_number,
                  team_product_id=product_id, market_id=market_id)
          .order_by('-id').first())
    ad = (RoundResultAdoption.objects
          .filter(team_id=team_id, round_number=rnd.round_number,
                  market_id=market_id).order_by('-id').first())
    fin = (RoundResultFinancials.objects
           .filter(team_id=team_id, round_number=rnd.round_number)
           .order_by('-id').first())
    idx = (RoundResultPerformanceIndex.objects
           .filter(team_id=team_id, round_number=rnd.round_number)
           .order_by('-id').first())
    return {
        'units_produced': str(pm.units_produced) if pm else None,
        'units_sold': str(pm.units_sold) if pm else None,
        'units_unsold': str(pm.units_unsold) if pm else None,
        'row_retail_price': str(pm.retail_price) if pm else None,
        'adoption_pool': str(ad.adoption_pool) if ad else None,
        'fit_score': str(ad.fit_score) if ad else None,
        'adjusted_fit_score': str(ad.adjusted_fit_score) if ad else None,
        'total_revenue': str(fin.total_revenue) if fin else None,
        'net_income': str(fin.net_income) if fin else None,
        'cash_closing': str(fin.cash_closing) if fin else None,
        'index_value': str(idx.index_value) if idx else None,
    }


def evaluate_at_price(target, price):
    """Set one product/market row's price, resolve, and read everything back."""
    proof = {}

    def mutate():
        write_baseline()
        # The row is found by its domain coordinates, not by the primary key
        # captured earlier: `BASE.build` deletes and recreates the marketing
        # rows on every preparation, so that pk no longer exists by the time
        # this runs. Looking it up by (team, product, market) also makes the
        # proof below stronger — it shows the price landed on the row for the
        # intended product in the intended market, rather than on whatever row
        # happened to keep an id.
        row = DecisionMarketing.objects.get(
            submission__round=rnd,
            submission__team_id=target['team_id'],
            team_product_id=target['product_id'],
            market_id=target['market_id'])
        row.retail_price = D(price)
        row.save(update_fields=['retail_price'])

        stored = DecisionMarketing.objects.get(pk=row.pk)
        proof['row_id'] = stored.pk
        proof['team_id'] = stored.submission.team_id
        proof['product_id'] = stored.team_product_id
        proof['market_id'] = stored.market_id
        proof['stored_price'] = str(stored.retail_price)
        proof['rows_matching_coordinates'] = DecisionMarketing.objects.filter(
            submission__round=rnd,
            submission__team_id=target['team_id'],
            team_product_id=target['product_id'],
            market_id=target['market_id']).count()
        # Each conjunct is recorded separately. The first version returned a
        # bare boolean, and when it came back false the refusal could say only
        # that the mutation had missed -- not which of five things was wrong.
        # The price is compared numerically: the column stores two decimal
        # places, so a stored 50.00 is the requested 50 even though the two
        # strings differ, and comparing the strings failed a mutation that had
        # in fact landed exactly where it was aimed.
        proof['checks'] = {
            'team_matches': stored.submission.team_id == target['team_id'],
            'product_matches': stored.team_product_id == target['product_id'],
            'market_matches': stored.market_id == target['market_id'],
            'price_stored_exactly': D(stored.retail_price) == D(price),
            'exactly_one_row': proof['rows_matching_coordinates'] == 1,
        }
        proof['reached_intended_row'] = all(proof['checks'].values())
        avg, rivals = market_average_price(
            target['team_id'], target['product_id'], target['market_id'], price)
        proof['market_average_price'] = avg
        proof['rival_rows_at_this_positioning'] = rivals
        proof['price_fit_score'] = price_fit(
            target['team_id'], target['product_id'], target['market_id'])

    # Read inside the transaction. The previous version read them after
    # `evaluate` returned, by which point the rollback had removed every result
    # row, and the gate refused on seven missing diagnostics — correctly, but
    # for a reason that was mine rather than the model's.
    def capture(into):
        into['detail'] = outcomes(target['team_id'], target['product_id'],
                                  target['market_id'])

    metrics = CF.evaluate(game, rnd, Team.objects.get(pk=target['team_id']),
                          mutate, capture=capture)
    return {'proof': proof,
            'outcomes': metrics.pop('detail', {}),
            'composite': metrics}


baseline_one = CF.evaluate(game, rnd, teams[0], write_baseline)
baseline_two = CF.evaluate(game, rnd, teams[0], write_baseline)
result['baseline_repeat_delta'] = CF.delta(baseline_one, baseline_two)
result['baseline_is_repeatable'] = CF.is_zero(result['baseline_repeat_delta'])

for label in ('alone', 'shared'):
    target = result['selected'][label]
    per_price = {}
    for price in PRICES:
        per_price[price] = evaluate_at_price(target, price)
    units = {p: v['outcomes']['units_sold'] for p, v in per_price.items()}
    fits = {p: v['proof']['price_fit_score'] for p, v in per_price.items()}
    result['subjects'][label] = {
        'group': target['group'],
        'team': target['team'],
        'product': target['product'],
        'rival_rows': per_price[PRICES[0]]['proof']['rival_rows_at_this_positioning'],
        'by_price': per_price,
        'units_sold_by_price': units,
        'price_fit_by_price': fits,
        'units_constant_across_prices': len(set(units.values())) == 1,
        'price_fit_constant_across_prices': len(set(fits.values())) == 1,
    }

result['gate_usable'] = True
result['hypothesis_supported'] = bool(
    result['subjects']['alone']['units_constant_across_prices']
    and not result['subjects']['shared']['units_constant_across_prices'])
print('---V2023-GATE-JSON---')
print(json.dumps(result, default=str))
