"""Enforcement of the authored cohort caps, and of competition-game ownership.

`Section.max_teams` (8), `Section.team_size_min` (3) and `Section.team_size_max`
(5) have been authored since the schema was written, and until now nothing read
them except a serializer field list. Finding V2-042 enrolled eight students and
put all of them on one team whose maximum is five, through the supported
surfaces, and neither refused. The values were right; only enforcement was
missing.

Two things this module exists to prevent:

**One rule, one place.** Game creation carried an unrelated `num_teams must be
between 2 and 16` that had nothing to do with the section's `max_teams`. Two
caps that disagree is one cap that does not exist, so the cap is computed here
and every surface asks this module rather than restating a number.

**One team, counted once.** Team membership has two live representations:
`Enrollment.team_id`, which the results API calls "the real source of truth",
and `User.team_id`, which `UserViewSet` writes independently and never syncs
back -- `manage.py link_users_to_game` exists because the two drift. A cap
enforced on one of them is not a cap, so occupancy is the union of both.

Competition games additionally require an owned course. `instructor_can_access_
game` treats a course with `instructor_id IS NULL` as a shared pilot cohort
readable by any instructor. That is the adopted rule for the pilot and is
preserved exactly; what is refused here is its *reach into a competition*,
where several institutions share one deployment and an unowned course would
grant every judge cross-cohort access (V2-033).
"""
import logging

logger = logging.getLogger(__name__)

# A game needs at least this many teams to be a competition at all. The upper
# bound is authored per section (`Section.max_teams`); this lower bound is not
# authored anywhere, and replaces the previous hardcoded lower half of
# "between 2 and 16".
MIN_TEAMS_PER_GAME = 2

# Used only when a game is created without a section, so no authored cap can be
# read. Matches the authored `Section.max_teams` default (Ruling 4: maximum 8).
DEFAULT_MAX_TEAMS = 8


# ---------------------------------------------------------------------------
# Resolving the cohort behind a thing
# ---------------------------------------------------------------------------

def section_for_id(section_id):
    from core.models.course import Section
    if section_id in (None, ''):
        return None
    try:
        return Section.objects.filter(section_id=section_id).first()
    except Exception:
        logger.exception('Could not resolve section %s', section_id)
        return None


def section_for_game(game):
    """The section behind a game, by either of the two links that exist.

    A section reaches its game two ways and neither is reliable alone: the
    pilot section sets both `Game.section_id` and `SimulationInstance.game_id`,
    while the demo section sets only the latter. `_game_ids_for_section` in
    views/course.py resolves it the same way.
    """
    from core.models.course import Section, SimulationInstance
    if game is None:
        return None
    try:
        section_id = getattr(game, 'section_id', None)
        if section_id:
            section = Section.objects.filter(section_id=section_id).first()
            if section is not None:
                return section
        instance = SimulationInstance.objects.filter(game_id=game.pk).first()
        if instance is not None:
            return Section.objects.filter(
                section_id=instance.section_id).first()
    except Exception:
        logger.exception('Could not resolve section for game %s',
                         getattr(game, 'pk', None))
    return None


def section_for_team(team_id):
    """The section behind a team, via its game."""
    from core.models.core import Team
    try:
        team = Team.objects.filter(id=team_id).select_related('game').first()
    except Exception:
        return None
    if team is None:
        return None
    return section_for_game(team.game)


def section_for_user(user_id):
    """The section a user is enrolled in, if exactly one is resolvable."""
    from core.models.course import Enrollment, Section
    try:
        enrollment = Enrollment.objects.filter(
            user_id=user_id, is_active=True).first()
    except Exception:
        return None
    if enrollment is None:
        return None
    return Section.objects.filter(section_id=enrollment.section_id).first()


def course_for_game(game):
    from core.models.course import Course
    section = section_for_game(game)
    if section is None:
        return None
    try:
        return Course.objects.filter(course_id=section.course_id).first()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------

def seat_capacity(section):
    """How many students a section can seat: teams x maximum team size."""
    if section is None:
        return None
    return int(section.max_teams) * int(section.team_size_max)


def active_enrolment_count(section):
    from core.models.course import Enrollment
    if section is None:
        return 0
    try:
        return Enrollment.objects.filter(
            section_id=section.section_id, is_active=True).count()
    except Exception:
        return 0


def team_member_ids(team_id):
    """Everyone on a team, counted once, across both representations.

    `Enrollment.team_id` is authoritative, but `User.team_id` is written
    independently by the user-management routes; a member recorded only there
    is still a member sitting in the room.
    """
    from core.models.course import Enrollment
    from core.models import User
    member_ids = set()
    if team_id in (None, ''):
        return member_ids
    try:
        member_ids.update(
            Enrollment.objects.filter(team_id=team_id, is_active=True)
            .values_list('user_id', flat=True))
    except Exception:
        logger.exception('Could not count enrolments for team %s', team_id)
    try:
        member_ids.update(
            User.objects.filter(team_id=team_id).values_list('user_id',
                                                             flat=True))
    except Exception:
        logger.exception('Could not count users for team %s', team_id)
    return member_ids


def team_member_count(team_id):
    return len(team_member_ids(team_id))


def active_team_count(game):
    """Teams occupying a slot in the competitive field.

    A withdrawn team is not in the field and does not consume a slot.
    """
    from core.models.core import Team
    if game is None:
        return 0
    try:
        return Team.objects.filter(
            game=game, participation_status='active').count()
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# The caps themselves. Each returns a rendered refusal, or None to allow.
# ---------------------------------------------------------------------------

def enrolment_capacity_error(section, *, adding=1, language='en'):
    """Refuse an enrolment that would exceed the section's seat capacity.

    The cap binds at enrolment as well as at team assignment: refusing here is
    recoverable, whereas discovering at assignment time that the cohort cannot
    be seated is not.
    """
    from core.utils.cohort_messages import cohort_message
    if section is None:
        return None
    capacity = seat_capacity(section)
    if capacity is None or capacity <= 0:
        return None
    if active_enrolment_count(section) + adding <= capacity:
        return None
    return cohort_message(
        'section_full', language=language, capacity=capacity,
        max_teams=section.max_teams, team_size_max=section.team_size_max)


def team_capacity_error(section, team_id, *, joining_user_id=None,
                        language='en', team_name=None):
    """Refuse a team assignment that would exceed `team_size_max`.

    A user already counted on the target team is not counted twice, so
    re-asserting an existing assignment is never refused.
    """
    from core.utils.cohort_messages import cohort_message
    if section is None or team_id in (None, ''):
        return None
    members = team_member_ids(team_id)
    if joining_user_id is not None and joining_user_id in members:
        return None
    if len(members) + 1 <= int(section.team_size_max):
        return None
    return cohort_message(
        'team_full', language=language,
        team=team_name or _team_label(team_id),
        current=len(members))


def under_minimum_teams(section, game=None, *, language='en'):
    """Teams below `team_size_min`, reported rather than refused.

    A team is legitimately below the minimum for the whole period it is being
    filled, so refusing an assignment for it would make ordinary roster
    building impossible. The caller surfaces this so the console can show it.
    """
    from core.models.core import Team
    from core.utils.cohort_messages import cohort_message
    if section is None:
        return []
    minimum = int(section.team_size_min)
    reports = []
    try:
        if game is not None:
            teams = Team.objects.filter(game=game,
                                        participation_status='active')
        else:
            from core.models.course import Enrollment
            team_ids = set(
                Enrollment.objects.filter(section_id=section.section_id,
                                          is_active=True)
                .exclude(team_id__isnull=True)
                .values_list('team_id', flat=True))
            teams = Team.objects.filter(id__in=team_ids)
        for team in teams:
            count = team_member_count(team.id)
            if count < minimum:
                reports.append({
                    'team_id': team.id,
                    'team_name': team.name,
                    'member_count': count,
                    'minimum': minimum,
                    'detail': cohort_message(
                        'team_under_minimum', language=language,
                        team=team.name, current=count, minimum=minimum),
                })
    except Exception:
        logger.exception('Could not evaluate minimum team size for section %s',
                         getattr(section, 'section_id', None))
    return reports


def game_team_count_error(section, requested, *, language='en'):
    """The single cap on how many teams a new game may have.

    Replaces the unrelated `num_teams must be between 2 and 16`. The upper
    bound is the section's authored `max_teams`; without a section there is no
    authored cap to read, so the authored default stands in.
    """
    from core.utils.cohort_messages import cohort_message
    maximum = int(section.max_teams) if section is not None else DEFAULT_MAX_TEAMS
    if requested < MIN_TEAMS_PER_GAME:
        return cohort_message('game_below_minimum', language=language,
                              minimum=MIN_TEAMS_PER_GAME, requested=requested)
    if requested > maximum:
        return cohort_message('game_exceeds_section_cap', language=language,
                              maximum=maximum, requested=requested)
    return None


def _team_label(team_id):
    from core.models.core import Team
    try:
        team = Team.objects.filter(id=team_id).first()
        if team is not None:
            return team.name
    except Exception:
        pass
    return f'Team {team_id}'


# ---------------------------------------------------------------------------
# Competition games (V2-033)
# ---------------------------------------------------------------------------

def is_competition_game(game):
    """Whether this game is a competition heat.

    Read from `SimulationInstance.settings['is_competition']`, which is an
    existing `jsonb` column on an existing table, so marking a heat needs no
    schema change and is reversible by deleting the key. Resolved through this
    one helper so that adopting a dedicated `Game.is_competition` field later
    is a change here and nowhere else -- two flags that disagree would be the
    same defect as two caps that disagree.
    """
    from core.models.course import SimulationInstance
    if game is None:
        return False
    try:
        instance = SimulationInstance.objects.filter(game_id=game.pk).first()
        if instance is None:
            section_id = getattr(game, 'section_id', None)
            if section_id:
                instance = SimulationInstance.objects.filter(
                    section_id=section_id).first()
        if instance is None:
            return False
        settings_blob = instance.settings or {}
        if not isinstance(settings_blob, dict):
            return False
        return bool(settings_blob.get('is_competition', False))
    except Exception:
        # A game whose cohort tables cannot be read is not treated as a
        # competition game: this must never turn a readable game into a 500.
        logger.exception('Could not resolve competition mode for game %s',
                         getattr(game, 'pk', None))
        return False


def competition_ownership_error(game, *, language='en'):
    """Refuse a competition game whose course has no instructor of record.

    `instructor_can_access_game` deliberately treats a course with no
    `instructor_id` as a shared pilot cohort visible to any instructor, and
    that behaviour is preserved untouched for non-competition games. In a
    competition it would mean several institutions on one deployment with any
    unowned course readable by every judge, so a competition game is refused
    before it can be opened or acted on -- a precondition on the game, not a
    runbook step someone has to remember.
    """
    from core.utils.cohort_messages import cohort_message
    if not is_competition_game(game):
        return None
    course = course_for_game(game)
    if course is not None and course.instructor_id is not None:
        return None
    return cohort_message('competition_course_unowned', language=language,
                          game=getattr(game, 'name', 'This game'))


def competition_section_ownership_error(section, *, language='en'):
    """`competition_ownership_error`, asked of a section rather than a game.

    The roster and team-assignment routes name a section, and a heat's section
    exists before its game does, so the flag is read from the section's own
    `SimulationInstance` -- the same column `is_competition_game` reads.
    """
    from core.models.core import Game
    from core.models.course import Course, SimulationInstance
    from core.utils.cohort_messages import cohort_message
    if section is None:
        return None
    try:
        instance = SimulationInstance.objects.filter(
            section_id=section.section_id).first()
        settings_blob = (instance.settings or {}) if instance else {}
        if not (isinstance(settings_blob, dict)
                and settings_blob.get('is_competition', False)):
            return None
        course = Course.objects.filter(course_id=section.course_id).first()
        if course is not None and course.instructor_id is not None:
            return None
        game = (Game.objects.filter(pk=instance.game_id).first()
                if instance.game_id else None)
        label = (getattr(game, 'name', None) or section.section_name
                 or section.section_code)
    except Exception:
        # As in `is_competition_game`: a cohort that cannot be read is not
        # turned into a 500 by the check that protects it.
        logger.exception('Could not resolve competition mode for section %s',
                         getattr(section, 'section_id', None))
        return None
    return cohort_message('competition_course_unowned', language=language,
                          game=label)
