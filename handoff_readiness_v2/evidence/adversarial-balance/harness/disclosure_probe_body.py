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
COMPANION_PATH = 'trade_finance.lc_doc_prep_investment'
PROTECTED_KEY = 'buyer_payment_instrument'
# The value must be a real instrument id: the write serializer validates it
# against the scenario catalogue, so an invented sentinel is rejected before
# the disclosure question is ever reached. That has a consequence the probe
# has to respect -- the catalogue endpoint lists every instrument id by
# design, so finding the id there is not the team's decision leaking. Team
# surfaces are therefore searched for the id *inside a trade_finance decision
# row*, and the catalogue is reported as its own separate question.


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
    # The override table records who set it, and the column is not nullable:
    # an override is an instructor action and the model insists on saying so.
    instructor = DjangoUser.objects.filter(is_superuser=True).first()

    token = create_access_token(student)
    # SERVER_NAME matters: Django's test client sends Host: testserver, which
    # is not in ALLOWED_HOSTS, and every request comes back 400 before routing.
    # The first run of this probe reported "read gate holds" off six such 400s
    # -- six requests that never reached the application.
    client = Client(HTTP_AUTHORIZATION=f'Bearer {token}',
                    SERVER_NAME='localhost')

    started = time.time()
    report = {
        'field_path': FIELD_PATH,
        'protected_key': PROTECTED_KEY,
        'sentinel': None,
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

    # Positive control. If a surface the student is unambiguously entitled to
    # read does not answer 200, nothing else this probe reports means anything,
    # and it must refuse rather than describe failures as protection.
    control_url = (f'/api/games/{game.id}/teams/{team.id}/decisions/'
                   f'round/{game.current_round}/summary/')
    control = client.get(control_url)
    report['positive_control'] = {
        'url': control_url,
        'status': control.status_code,
        'reached_the_application': control.status_code == 200,
    }

    from core.models import TradeFinanceInstrument
    instrument = (TradeFinanceInstrument.objects
                  .filter(scenario=game.scenario).order_by('id').first())
    if instrument is None:
        report['refused'] = ('the scenario declares no trade finance '
                             'instruments, so the gated field has no legal '
                             'value and the probe cannot run')
        return report
    protected_value = instrument.instrument_id
    report['sentinel'] = protected_value

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
            'buyer_payment_instrument': protected_value,
            'lc_doc_prep_investment': 'standard'}]}),
        content_type='application/json')
    record('write_before_unlock_is_refused',
           status=locked_write.status_code,
           refused=locked_write.status_code >= 400)

    # --- 2. the reachable path that persists a locked value ---------------
    # An instructor lowers the unlock round for their class, the team writes
    # the field legally, and the instructor restores the schedule.
    # Both gated fields on this row have to be unlocked, or the write is
    # refused for the companion field and says nothing about this one.
    overrides = [
        ClassProgressiveDisclosureOverride.objects.create(
            game=game, field_path=path, override_unlock_round=1,
            created_by=instructor)
        for path in (FIELD_PATH, COMPANION_PATH)]
    allowed_write = client.post(
        tf_url,
        data=json.dumps({'trade_finance': [{
            'segment': segment.id, 'market': market.id,
            'buyer_payment_instrument': protected_value,
            'lc_doc_prep_investment': 'standard'}]}),
        content_type='application/json')
    record('write_while_overridden_is_accepted',
           status=allowed_write.status_code,
           accepted=allowed_write.status_code < 400)
    for entry in overrides:
        entry.delete()
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
    def decision_rows_expose(payload):
        """Does this payload carry the team's own locked decision value?"""
        found = []

        def walk(node):
            if isinstance(node, dict):
                if node.get(PROTECTED_KEY) == protected_value:
                    found.append(node)
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)
        walk(payload)
        return found

    exposures = {}
    for name, url in surfaces.items():
        response = client.get(url)
        text = response.content.decode('utf-8', 'replace')
        try:
            payload = json.loads(text)
        except ValueError:
            payload = None
        rows = decision_rows_expose(payload) if payload is not None else []
        exposures[name] = {
            'url': url,
            'status': response.status_code,
            'decision_row_exposes_value': bool(rows),
            'value_appears_anywhere': protected_value in text,
            'is_catalogue_surface': name == 'scenario_instrument_catalogue',
        }
        record(f'read_before_unlock:{name}',
               status=response.status_code,
               leaks_decision=bool(rows))
    report['read_surfaces_before_unlock'] = exposures
    report['leaking_surfaces'] = [
        name for name, e in exposures.items()
        if e['decision_row_exposes_value']]
    catalogue = exposures.get('scenario_instrument_catalogue', {})
    report['catalogue_lists_gated_mechanic_before_unlock'] = {
        'status': catalogue.get('status'),
        'lists_instruments': catalogue.get('value_appears_anywhere'),
        'note': ('the catalogue endpoint carries no permission class beyond '
                 'authentication and no round gate; it lists every instrument '
                 'id at round 1 for a mechanic authored to unlock at round 4. '
                 'Reported as its own question rather than as the team '
                 'decision leaking.'),
    }

    # --- 4. another class's disclosure state must not unlock this one -----
    foreign = None
    if other_game is not None:
        foreign = ClassProgressiveDisclosureOverride.objects.create(
            game=other_game, field_path=FIELD_PATH, override_unlock_round=1,
            created_by=instructor)
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
        override_unlock_round=game.current_round, created_by=instructor)
    after = client.get(tf_url)
    record('read_after_unlock', status=after.status_code)
    try:
        after_payload = json.loads(after.content.decode('utf-8', 'replace'))
    except ValueError:
        after_payload = None
    report['readable_after_unlock'] = bool(
        decision_rows_expose(after_payload) if after_payload else False)
    advanced.delete()

    report['probe_is_valid'] = bool(
        report['positive_control']['reached_the_application']
        and report['steps'][1]['accepted'])
    report['write_gate_holds'] = bool(
        report['steps'][0]['refused'] and report['steps'][1]['accepted'])
    report['read_gate_holds'] = not report['leaking_surfaces']
    report['class_isolation_holds'] = (
        report['unlock_with_foreign_override'] != 1)
    report['elapsed_seconds'] = round(time.time() - started, 1)
    return report
