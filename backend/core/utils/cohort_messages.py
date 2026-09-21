"""Shared, bilingual wording for cohort-cap refusals.

Stage 6 of GSP-CRV2-10 enforces the authored cohort caps (Ruling 4 of
2026-08-31, reaffirmed as R12 on 2026-09-11): a competitive field of 6-8 firms
per game, maximum 8, with teams of 3-5 members. The values were already
authored on `Section`; only enforcement was missing (finding V2-042).

A student or an instructor who hits one of these limits must learn what the
rule is and what to do next -- not a column name. The wording therefore lives
here rather than in the views, so that the roster surface, the team-assignment
surface and game creation cannot describe one rule three different ways.

Deliberately a separate module from `participant_messages`: these are cohort
administration messages rather than decision-validation messages, and keeping
them apart avoids two handoffs editing one catalogue at the same time.
"""
from core.utils.localization import get_user_language


MESSAGES = {
    'section_full': {
        'en': ('This section is full. It seats {capacity} students '
               '({max_teams} teams of up to {team_size_max}). Remove a student, '
               'or raise the section limits, before enrolling another.'),
        'zh-CN': ('本班级名额已满，可容纳 {capacity} 名学生（{max_teams} 个团队，'
                  '每队最多 {team_size_max} 人）。请先移除一名学生，或提高班级上限，'
                  '再添加新学生。'),
    },
    'team_full': {
        'en': ('{team} already has {current} members, the maximum this section '
               'allows. Choose another team, or raise the team size limit.'),
        'zh-CN': ('{team} 已有 {current} 名成员，已达本班级允许的上限。'
                  '请选择其他团队，或提高团队人数上限。'),
    },
    'team_under_minimum': {
        'en': ('{team} has {current} member(s); this section expects at least '
               '{minimum}. Add members before the game starts.'),
        'zh-CN': ('{team} 目前有 {current} 名成员；本班级要求至少 {minimum} 名。'
                  '请在比赛开始前补充成员。'),
    },
    # V2-104. The other ways one item of a team assignment can be refused. They
    # reach the instructor in the same list as `team_full`, so they are written
    # for the same reader: what happened, and what to do, with no column name.
    'assignment_student_not_enrolled': {
        'en': ('This student is no longer on an active roster, so they were '
               'not assigned. Reload the roster and check that they are still '
               'in the section.'),
        'zh-CN': ('该学生已不在有效名单中，因此未被分配。'
                  '请刷新名单，确认该学生仍在本班级。'),
    },
    'assignment_team_not_found': {
        'en': ('That team no longer exists, so the student was not assigned. '
               'Reload the roster and choose another team.'),
        'zh-CN': ('该团队已不存在，因此学生未被分配。请刷新名单并选择其他团队。'),
    },
    'assignment_student_missing': {
        'en': ('One assignment did not say which student it was for, so it '
               'was skipped. Reload the roster and try again.'),
        'zh-CN': ('有一项分配未指明学生，已被跳过。请刷新名单后重试。'),
    },
    'game_exceeds_section_cap': {
        'en': ('This section runs at most {maximum} teams, and {requested} were '
               'requested. Reduce the number of teams, or raise the section '
               'team limit.'),
        'zh-CN': ('本班级最多可运行 {maximum} 个团队，本次请求为 {requested} 个。'
                  '请减少团队数量，或提高班级的团队上限。'),
    },
    'game_below_minimum': {
        'en': ('A game needs at least {minimum} teams, and {requested} were '
               'requested. Increase the number of teams.'),
        'zh-CN': ('一场比赛至少需要 {minimum} 个团队，本次请求为 {requested} 个。'
                  '请增加团队数量。'),
    },
    'competition_course_unowned': {
        'en': ('{game} is a competition game with no instructor of record, so '
               'it cannot be opened or changed. Assign an instructor to its '
               'course, then try again.'),
        'zh-CN': ('{game} 是比赛场次，但尚未指定负责教师，因此无法开启或修改。'
                  '请先为其所属课程指定教师，然后重试。'),
    },
}


def language_for_request(request):
    """The supported language for a request, defaulting safely to English.

    Resolved through the same helper the rest of the platform uses so an
    instructor working in Chinese is refused in Chinese.
    """
    try:
        return 'zh-CN' if get_user_language(request) == 'zh-CN' else 'en'
    except Exception:
        return 'en'


def cohort_message(key, *, language='en', **values):
    """Render a reviewed cohort-cap message in the requested language."""
    try:
        template = MESSAGES[key][language]
    except KeyError:
        try:
            template = MESSAGES[key]['en']
        except KeyError as error:
            raise KeyError(f'Unknown cohort message {key!r}') from error
    return template.format(**values)
