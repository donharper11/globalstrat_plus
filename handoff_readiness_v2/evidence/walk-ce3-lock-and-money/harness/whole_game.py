"""A whole game, six rounds, with every lock pressed through the real route.

Why this exists: W-CE3-02 was missed by unit tests. The lock a team can never
reach only shows up across rounds, once a team's cash has gone negative and the
next round's Decision Summary is opened. So the proof is a game, not a case.

What it drives, all of it through the product's own HTTP routes with a signed-in
team member's bearer token (`/api/auth/login/`, `.../decisions/round/N/summary/`,
`.../financing/`, `.../lock/`):

* four teams play rounds 1..N with a differentiated, non-trivial decision set,
  seeded the way `handoff_readiness_v2/determinism_fixture.py` seeds one;
* one team (index 0, "the distressed team") is made to spend nearly all its
  cash on decisions the lock ACCEPTS, so the loss that follows comes from the
  round resolving -- COGS, admin overhead, interest, tax -- and not from a
  draft the lock refused. That is the route to negative cash that survives
  decision 14;
* from the round after its cash goes negative, the team is asked to lock three
  ways, in this order, and each answer is recorded:
    1. as it stands;
    2. stripped -- every declared budget, promotion budget and dividend set to
       zero through the real save routes;
    3. stripped, then financed -- new debt raised through the real financing
       route.
* a round is closed only after every team has locked itself. `close_round`
  reports how many submissions IT had to lock; anything but zero means a team
  was force-advanced, and the per-round line says so.

ISOLATED USE ONLY: reads ./dbenv, refuses the production database host.

    bash make_db.sh && python3 seed.py && python3 whole_game.py --label red
"""
import argparse
import io
import json
import os
import pathlib
import sys
from decimal import ROUND_DOWN, ROUND_UP, Decimal as D

SCRATCH = pathlib.Path(__file__).resolve().parent
WT = SCRATCH.parents[3]

for line in (SCRATCH / 'dbenv').read_text().splitlines():
    if line.startswith('export '):
        key, _, value = line[len('export '):].partition('=')
        os.environ[key] = value

sys.path.insert(0, str(WT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')

import django                                                      # noqa: E402
django.setup()

from django.core.management import call_command                    # noqa: E402
from django.test import Client                                     # noqa: E402
from django.utils import timezone                                  # noqa: E402

from core.models import (DecisionSubmission, Game, Round, Team,     # noqa: E402
                         TalentAllocation, User)
from core.models.course import Course, Enrollment, Section          # noqa: E402
from core.models.cc31_models import ComplianceInvestment            # noqa: E402
from core.models.decisions import (                                 # noqa: E402
    DecisionBudgetAllocation, DecisionESG, DecisionMarketEntry,
    DecisionMarketing, DecisionPlant, DecisionProductCreate,
    DecisionProductRetire)
from core.models.results_financials import RoundResultFinancials    # noqa: E402
from core.models.scenario import (                                  # noqa: E402
    EntryModeDefinition, FeatureDefinition, MarketDefinition, Scenario)
from core.models.team_state import (TeamMarketPresence, TeamPlatform,  # noqa: E402
                                    TeamProduct)
from core.utils.passwords import hash_password                      # noqa: E402

PRODUCTION_DB_HOST = '192.168.50.38'
PASSWORD = 'walk-pass-2026'

# (label, price factor, volume, rd share, promo share, entry markets)
PROFILES = [
    ('distressed',      D('0.80'), 2600, D('0.10'), D('0.55'), 2),
    ('marketing_heavy', D('0.95'), 1800, D('0.15'), D('0.65'), 2),
    ('balanced',        D('1.00'), 1200, D('0.35'), D('0.40'), 1),
    ('conservative',    D('1.12'),  800, D('0.20'), D('0.20'), 0),
]


class Api:
    """The product's HTTP surface, as a signed-in team member sees it."""

    def __init__(self, username, password):
        # `127.0.0.1` because the product's ALLOWED_HOSTS is the real one: the
        # harness must not relax a production setting to make itself work.
        self.client = Client(SERVER_NAME='127.0.0.1')
        response = self.client.post(
            '/api/auth/login/',
            data=json.dumps({'username': username, 'password': password}),
            content_type='application/json')
        if response.status_code != 200:
            raise SystemExit(f'login failed for {username}: '
                             f'{response.status_code} {response.content[:300]}')
        self.token = response.json().get('access_token') or response.json().get('access')
        if not self.token:
            raise SystemExit(f'no access token in login response: {response.json()}')

    def _call(self, method, path, body=None):
        kwargs = {'HTTP_AUTHORIZATION': f'Bearer {self.token}'}
        if body is not None:
            kwargs['data'] = json.dumps(body, default=str)
            kwargs['content_type'] = 'application/json'
        response = getattr(self.client, method)(path, **kwargs)
        try:
            payload = response.json()
        except Exception:
            payload = response.content[:400].decode('utf-8', 'replace')
        return response.status_code, payload

    def get(self, path):
        return self._call('get', path)

    def post(self, path, body=None):
        return self._call('post', path, body if body is not None else {})

    def patch(self, path, body):
        return self._call('patch', path, body)


def make_roster(game, label):
    """One student per team, enrolled through `Enrollment`, known password.

    Membership goes through `Enrollment`, not `TeamMember`: both are checked by
    user id, but `TeamMember.user` is a foreign key to Django's `auth_user` and
    these students are `core.User` rows. `Enrollment.user_id` is a plain
    integer, which is what `IsTeamMember` actually compares.
    """
    course = Course.objects.create(
        course_code=f'WCE3{label.upper()}{game.id}'[:20],
        course_name='WALK-CE3 lock and money', instructor_id=None,
        is_active=True)
    section = Section.objects.create(
        course_id=course.course_id, section_code='S1', section_name='S1',
        max_teams=8, team_size_min=1, team_size_max=4, is_active=True)
    accounts = {}
    hashed = hash_password(PASSWORD)
    for index, team in enumerate(Team.objects.filter(game=game).order_by('id')):
        username = f'walkce3_{label}_t{index + 1}'
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={'role': 'student', 'email': f'{username}@example.invalid',
                      'display_name': f'Team {index + 1} Student'})
        User.objects.filter(pk=user.pk).update(password_hash=hashed,
                                               role='student')
        user.refresh_from_db()
        Enrollment.objects.create(
            user_id=user.user_id, section_id=section.section_id,
            team_id=team.id, is_active=True, enrolled_at=timezone.now())
        accounts[team.id] = username
    return accounts


def seed_round(game, round_obj, scenario, distressed_team_id,
               distressed_share=None, distressed_volume=None):
    """A differentiated decision set per team, and an affordable big spend.

    Every rule the lock validator enforces is satisfied here deliberately --
    the entry investment reaches the entry mode's own capital requirement, the
    promotion budgets total the declared marketing budget, and each round
    carries a product decision -- so that a refusal in the record is the
    platform's, not the driver's.

    `distressed_volume` is how many units the distressed team builds per
    product-market in this round. It is the lever that takes a team into the
    red WITHOUT the lock having refused anything: cost of goods is charged at
    resolution and is deliberately outside `funding_need.decision_outlays`
    (a rule that runs before the first competitive write cannot know it), so
    a team that builds stock nobody buys passes every affordability check and
    still ends the round with less cash than it started. That is the route to
    negative cash that survives decision 14, and it is how a real team would
    get there.

    `distressed_share` is the fraction of the distressed team's CURRENT cash it
    declares this round. Kept strictly below 1 so the lock ACCEPTS the draft.
    """
    markets = list(MarketDefinition.objects.filter(scenario=scenario).order_by('code'))
    features = list(FeatureDefinition.objects.filter(scenario=scenario).order_by('code')[:4])
    # The cheapest legal way in. Ordering by code picked `acquisition`, whose
    # capital requirement is $20,000,000, and every entry was then refused.
    entry_mode = (EntryModeDefinition.objects.filter(scenario=scenario)
                  .order_by('capital_requirement', 'code').first())
    teams = list(Team.objects.filter(game=game).order_by('id'))

    for index, team in enumerate(teams):
        label, price_factor, volume, rd_share, promo_share, entries = \
            PROFILES[index % len(PROFILES)]
        submission, _ = DecisionSubmission.objects.update_or_create(
            team=team, round=round_obj, defaults={'status': 'draft'})

        budget = D('10000000')
        if team.id == distressed_team_id and distressed_share:
            cash = D(str(team.cash_on_hand))
            if cash > 0:
                budget = (cash * D(str(distressed_share))).quantize(D('1'))

        marketing_budget = budget * promo_share
        DecisionBudgetAllocation.objects.update_or_create(
            submission=submission, defaults=dict(
                rd_budget=budget * rd_share,
                marketing_budget=marketing_budget,
                strategy_budget=budget * D('0.15'),
                research_budget=budget * D('0.05')))

        home = team.home_market or markets[0]
        products = list(TeamProduct.objects.filter(
            team=team, status='active').order_by('id'))
        row_markets = [home] + [m for m in markets[:entries] if m != home]
        rows = max(len(products) * len(row_markets), 1)
        # Promotion plus distribution must stay inside the declared marketing
        # budget or the lock refuses -- `marketing_budget_exceeded`.
        row_volume = volume
        if team.id == distressed_team_id and distressed_volume:
            row_volume = distressed_volume
        distribution = D('50000')
        promotion = ((marketing_budget / D(rows)) - distribution).quantize(
            D('0.01'), rounding=ROUND_DOWN)
        if promotion < 0:
            promotion = D('0')
        for product in products:
            for offset, market in enumerate(row_markets):
                DecisionMarketing.objects.update_or_create(
                    submission=submission, team_product=product, market=market,
                    defaults=dict(
                        retail_price=(D('500') * price_factor).quantize(D('0.01')),
                        promotion_budget=promotion,
                        campaign_focus_feature_ids=[f.id for f in features[:2]],
                        channel_digital_pct=D('0.6'),
                        channel_traditional_pct=D('0.3'),
                        channel_trade_pct=D('0.1'),
                        distribution_strategy='hybrid',
                        distribution_investment=distribution,
                        sales_team_count=5 + index,
                        production_volume=row_volume + 50 * offset,
                        demand_estimate=row_volume + 50 * offset,
                        production_source_market=home))

        for market in markets[:entries]:
            if market == home:
                continue
            if TeamMarketPresence.objects.filter(
                    team=team, market=market).exclude(status='exited').exists():
                continue
            DecisionMarketEntry.objects.update_or_create(
                submission=submission, market=market, action='enter',
                defaults=dict(entry_mode=entry_mode,
                              initial_investment=D(str(
                                  entry_mode.capital_requirement))))
            DecisionPlant.objects.update_or_create(
                submission=submission, market=market, action='contract',
                defaults=dict(capacity_units=0, contract_mfg_volume=volume // 2))
            ComplianceInvestment.objects.update_or_create(
                submission=submission, market=market,
                defaults=dict(investment_amount=D('200000')))

        # `lock_blockers_for` asks for a product decision in EVERY round
        # ("Set the product portfolio before locking"), so the driver makes
        # one: a new product while the portfolio is under the scenario cap,
        # and a retirement once it is at the cap.
        platform = TeamPlatform.objects.filter(
            team=team, status='active').order_by('id').first()
        presence_ids = list(TeamMarketPresence.objects.filter(
            team=team, status='active').values_list('market_id', flat=True))
        submission.product_creates.all().delete()
        submission.product_retires.all().delete()
        if (platform is not None and presence_ids
                and len(products) < (scenario.max_products_total or 6)):
            DecisionProductCreate.objects.create(
                submission=submission, team_platform=platform,
                product_name=f'{team.name[:12]} R{round_obj.round_number}'[:100],
                positioning='mainstream',
                target_market_ids=presence_ids[:1])
        elif products:
            DecisionProductRetire.objects.create(
                submission=submission, team_product=products[-1],
                timing='end_of_round')

        # A strategy decision in every round: after round 1 the markets are
        # already entered, so without this the lock refuses with "Set at least
        # one strategy decision before locking" and no cash figure is ever
        # reached.
        DecisionESG.objects.update_or_create(
            submission=submission, defaults=dict(
                environmental_investment=D('100000'),
                social_investment=D('100000')))

        # The mandatory board memo, written. It is a piece of student prose,
        # not a decision this proof is about; the lock asks for it in the round
        # its assignment triggers, so the driver submits one.
        _submit_mandatory_communications(game, team, round_obj, scenario)

        for pool in ('rd', 'commercial', 'operations'):
            TalentAllocation.objects.update_or_create(
                submission=submission, talent_pool=pool,
                defaults=dict(hq_count=8 + index,
                              market_allocation={m.code: 3 + index
                                                 for m in markets[:3]}))


def _submit_mandatory_communications(game, team, round_obj, scenario):
    from core.models.cc32_models import (CommunicationAssignment,
                                         TeamCommunication)
    from core.models.results import EventInstance
    for ca in CommunicationAssignment.objects.filter(
            scenario=scenario, is_mandatory=True).order_by('id'):
        triggered = False
        if ca.trigger_type == 'ROUND_MILESTONE':
            triggered = ((ca.trigger_condition or {}).get('round')
                         == round_obj.round_number)
        elif ca.trigger_type == 'EVENT_BASED':
            categories = (ca.trigger_condition or {}).get('event_category', [])
            if isinstance(categories, str):
                categories = [categories]
            triggered = EventInstance.objects.filter(
                game=game, round_number=round_obj.round_number,
                event_template__category__in=categories).exists()
        if not triggered:
            continue
        text = ('Our expansion plan for this round balances growth against '
                'the cash the business can fund from operations and debt.') * 6
        TeamCommunication.objects.update_or_create(
            game=game, team=team, round=round_obj, assignment=ca,
            defaults=dict(content=text, word_count=len(text.split()),
                          submitted_at=timezone.now(), is_draft=False))


def strip_to_nothing(api, game_id, team_id, round_number, submission):
    """Everything a screen can reduce, set to zero through the real routes."""
    base = f'/api/games/{game_id}/teams/{team_id}/decisions/round/{round_number}/'
    steps = []
    steps.append(('budget', *api.patch(base + 'budget/', {
        'rd_budget': 0, 'marketing_budget': 0, 'strategy_budget': 0,
        'research_budget': 0})))
    rows = []
    for md in submission.marketing_decisions.select_related(
            'team_product', 'market').order_by('id'):
        rows.append({
            'team_product': md.team_product_id, 'market': md.market_id,
            'retail_price': str(md.retail_price), 'promotion_budget': 0,
            'campaign_focus_feature_ids': md.campaign_focus_feature_ids,
            'channel_digital_pct': str(md.channel_digital_pct),
            'channel_traditional_pct': str(md.channel_traditional_pct),
            'channel_trade_pct': str(md.channel_trade_pct),
            'distribution_strategy': md.distribution_strategy,
            'distribution_investment': 0,
            'sales_team_count': 0,
            'production_volume': md.production_volume,
            'demand_estimate': md.demand_estimate,
            'production_source_market': md.production_source_market_id,
        })
    if rows:
        steps.append(('marketing', *api.patch(base + 'marketing/', rows)))
    steps.append(('compliance', *api.patch(base + 'compliance-investments/', [])))
    steps.append(('financing_zero', *api.patch(base + 'financing/', {
        'new_debt': 0, 'new_equity': 0, 'debt_repayment': 0,
        'dividend_per_share': 0})))
    return [{'step': name, 'status': code,
             'body': body if code >= 400 else 'ok'} for name, code, body in steps]


def _says_raise_equity(blockers):
    """The refusal that tells a distressed team debt will not reach it."""
    return any('Raise equity instead' in str(b) for b in (blockers or []))


def _shortfall_from_summary(summary):
    """What the Decision Summary's own figures say is missing.

    Exactly the gap, not a round number above it: V2-024 caps an equity raise
    at the round's funding shortfall, so a raise rounded up is refused by a
    different rule and would not test this one.
    """
    if not isinstance(summary, dict):
        return D('0')
    bs = summary.get('budget_summary') or {}
    committed = D(str(bs.get('committed_total') or 0))
    available = D(str(bs.get('total_available') or 0))
    gap = committed - available
    return gap if gap > 0 else D('0')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True, help='red or green')
    parser.add_argument('--teams', type=int, default=4)
    parser.add_argument('--rounds', type=int, default=6)
    parser.add_argument('--name', default=None)
    args = parser.parse_args()

    # V2-128: never write a pre-resolution dump into the live backup root.
    sys.path.insert(0, str(WT / 'handoff_readiness_v2'))
    from harness_isolation import require_disposable_backup_dir
    require_disposable_backup_dir()

    from django.conf import settings
    host = settings.DATABASES['default'].get('HOST')
    if host == PRODUCTION_DB_HOST or getattr(settings, 'IS_PRODUCTION', False):
        raise SystemExit(f'Refusing to run: {host!r} is production.')

    name = args.name or f'WALK-CE3-LOCKMONEY-{args.label.upper()}'
    scenario = Scenario.objects.order_by('id').first()
    call_command('initialize_game', scenario=scenario.id, teams=args.teams,
                 name=name, stdout=io.StringIO())
    game = Game.objects.filter(name=name).order_by('-id').first()
    game.section_id = 90101
    game.save(update_fields=['section_id'])

    accounts = make_roster(game, args.label)
    teams = list(Team.objects.filter(game=game).order_by('id'))
    distressed = teams[0]
    apis = {t.id: Api(accounts[t.id], PASSWORD) for t in teams}

    record = {'label': args.label, 'game_id': game.id,
              'scenario': scenario.name, 'distressed_team': distressed.name,
              'rounds': []}

    from core.engine.advance_round import (advance_to_next_round, close_round,
                                           process_round)

    for _ in range(args.rounds):
        rn = game.current_round
        round_obj = Round.objects.get(game=game, round_number=rn)
        distressed.refresh_from_db()
        opening = {t.name: str(Team.objects.get(pk=t.id).cash_on_hand)
                   for t in teams}
        # Round 2 is where the distressed team commits nearly everything it
        # holds -- affordably. The loss that follows is the round resolving.
        # Round 2 is the round the distressed team builds far more stock than
        # its market will buy. Nothing the lock checks refuses it; the money
        # goes at resolution, and the team opens round 3 in the red.
        over = 90000 if rn == 2 else None
        seed_round(game, round_obj, scenario, distressed.id, None, over)

        round_record = {'round': rn, 'cash_opening': opening, 'teams': []}

        for team in teams:
            api = apis[team.id]
            base = (f'/api/games/{game.id}/teams/{team.id}'
                    f'/decisions/round/{rn}/')
            entry = {'team': team.name,
                     'cash_on_hand': str(Team.objects.get(pk=team.id).cash_on_hand)}
            _, summary = api.get(base + 'summary/')
            entry['can_lock'] = summary.get('can_lock') if isinstance(summary, dict) else None
            entry['lock_blockers'] = (summary.get('lock_blockers')
                                      if isinstance(summary, dict) else summary)
            code, body = api.post(base + 'lock/')
            entry['lock'] = {'status': code,
                             'errors': body.get('errors') if isinstance(body, dict) else body}
            entry['locked'] = code == 200

            if not entry['locked']:
                # What a player does next, through the real routes.
                submission = DecisionSubmission.objects.get(
                    team=team, round=round_obj)
                entry['strip'] = strip_to_nothing(api, game.id, team.id, rn,
                                                  submission)
                _, summary = api.get(base + 'summary/')
                entry['blockers_stripped'] = (summary.get('lock_blockers')
                                              if isinstance(summary, dict) else summary)
                code, body = api.post(base + 'lock/')
                entry['lock_stripped'] = {
                    'status': code,
                    'errors': body.get('errors') if isinstance(body, dict) else body}
                entry['locked'] = code == 200

                if not entry['locked']:
                    # Raise financing, as the blocker beside it says to, and
                    # raise the amount the page's own figures say is missing
                    # rather than an invented round number -- a raise larger
                    # than the ceiling is refused for a different reason and
                    # would not test this.
                    _, after = api.get(base + 'summary/')
                    shortfall = _shortfall_from_summary(after)
                    entry['financing_shortfall'] = str(shortfall)
                    fin_code, fin_body = api.patch(base + 'financing/', {
                        'new_debt': str(shortfall), 'new_equity': 0,
                        'debt_repayment': 0, 'dividend_per_share': 0})
                    entry['financing_save'] = {'status': fin_code,
                                               'body': fin_body if fin_code >= 400 else 'ok'}
                    _, summary = api.get(base + 'summary/')
                    entry['blockers_after_financing'] = (
                        summary.get('lock_blockers')
                        if isinstance(summary, dict) else summary)
                    code, body = api.post(base + 'lock/')
                    entry['lock_after_financing'] = {
                        'status': code,
                        'errors': body.get('errors') if isinstance(body, dict) else body}
                    entry['locked'] = code == 200

                if not entry['locked'] and _says_raise_equity(
                        entry.get('blockers_after_financing')):
                    # Doing what the page just said: lenders will not lend to
                    # a company in distress, so raise equity instead.
                    _, after = api.get(base + 'summary/')
                    shortfall = _shortfall_from_summary(after)
                    entry['equity_shortfall'] = str(shortfall)
                    fin_code, fin_body = api.patch(base + 'financing/', {
                        'new_debt': 0, 'new_equity': str(shortfall),
                        'debt_repayment': 0, 'dividend_per_share': 0})
                    entry['equity_save'] = {'status': fin_code,
                                            'body': fin_body if fin_code >= 400 else 'ok'}
                    _, summary = api.get(base + 'summary/')
                    entry['blockers_after_equity'] = (
                        summary.get('lock_blockers')
                        if isinstance(summary, dict) else summary)
                    code, body = api.post(base + 'lock/')
                    entry['lock_after_equity'] = {
                        'status': code,
                        'errors': body.get('errors') if isinstance(body, dict) else body}
                    entry['locked'] = code == 200

            round_record['teams'].append(entry)

        round_obj.deadline = timezone.now()
        round_obj.save(update_fields=['deadline'])
        closed = close_round(game.id, reason='walk-ce3-proof')
        round_record['forced_by_deadline'] = closed.get('submissions_locked', 0)
        process_round(game.id)

        round_record['cash_closing'] = {}
        round_record['statement'] = {}
        for team in teams:
            fin = RoundResultFinancials.objects.filter(
                game=game, team=team, round_number=rn).first()
            team.refresh_from_db()
            round_record['cash_closing'][team.name] = str(team.cash_on_hand)
            if fin:
                round_record['statement'][team.name] = {
                    'cash_opening': str(fin.cash_opening),
                    'cash_closing': str(fin.cash_closing),
                    'net_income': str(fin.net_income),
                    'operating_income': str(fin.operating_income),
                }
        record['rounds'].append(round_record)
        print(f'round={rn} forced_by_deadline={round_record["forced_by_deadline"]} '
              + ' '.join(f'{e["team"]}:{"LOCKED" if e["locked"] else "REFUSED"}'
                         for e in round_record['teams']))
        for team in teams:
            print(f'    {team.name}: cash '
                  f'{round_record["cash_opening"].get(team.name)} -> '
                  f'{round_record["cash_closing"].get(team.name)}')

        game.refresh_from_db()
        if game.current_round < (scenario.num_rounds or 1):
            advance_to_next_round(game.id)
            game.refresh_from_db()

    out = SCRATCH.parent / f'whole-game-{args.label}.json'
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    print(f'record={out}')

    forced = sum(r['forced_by_deadline'] for r in record['rounds'])
    never_locked = [(r['round'], e['team']) for r in record['rounds']
                    for e in r['teams'] if not e['locked']]
    print(f'total_forced_by_deadline={forced} never_locked={never_locked}')
    return 0 if (forced == 0 and not never_locked) else 1


if __name__ == '__main__':
    raise SystemExit(main())
