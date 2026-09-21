"""Ownership for the cohort routes that name no game.

`GameScopeGuardMiddleware` enforces "is this their game" for every route whose
pattern carries a `game_id`. The roster, team-assignment, course and section
routes carry a section, an enrolment, a team or a course instead, so that
boundary never saw them, and their views declared `IsInstructor` — which
answers "is this an instructor" and nothing else. Driven with two instructor
accounts, every one of them let the second instructor read and rewrite the
first one's cohort.

The rule is not restated here: `core.permissions.instructor_can_access_course`
is the single definition, and it is `instructor_can_access_game`'s rule asked
of a course. What this module adds is the refusal itself, so that the four
views cannot word, code or record it four different ways:

* 403, the status the game-scope boundary uses for the same refusal;
* a reviewed bilingual sentence, in the caller's language;
* the request id, identical in the response and in the record;
* an `AuthorizationRefusalEvent` for a refused *mutation*, written outside any
  request transaction. Refused reads are not recorded, for the reason the
  middleware gives: that table counts attempted tampering.
"""
import logging

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from core.utils.cohort_messages import cohort_message, language_for_request

logger = logging.getLogger(__name__)

REFUSAL_CODE = 'cohort_belongs_to_another_instructor'
_MUTATING = ('POST', 'PUT', 'PATCH', 'DELETE')


class CohortOwnershipRefused(APIException):
    """The same refusal, for a viewset that has to raise rather than return."""
    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, payload):
        super().__init__(detail=payload)


def _game_id_for(section):
    """The game behind a section, for the refusal record. Best effort."""
    if section is None:
        return None
    try:
        from core.models.core import Game
        from core.models.course import SimulationInstance
        game_id = (SimulationInstance.objects
                   .filter(section_id=section.section_id)
                   .exclude(game_id__isnull=True)
                   .values_list('game_id', flat=True).first())
        if game_id is None:
            game_id = (Game.objects.filter(section_id=section.section_id)
                       .values_list('id', flat=True).first())
        return game_id
    except Exception:
        logger.exception('Could not resolve a game for section %s',
                         getattr(section, 'section_id', None))
        return None


def ownership_refusal_payload(request, *, section=None, course=None):
    """None when the caller may act on this cohort; otherwise the 403 body.

    Pass the section when there is one and the course when there is not. A
    cohort that cannot be resolved at all (`section` and `course` both None) is
    not refused here: the view answers 404 for it, exactly as the game-scope
    boundary leaves a missing game to its view.
    """
    from core.permissions import (instructor_can_access_course,
                                  instructor_can_access_section)
    if section is not None:
        allowed = instructor_can_access_section(request, section)
    elif course is not None:
        allowed = instructor_can_access_course(request, course)
    else:
        return None
    if allowed:
        return None

    from core.services.lifecycle import request_id_for
    request_id = request_id_for(request)
    method = (request.method or '').upper()
    if method in _MUTATING:
        from core.middleware import GameScopeGuardMiddleware
        match = getattr(request, 'resolver_match', None)
        GameScopeGuardMiddleware._record_refusal(
            request, _game_id_for(section), method,
            getattr(match, 'route', '') or '', request_id,
            'Course or section belongs to another instructor')
    return {
        'error': cohort_message(REFUSAL_CODE,
                                language=language_for_request(request)),
        'code': REFUSAL_CODE,
        'request_id': request_id,
    }


def ownership_refusal(request, *, section=None, course=None):
    """The refusal as a response, or None when the caller may proceed."""
    payload = ownership_refusal_payload(request, section=section, course=course)
    if payload is None:
        return None
    return Response(payload, status=status.HTTP_403_FORBIDDEN)


def competition_roster_refusal(request, section):
    """V2-033, reaching the roster of a heat with no instructor of record.

    Every lifecycle action on such a game is already refused inside
    `operator_action`. Its roster and its team assignments are part of what the
    heat resolves from, and they were open to any instructor account, because
    an unowned course is otherwise the shared pilot cohort.
    """
    from core.services.cohort_caps import competition_section_ownership_error
    unowned = competition_section_ownership_error(
        section, language=language_for_request(request))
    if not unowned:
        return None
    from core.services.lifecycle import request_id_for
    return Response(
        {'error': unowned, 'code': 'competition_course_unowned',
         'request_id': request_id_for(request)},
        status=status.HTTP_400_BAD_REQUEST)


def write_refusal(request, section):
    """Both checks a cohort write needs, in the order that explains most."""
    return (ownership_refusal(request, section=section)
            or competition_roster_refusal(request, section))
