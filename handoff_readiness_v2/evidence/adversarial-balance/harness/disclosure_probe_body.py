"""Progressive disclosure: is a locked field's value reachable before unlock?

A real student walkthrough over the supported API, with a signed JWT minted the
way the login endpoint mints it -- not a serializer call, and not the UI.

The field is `trade_finance.buyer_payment_instrument`, authored to unlock at
round 4 in `core.utils.disclosure.DEFAULT_UNLOCK_ROUNDS`. Write serializers
consult that registry; the question here is whether the *read* surfaces do.

The value has to exist before it can leak, and it can: an instructor may lower
the unlock round for their class, the team writes the field legally, and the
instructor restores the schedule. The value then sits in a round the field is
locked for. That path is exercised exactly, rather than writing the row behind
the API's back, so a leak found here is one a class can actually produce.
"""
import json
import time

from django.contrib.auth.models import User as DjangoUser
from django.core.management import call_command
from django.test import Client

FIELD_PATH = 'trade_finance.buyer_payment_instrument'
PROTECTED_KEY = 'buyer_payment_instrument'
PROTECTED_VALUE = 'LOCKED-INSTRUMENT-SENTINEL'


def run():
    if not DjangoUser.objects.filter(is_superuser=True).exists():
        DjangoUser.objects.create_superuser('disclosure', 'a@e.com', 'x')
    call_command('load_all_scenarios', verbosity=0)
    call_command('setup_test_game', verbosity=0)

    from core.authentication import create_access_token
    from core.models import Enrollment, Game, Round, Team, User
    from core.models.overrides import ClassProgressiveDisclosureOverride
    from core.models.sc_decisions import TradeFinanceDecision
    from core.models.scenario import MarketDefinition, SegmentDefinition
    from core.utils.disclosure import get_effective_unlock_round

    game = Game.objects.order_by('-id').first()
    game.refresh_from_db()
    team = Team.objects.filter(game=game).order_by('id').first()
    other_game = Game.objects.exclude(pk=game.pk).order_by('-id').first()

    student = User.objects.filter(role='student').first()
    if student is None:
        student = User.objects.create(username='probe-student',
                                      role='student', email='s@e.com')
    Enrollment.objects.get_or_create(
        user_id=student.user_id, team_id=team.id,
        defaults={'is_active': True})
    Enrollment.objects.filter(user_id=student.user_id,
                              team_id=team.id).update(is_active=True)
    token = create_access_token(student)
    client = Client(HTTP_AUTHORIZATION=f'Bearer {token}')

    started = time.time()
    report = {
        'field_path': FIELD_PATH,
        'protected_key': PROTECTED_KEY,
        'sentinel': PROTECTED_VALUE,
        'game': game.id,
        'team': team.id,
        'student': student.user_id,
        'authored_unlock_round': get_effective_unlock_round(game, FIELD_PATH),
        'current_round': game.current_round,
        'steps': [],
    }

    def record(step, **kw):
        entry = {'step': step, **kw}
        report['steps'].append(entry)
        print(f"  {step}: "
              + ', '.join(f'{k}={v}' for k, v in kw.items() if k != 'body'),
              flush=True)
        return entry

    rnd = Round.objects.get(game=game, round_number=game.current_round)
    segment = SegmentDefinition.objects.filter(
        scenario=game.scenario, segment_type='customer').order_by('id').first()
    market = MarketDefinition.objects.filter(
        scenario=game.scenario).order_by('id').first()

    base = f'/api/games/{game.id}/teams/{team.id}'
    tf_url = f'{base}/sc/round/{rnd.round_number}/trade-finance/'

    # --- 1. the write gate, confirmed rather than assumed -----------------
    locked_write = client.post(
        tf_url,
        data=json.dumps({'trade_finance': [{
            'segment': segment.id, 'market': market.id,
            'buyer_payment_instrument': PROTECTED_VALUE,
            'lc_doc_prep_investment': 'standard'}]}),
        content_type='application/json')
    record('write_before_unlock_is_refused',
           status=locked_write.status_code,
           refused=locked_write.status_code >= 400)

    # --- 2. the reachable path that persists a locked value ---------------
    # An instructor lowers the unlock round for their class, the team writes
    # the field legally, and the instructor restores the schedule.
    override = ClassProgressiveDisclosureOverride.objects.create(
        game=game, field_path=FIELD_PATH, override_unlock_round=1,
        created_by=None)
    allowed_write = client.post(
        tf_url,
        data=json.dumps({'trade_finance': [{
            'segment': segment.id, 'market': market.id,
            'buyer_payment_instrument': PROTECTED_VALUE,
            'lc_doc_prep_investment': 'standard'}]}),
        content_type='application/json')
    record('write_while_overridden_is_accepted',
           status=allowed_write.status_code,
           accepted=allowed_write.status_code < 400)
    override.delete()
    record('override_removed_field_is_locked_again',
           effective_unlock=get_effective_unlock_round(game, FIELD_PATH),
           current_round=game.current_round)

    persisted = TradeFinanceDecision.objects.filter(
        team=team, round=rnd).first()
    record('value_is_persisted_in_a_locked_round',
           present=persisted is not None,
           value=getattr(persisted, PROTECTED_KEY, None))

    # --- 3. every student read surface that could expose it ---------------
    surfaces = {
        'team_trade_finance_list': tf_url,
        'team_trade_finance_direct_round_object':
            f'{base}/sc/round/{rnd.round_number}/trade-finance/',
        'hedge_positions': f'{base}/sc/hedge-positions/',
        'scenario_instrument_catalogue':
            f'/api/scenarios/{game.scenario_id}/trade-finance-instruments/',
        'decision_summary': f'{base}/decisions/round/{rnd.round_number}/summary/',
        'decision_submission': f'{base}/decisions/round/{rnd.round_number}/',
    }
    exposures = {}
    for name, url in surfaces.items():
        response = client.get(url)
        text = response.content.decode('utf-8', 'replace')
        exposures[name] = {
            'url': url,
            'status': response.status_code,
            'sentinel_in_body': PROTECTED_VALUE in text,
            'protected_key_in_body': PROTECTED_KEY in text,
        }
        record(f'read_before_unlock:{name}',
               status=response.status_code,
               leaks_value=PROTECTED_VALUE in text)
    report['read_surfaces_before_unlock'] = exposures
    report['leaking_surfaces'] = [
        name for name, e in exposures.items() if e['sentinel_in_body']]

    # --- 4. another class's disclosure state must not unlock this one -----
    foreign = None
    if other_game is not None:
        foreign = ClassProgressiveDisclosureOverride.objects.create(
            game=other_game, field_path=FIELD_PATH, override_unlock_round=1,
            created_by=None)
    report['unlock_with_foreign_override'] = get_effective_unlock_round(
        game, FIELD_PATH)
    record('foreign_override_does_not_unlock',
           other_game=getattr(other_game, 'id', None),
           effective_unlock=report['unlock_with_foreign_override'],
           isolated=report['unlock_with_foreign_override'] != 1)
    if foreign is not None:
        foreign.delete()

    # --- 5. after the authored unlock the same student may read and write -
    unlock_round = report['authored_unlock_round']
    advanced = ClassProgressiveDisclosureOverride.objects.create(
        game=game, field_path=FIELD_PATH,
        override_unlock_round=game.current_round, created_by=None)
    after = client.get(tf_url)
    record('read_after_unlock',
           status=after.status_code,
           value_present=PROTECTED_VALUE in after.content.decode(
               'utf-8', 'replace'))
    report['readable_after_unlock'] = PROTECTED_VALUE in after.content.decode(
        'utf-8', 'replace')
    advanced.delete()

    report['write_gate_holds'] = bool(
        report['steps'][0]['refused'] and report['steps'][1]['accepted'])
    report['read_gate_holds'] = not report['leaking_surfaces']
    report['class_isolation_holds'] = (
        report['unlock_with_foreign_override'] != 1)
    report['elapsed_seconds'] = round(time.time() - started, 1)
    return report
