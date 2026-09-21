"""One boundary every operator action passes through.

The defect this exists to close (V2-004) was not a missing lock; it was that
each lifecycle endpoint decided for itself what to lock and when to check. Two
operators could both read `status='closed'`, both decide they were allowed to
proceed, and only discover the conflict deep inside the engine — where it
surfaced as a 500, or worse, as a second resolution.

Using it looks like this::

    with operator_action(request, game_id, 'process_round') as action:
        if action.round.status == 'processed':
            raise LifecycleConflict(
                'Round 3 has already been processed.',
                guidance='Refresh the console; another operator processed it.')
        ...
        action.commit(before, after)

Inside the block, the game row, the round row and the advisory lock are all
held, so `action.round` is state no other operator or student write can be
changing. Everything checked before entering the block is a guess.
"""
import contextlib
import logging
import uuid

from django.db import OperationalError, transaction
from rest_framework import status
from rest_framework.response import Response

from core.models.core import Game, Round
from core.services.competition_locks import lock_game_for_lifecycle
from core.utils.operator_messages import (
    language_for_request, lifecycle_refusal, operator_message, round_status)

logger = logging.getLogger('core.lifecycle')


class LifecycleError(Exception):
    """Base for a refusal that is expected, explained and not a server fault."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail, guidance='', code='', localise=None):
        super().__init__(detail)
        # `detail` and `guidance` are English, always: they are what the
        # operator audit row and the server log record. `localise(language)`
        # returns the same two sentences for the operator reading the response
        # (see `core.utils.operator_messages.lifecycle_refusal`).
        self.detail = detail
        self.guidance = guidance
        self.code = code
        self.localise = localise

    def as_payload(self, request_id='', language='en'):
        detail, guidance = self.detail, self.guidance
        if self.localise is not None and language != 'en':
            detail, guidance = self.localise(language)
        payload = {'error': detail, 'code': self.code or type(self).__name__}
        if guidance:
            payload['guidance'] = guidance
        if request_id:
            payload['request_id'] = request_id
        return payload


class LifecycleConflict(LifecycleError):
    """This action is already done, superseded, or impossible from here. 409.

    The split between the two is a promise to the operator about what to do
    next, and it is stable:

    * **409** — refresh and look again. Another operator or the deadline
      scheduler already achieved this intent ("already closed", "already
      processed"), or the state is terminal for this action ("a processed
      round cannot be reopened"). Nothing the operator types will change that.
    * **400** — do something else first, or fix the request. "Close the round
      first, or force", "that team is not locked", "a reason is required",
      "unparseable deadline".

    A caller that sends `expected_round_number` / `expected_status` also gets a
    409 whenever the state moved under it, which is what distinguishes losing a
    race from simply asking too early.
    """

    status_code = status.HTTP_409_CONFLICT


class LifecyclePrecondition(LifecycleError):
    """The request cannot run against this state until the operator changes
    something else first, or the request body is wrong. 400."""

    status_code = status.HTTP_400_BAD_REQUEST


class OperatorAction:
    """The state an operator action is allowed to reason about, plus its audit.

    A view sets `before` once it has read the state under the lock, then either
    calls `commit(after)` or raises a `LifecycleError`. Refusals are audited by
    `operator_action` itself, *after* the transaction ends: a refusal raised
    inside the atomic block rolls that block back, so an audit row written
    there would vanish along with the change it was recording.
    """

    def __init__(self, request, game, action, request_id):
        self.request = request
        self.game = game
        self.action = action
        self.request_id = request_id
        self.before = {}
        # Remembered so a refusal can name its round after the transaction —
        # and the row lock with it — has gone.
        self.round_pk = None

    @property
    def round(self):
        """The game's current round, read under the lock. Never cached."""
        round_obj = Round.objects.select_for_update().filter(
            game=self.game, round_number=self.game.current_round).first()
        if round_obj is not None:
            self.round_pk = round_obj.pk
        return round_obj

    def require_round(self):
        round_obj = self.round
        if round_obj is None:
            raise lifecycle_refusal(
                LifecyclePrecondition, 'round_missing',
                game=self.game.name, round=self.game.current_round)
        return round_obj

    def check_expected(self, round_obj):
        """Optimistic check against what the operator was looking at.

        A console renders a round, the operator clicks, and by the time the
        request arrives the round may have moved. Without this the loser of a
        race gets whatever message fits the *new* state — "close it first" —
        which reads as a mistake rather than as a race. With it, the refusal
        names what changed.
        """
        expected_number = self.request.data.get('expected_round_number')
        expected_status = self.request.data.get('expected_status')
        if expected_number not in (None, ''):
            try:
                expected_number = int(expected_number)
            except (TypeError, ValueError):
                raise lifecycle_refusal(
                    LifecyclePrecondition, 'expected_round_not_a_number')
            if expected_number != round_obj.round_number:
                raise lifecycle_refusal(
                    LifecycleConflict, 'state_moved_round',
                    guidance_key='state_moved_guidance',
                    current=round_obj.round_number, expected=expected_number)
        if expected_status not in (None, '') and expected_status != round_obj.status:
            raise lifecycle_refusal(
                LifecycleConflict, 'state_moved_status',
                guidance_key='state_moved_guidance',
                round=round_obj.round_number,
                status=round_status(round_obj.status),
                expected=round_status(str(expected_status)))
        return round_obj

    def require_reason(self, minimum=10):
        """A force flag is only a bypass if someone has to say why."""
        reason = str(self.request.data.get('reason', '')).strip()
        if len(reason) < minimum:
            raise lifecycle_refusal(
                LifecyclePrecondition, 'reason_required', minimum=minimum)
        return reason

    def commit(self, before, after, reason=''):
        from core.services.competition_audit import record_operator_event
        return record_operator_event(
            self.request, self.game, self.round, self.action, before, after,
            outcome='committed', request_id=self.request_id, reason=reason or None)

    def record_fault(self, detail, code='engine_failure'):
        """Audit a genuine failure without unwinding the transaction.

        Distinct from a refusal: the engine tried and broke. It must not raise
        out of the boundary, because the engine's own FAILED marker is written
        in this transaction and re-raising would roll it back with everything
        else. The row is written here so the attempt is still observable.
        """
        from core.services.competition_audit import record_operator_event
        return record_operator_event(
            self.request, self.game, self.round, self.action, self.before, {},
            outcome='rejected', request_id=self.request_id,
            conflict={'code': code, 'detail': detail, 'status': 500})

    def rejection_record(self, error):
        """Everything needed to audit this refusal once the rollback is done.

        Resolved eagerly, while the rows are still readable, because the caller
        writes it after the transaction that read them has gone.
        """
        return {
            'game_id': self.game.pk,
            'round_id': self.round_pk,
            'action': self.action,
            'before': self.before,
            'request_id': self.request_id,
            'conflict': {'code': error.code or type(error).__name__,
                         'detail': error.detail,
                         'status': error.status_code},
        }


_REQUEST_ID_ATTRIBUTE = '_gsp_request_id'


def request_id_for(request):
    """The caller's correlation id, or one minted for it — resolved once.

    The value is cached on the request. Without that, a server-minted id is a
    fresh UUID on every call, so the id an operator sees in a refusal response
    is not the id on the audit row for that refusal — the correlation the
    runbook tells them to use silently points at nothing. Any code that needs
    the id for this request, at any depth, gets the same one.
    """
    cached = getattr(request, _REQUEST_ID_ATTRIBUTE, None)
    if cached:
        return cached
    headers = getattr(request, 'headers', None) or {}
    try:
        supplied = (headers.get('X-Request-ID') or '').strip()
    except AttributeError:
        supplied = ''
    request_id = supplied[:128] if supplied else f'srv-{uuid.uuid4()}'
    try:
        setattr(request, _REQUEST_ID_ATTRIBUTE, request_id)
    except AttributeError:
        # A request object that refuses attributes (a bare mock in a test)
        # still gets a usable id; it just cannot be cached.
        pass
    # DRF wraps the Django request; cache on both so a handler that unwraps it
    # does not mint a second id.
    underlying = getattr(request, '_request', None)
    if underlying is not None and not getattr(underlying, _REQUEST_ID_ATTRIBUTE, None):
        try:
            setattr(underlying, _REQUEST_ID_ATTRIBUTE, request_id)
        except AttributeError:
            pass
    return request_id


@contextlib.contextmanager
def operator_action(request, game_id, action):
    """Hold the coordination boundary for the duration of one operator action.

    Acquires, in the documented order: the exclusive advisory lock for the
    game, then the game row. The round row is taken by `action.round`, which is
    deliberately a fresh read every time so a caller cannot accidentally
    validate against a stale copy.

    A `LifecycleError` raised inside the block rolls the block back — which is
    the point, since the action must leave nothing behind — and is then audited
    as a rejection in a fresh transaction, so the attempt stays observable.
    """
    request_id = request_id_for(request)
    holder = OperatorAction(request, None, action, request_id)
    try:
        with transaction.atomic():
            lock_game_for_lifecycle(game_id)
            game = Game.objects.select_for_update().filter(pk=game_id).first()
            if game is None:
                raise lifecycle_refusal(LifecyclePrecondition, 'game_not_found')
            holder.game = game
            # A competition heat whose course has no instructor of record is
            # refused before any lifecycle action runs. Every operator action
            # passes through here, so this is a precondition on the game rather
            # than a runbook step someone has to remember (V2-033).
            #
            # Non-competition games are untouched: `instructor_can_access_game`
            # still treats an unowned course as the shared pilot cohort, which
            # is the adopted rule and is what the live pilot relies on. What is
            # refused is that rule's reach into a competition, where several
            # institutions share one deployment.
            from core.services.cohort_caps import competition_ownership_error
            if competition_ownership_error(game):
                # English into the audit row, the operator's language into the
                # response -- the same split as every other refusal here.
                raise LifecyclePrecondition(
                    competition_ownership_error(game, language='en'),
                    guidance=operator_message(
                        'competition_course_unowned_guidance'),
                    code='competition_course_unowned',
                    localise=lambda language: (
                        competition_ownership_error(game, language=language),
                        operator_message('competition_course_unowned_guidance',
                                         language=language)))
            yield holder
    except LifecycleError as error:
        if holder.game is not None:
            _record_rejection(request, holder, error)
        raise


def _record_rejection(request, holder, error):
    """Write the refusal outside the transaction that was just rolled back."""
    from core.services.competition_audit import record_operator_event
    try:
        record = holder.rejection_record(error)
        with transaction.atomic():
            game = Game.objects.get(pk=record['game_id'])
            round_obj = (Round.objects.filter(pk=record['round_id']).first()
                         if record['round_id'] else None)
            record_operator_event(
                request, game, round_obj, record['action'], record['before'], {},
                outcome='rejected', request_id=record['request_id'],
                conflict=record['conflict'])
    except Exception:
        # An audit failure must not turn a clean refusal into a 500; it is
        # logged loudly instead, because a missing rejection row is a gap in
        # the evidence rather than a change to the competition.
        logger.exception('Could not record rejected operator action %s',
                         holder.action)


def lifecycle_view(function):
    """Turn a `LifecycleError` into its documented response instead of a 500."""
    import functools

    @functools.wraps(function)
    def wrapper(self, request, *args, **kwargs):
        try:
            return function(self, request, *args, **kwargs)
        except LifecycleError as error:
            logger.info('%s refused: %s', function.__qualname__, error.detail)
            return Response(
                error.as_payload(request_id_for(request),
                                 language=language_for_request(request)),
                status=error.status_code)

    return wrapper


def retry_on_serialization_failure(operation, attempts=3):
    """Bounded retry for an *idempotent* operation only.

    The lock order above is total, so PostgreSQL should never report a deadlock
    here; this exists for the serialization failures a busy server can still
    raise, and it is deliberately not applied to anything that mutates, because
    a retried non-idempotent action is a second action.
    """
    last = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except OperationalError as error:
            last = error
            logger.warning('Serialization failure on attempt %s/%s: %s',
                           attempt, attempts, error)
    raise last
