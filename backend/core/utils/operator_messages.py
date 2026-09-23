"""Bilingual wording for the refusals an instructor meets in the console.

D3 of 2026-09-21: nearly every operator route refused in English only, several
naming storage fields (`enrollment_id is required.`), so an instructor working
in Chinese read English reasons in the console's error toasts. The sentences
live here, in both shipped languages, and every one travels with a stable
machine `code` so the console can tell a sentence written for its reader from
one that is not (`frontend/.../pages/bilingualServerReason.js`).

Same pattern as `cohort_messages` (a literal `MESSAGES` dict, rendered through
`language_for_request`), and a separate module for the same reason that one is
separate from `participant_messages`: two handoffs should not have to edit one
catalogue at the same time. `check-participant-strings` reads this file as a
catalogue (A1 every language, A2 same placeholders, A3 no storage names).

Conventions
-----------
* A key ending `_guidance` is the "what to do next" line of the lifecycle
  refusal with the same stem. It is never a refusal on its own.
* The `code` of a refusal is its key, unless `CODES` says otherwise. `CODES`
  exists because several lifecycle refusals already shipped one code for
  several sentences (`round_already_processed`), and the codes are an API.
* The audit trail records the ENGLISH sentence whatever language the operator
  read, so an investigator reads one language. Only the response is localised.
"""
from core.utils.cohort_messages import language_for_request  # noqa: F401
from core.utils.participant_messages import ROUND_STATUS_LABELS

LANGUAGES = ('en', 'zh-CN')

PARTICIPATION_STATUS_LABELS = {
    'active': {'en': 'active', 'zh-CN': '处于参与状态'},
    'withdrawn': {'en': 'withdrawn', 'zh-CN': '已停用'},
}

GAME_STATUS_LABELS = {
    'setup': {'en': 'in setup', 'zh-CN': '设置中'},
    'active': {'en': 'active', 'zh-CN': '进行中'},
    'paused': {'en': 'paused', 'zh-CN': '已暂停'},
    'completed': {'en': 'completed', 'zh-CN': '已结束'},
    'archived': {'en': 'archived', 'zh-CN': '已归档'},
}

# How a team's round submission reached its state, as the drill-down shows it
# (W-CE-08, 2026-09-22). `classify_submission_origin` in views/results_api.py
# decides which applies; the sentence is chosen here so the console reads it
# in the instructor's language rather than the English the view used to hold.
SUBMISSION_ORIGIN_LABELS = {
    'no_submission': {'en': 'No submission', 'zh-CN': '未提交'},
    'draft': {'en': 'Draft (not locked)', 'zh-CN': '草稿（未锁定）'},
    'student_locked': {'en': 'Locked by team', 'zh-CN': '团队已锁定'},
    'deadline_locked': {'en': 'Auto-locked at deadline', 'zh-CN': '截止时自动锁定'},
    'defaulted_missing': {'en': 'Never submitted — defaulted at close',
                          'zh-CN': '从未提交——回合关闭时按默认处理'},
}

MESSAGES = {
    # -- the lifecycle boundary: every game-scoped operator write -----------
    'game_not_found': {
        'en': 'That game could not be found. Reload the console and choose the game again.',
        'zh-CN': '未找到该游戏。请刷新控制台后重新选择游戏。',
    },
    'round_missing': {
        'en': 'Game "{game}" has no round {round}.',
        'zh-CN': '游戏“{game}”没有第 {round} 回合。',
    },
    'round_missing_guidance': {
        'en': 'The game may not be initialised. Check the game setup.',
        'zh-CN': '该游戏可能尚未完成初始化。请检查游戏设置。',
    },
    'expected_round_not_a_number': {
        'en': 'The round number the console sent with this request was not a number. Reload the console and try again.',
        'zh-CN': '控制台随本次请求发送的回合编号不是数字。请刷新控制台后重试。',
    },
    'state_moved_round': {
        'en': 'The game has moved to round {current}; this request was for round {expected}.',
        'zh-CN': '游戏已进入第 {current} 回合；本次请求针对的是第 {expected} 回合。',
    },
    'state_moved_status': {
        'en': 'Round {round} is now {status}, not {expected} as the console showed.',
        'zh-CN': '第 {round} 回合当前{status}，而不是控制台显示的{expected}。',
    },
    'state_moved_guidance': {
        'en': 'Refresh the console and repeat the action if it is still what you want.',
        'zh-CN': '请刷新控制台；如仍需执行该操作，请再次操作。',
    },
    'reason_required': {
        'en': 'This action overrides an integrity check, so it requires a written reason of at least {minimum} characters.',
        'zh-CN': '此操作会绕过一项完整性检查，因此需要填写至少 {minimum} 个字符的书面理由。',
    },
    'reason_required_guidance': {
        'en': 'Repeat the action with a written reason explaining why this override is correct.',
        'zh-CN': '请填写书面理由，说明为何需要此次越权操作，然后重新执行。',
    },
    'competition_course_unowned_guidance': {
        'en': 'Assign an instructor to the course behind this game, then repeat the action.',
        'zh-CN': '请先为该游戏所属课程指定教师，然后重新执行该操作。',
    },

    # -- round control ------------------------------------------------------
    'game_belongs_to_another_instructor': {
        'en': 'This game belongs to another instructor.',
        'zh-CN': '该游戏属于另一位教师。',
    },
    'round_already_closed': {
        'en': 'Round {round} is already {status}.',
        'zh-CN': '第 {round} 回合{status}。',
    },
    'round_already_closed_guidance': {
        'en': 'Refresh the console — the deadline scheduler or another operator closed it first.',
        'zh-CN': '请刷新控制台——截止时间调度程序或另一位操作者已先行关闭该回合。',
    },
    'reopen_already_processed': {
        'en': 'Round {round} has already been processed and cannot be reopened.',
        'zh-CN': '第 {round} 回合已结算，无法重新开放。',
    },
    'reopen_already_processed_guidance': {
        'en': 'Results exist for this round. Recovery is the only route back; see the recovery runbook.',
        'zh-CN': '本回合的结果已经生成。只能通过恢复流程回退；请参阅恢复操作手册。',
    },
    'round_already_open': {
        'en': 'Round {round} is already open.',
        'zh-CN': '第 {round} 回合已处于开放状态。',
    },
    'round_already_open_guidance': {
        'en': 'Refresh the console — another operator reopened it.',
        'zh-CN': '请刷新控制台——另一位操作者已重新开放该回合。',
    },
    'deadline_unparseable': {
        'en': 'The deadline could not be read as a date and time. Pick the deadline again and resend.',
        'zh-CN': '无法将该截止时间识别为日期和时间。请重新选择截止时间后再提交。',
    },
    'deadline_in_past': {
        'en': 'The deadline has already passed.',
        'zh-CN': '截止时间已过。',
    },
    'deadline_in_past_guidance': {
        'en': 'Supply a new deadline when reopening, or the scheduler will close the round again within a minute.',
        'zh-CN': '重新开放时请设置新的截止时间，否则调度程序会在一分钟内再次关闭该回合。',
    },
    'process_already_processed': {
        'en': 'Round {round} has already been processed.',
        'zh-CN': '第 {round} 回合已结算。',
    },
    'process_already_processed_guidance': {
        'en': 'Refresh the console. If results look wrong, use recovery rather than processing again.',
        'zh-CN': '请刷新控制台。如结果有误，请使用恢复流程，而不要再次结算。',
    },
    'round_still_open': {
        'en': 'Round {round} is still open.',
        'zh-CN': '第 {round} 回合仍处于开放状态。',
    },
    'round_still_open_guidance': {
        'en': 'Close it first, or use the force option with a written reason to close and process in one step.',
        'zh-CN': '请先关闭该回合；或使用强制选项并填写书面理由，一步完成关闭和结算。',
    },
    'round_not_ready': {
        'en': '{detail}',
        'zh-CN': '本回合尚不具备结算条件。系统给出的原因（英文）：{detail}',
    },
    'round_not_ready_guidance': {
        'en': 'Re-lock the team, or close the round, then process again.',
        'zh-CN': '请重新锁定该团队的决策，或关闭该回合，然后再次结算。',
    },
    'processing_failed': {
        'en': 'Post-round processing failed: {detail}',
        'zh-CN': '回合结算失败。系统给出的原因（英文）：{detail}',
    },
    'round_not_processed': {
        'en': 'Round {round} is {status}, not processed.',
        'zh-CN': '第 {round} 回合{status}，尚未结算。',
    },
    'round_not_processed_guidance': {
        'en': 'Run post-round processing first, or use the force option with a written reason to advance without results.',
        'zh-CN': '请先执行回合结算；或使用强制选项并填写书面理由，在没有结果的情况下进入下一回合。',
    },
    'advance_refused': {
        'en': '{detail}',
        'zh-CN': '无法进入下一回合。系统给出的原因（英文）：{detail}',
    },
    'advance_refused_guidance': {
        'en': 'Refresh the console.',
        'zh-CN': '请刷新控制台。',
    },
    'advance_failed': {
        'en': 'Advance failed: {detail}',
        'zh-CN': '进入下一回合失败。系统给出的原因（英文）：{detail}',
    },
    'round_not_open': {
        'en': 'Round {round} is {status}; deadline changes are refused unless the round is open.',
        'zh-CN': '第 {round} 回合{status}；只有开放中的回合才能修改截止时间。',
    },
    'round_not_open_guidance': {
        'en': 'Reopen the round with a new deadline if students still need time.',
        'zh-CN': '如学生仍需时间，请重新开放该回合并设置新的截止时间。',
    },
    'minutes_not_a_number': {
        'en': 'The number of minutes must be a whole number.',
        'zh-CN': '分钟数必须为整数。',
    },
    'deadline_required': {
        'en': 'Provide a deadline, or a number of minutes from now.',
        'zh-CN': '请提供截止时间，或从现在起的分钟数。',
    },

    # -- the legacy one-step console routes ---------------------------------
    'legacy_advance_already_processed': {
        'en': 'Round {round} has already been processed.',
        'zh-CN': '第 {round} 回合已结算。',
    },
    'legacy_advance_already_processed_guidance': {
        'en': 'Refresh the console and advance instead.',
        'zh-CN': '请刷新控制台，然后改为进入下一回合。',
    },
    'team_not_locked': {
        'en': 'Team "{team}" has not locked decisions.',
        'zh-CN': '团队“{team}”尚未锁定决策。',
    },
    'team_not_locked_guidance': {
        'en': 'Lock or close the round first, or use the force option with a written reason.',
        'zh-CN': '请先锁定决策或关闭该回合；或使用强制选项并填写书面理由。',
    },
    'legacy_advance_failed': {
        'en': 'Round advance failed: {detail}',
        'zh-CN': '回合推进失败。系统给出的原因（英文）：{detail}',
    },
    'inject_already_processed': {
        'en': 'Round {round} has already been processed; an event injected now would not be part of it.',
        'zh-CN': '第 {round} 回合已结算；此时注入的事件不会计入该回合。',
    },
    'inject_already_processed_guidance': {
        'en': 'Advance to the next round and inject there.',
        'zh-CN': '请进入下一回合后再注入事件。',
    },
    'hours_not_a_number': {
        'en': 'The number of hours must be a whole number.',
        'zh-CN': '小时数必须为整数。',
    },
    'extend_already_processed': {
        'en': 'Round {round} has already been processed; its deadline cannot be extended.',
        'zh-CN': '第 {round} 回合已结算；无法延长其截止时间。',
    },
    'extend_already_processed_guidance': {
        'en': 'Advance to the next round and set its deadline there.',
        'zh-CN': '请进入下一回合，并在该回合设置截止时间。',
    },

    # -- game lifecycle: activate, pause, resume, archive --------------------
    'game_not_in_setup': {
        'en': 'This game is already {status}. Only a game in setup can be activated.',
        'zh-CN': '该游戏当前{status}。只有设置中的游戏才能激活。',
    },
    'game_not_in_setup_guidance': {
        'en': 'Refresh — another operator may have activated it.',
        'zh-CN': '请刷新——可能已有另一位操作者激活了该游戏。',
    },
    'round_one_missing': {
        'en': 'This game has no round 1, so it cannot be activated. Check the game setup.',
        'zh-CN': '该游戏没有第 1 回合，因此无法激活。请检查游戏设置。',
    },
    'game_not_active': {
        'en': 'This game is {status}, not active, so it cannot be paused.',
        'zh-CN': '该游戏当前{status}，并非进行中，因此无法暂停。',
    },
    'game_not_active_guidance': {
        'en': 'Refresh — another operator may have paused or completed it.',
        'zh-CN': '请刷新——可能已有另一位操作者暂停或结束了该游戏。',
    },
    'game_not_paused': {
        'en': 'This game is {status}, not paused, so it cannot be resumed.',
        'zh-CN': '该游戏当前{status}，并非已暂停，因此无法恢复。',
    },
    'game_not_paused_guidance': {
        'en': 'Refresh — another operator may have resumed it.',
        'zh-CN': '请刷新——可能已有另一位操作者恢复了该游戏。',
    },
    'game_already_archived': {
        'en': 'This game is already archived.',
        'zh-CN': '该游戏已归档。',
    },
    'game_already_archived_guidance': {
        'en': 'Refresh — another operator archived it.',
        'zh-CN': '请刷新——另一位操作者已将其归档。',
    },
    # Reset to Setup once a round has been processed (W-CE-26): the route
    # returns open rounds to pending and the game to round 0, and nothing
    # more, so a processed round would stay processed under a game that
    # believes it has not started.
    'reset_round_processed': {
        'en': 'Round {round} of "{game}" has already been processed, so the game cannot be reset to setup. The results and the record of that round are permanent.',
        'zh-CN': '游戏“{game}”的第 {round} 回合已结算，因此无法重置为初始设置。该回合的结果和记录为永久保存。',
    },
    'reset_round_processed_guidance': {
        'en': 'Archive the game instead, then create a new game for this section.',
        'zh-CN': '请改为归档该游戏，然后为该班级创建新的游戏。',
    },

    # -- game creation and the read-only console panels -----------------------
    'scenario_required': {
        'en': 'Choose a scenario before creating the game.',
        'zh-CN': '创建游戏前，请先选择情景。',
    },
    'scenario_not_found': {
        'en': 'That scenario could not be found. Reload the console and choose the scenario again.',
        'zh-CN': '未找到该情景。请刷新控制台后重新选择情景。',
    },
    'team_count_required': {
        'en': 'Enter the number of teams before creating the game.',
        'zh-CN': '创建游戏前，请先输入团队数量。',
    },
    'team_count_not_a_number': {
        'en': 'The number of teams must be a whole number.',
        'zh-CN': '团队数量必须为整数。',
    },
    'game_creator_missing': {
        'en': 'The game could not be recorded against an account, so it was not created. Contact support.',
        'zh-CN': '无法将该游戏记录到任何账户名下，因此未创建。请联系技术支持。',
    },
    'round_not_found': {
        'en': 'That round could not be found. Reload the console.',
        'zh-CN': '未找到该回合。请刷新控制台。',
    },

    # -- team participation ----------------------------------------------------
    'participation_action_invalid': {
        'en': 'Choose whether to deactivate or reactivate the team.',
        'zh-CN': '请选择停用或重新启用该团队。',
    },
    'confirmation_required': {
        'en': 'To confirm, type exactly: {expected}',
        'zh-CN': '如需确认，请准确输入：{expected}',
    },
    'participation_unchanged': {
        'en': 'This team is already {status}.',
        'zh-CN': '该团队当前{status}。',
    },
    'participation_unchanged_guidance': {
        'en': 'Refresh — another operator may have changed it.',
        'zh-CN': '请刷新——可能已有另一位操作者更改了该团队的状态。',
    },

    # -- student accounts ------------------------------------------------------
    'account_not_visible': {
        'en': 'That student could not be found, or is not in one of your courses.',
        'zh-CN': '未找到该学生，或该学生不在您的任何课程中。',
    },
    'account_instructor_reset_refused': {
        'en': 'Only an administrator can reset an instructor password.',
        'zh-CN': '只有管理员可以重置教师密码。',
    },
    'account_no_default_password': {
        'en': 'This account has neither a student number nor a username to derive a default password from. Set a password explicitly.',
        'zh-CN': '该账户既没有学号也没有用户名，无法生成默认密码。请直接设置一个密码。',
    },
    'account_bulk_selection_required': {
        'en': 'Choose the students to reset, or choose to reset only those with no password.',
        'zh-CN': '请选择要重置的学生，或选择仅重置尚未设置密码的学生。',
    },

    # -- team configuration --------------------------------------------------
    'round_1_started': {
        'en': 'Home markets cannot be changed after round 1 decisions have been submitted.',
        'zh-CN': '第 1 回合的决策提交后，不能再更改总部市场。',
    },
    'round_1_started_guidance': {
        'en': 'Team configuration is fixed once play starts.',
        'zh-CN': '游戏开始后，团队配置即固定。',
    },
    'team_config_no_teams': {
        'en': 'No teams were included in this request, so nothing was saved. Reload the console and try again.',
        'zh-CN': '本次请求未包含任何团队，因此未保存任何内容。请刷新控制台后重试。',
    },
    'team_config_team_not_in_game': {
        'en': 'One of the teams in this request is not part of this game, so nothing was saved. Reload the console and try again.',
        'zh-CN': '本次请求中有团队不属于该游戏，因此未保存任何内容。请刷新控制台后重试。',
    },
    'team_config_invalid_market': {
        'en': '"{market}" is not a market in this scenario. Available markets: {valid}.',
        'zh-CN': '“{market}”不是本情景中的市场。可选市场：{valid}。',
    },
    'scenario_has_no_markets': {
        'en': 'This scenario defines no markets, so home markets cannot be assigned.',
        'zh-CN': '本情景未定义任何市场，因此无法分配总部市场。',
    },

    # -- roster --------------------------------------------------------------
    'section_required': {
        'en': 'Choose a section first. The request did not say which section it was for.',
        'zh-CN': '请先选择班级。本次请求未指明班级。',
    },
    'section_not_found': {
        'en': 'That section could not be found. Reload the console and choose the section again.',
        'zh-CN': '未找到该班级。请刷新控制台后重新选择班级。',
    },
    'roster_unknown_action': {
        'en': 'The console asked the roster for something it cannot do. Reload the console and try again.',
        'zh-CN': '控制台向名单发出了无法执行的请求。请刷新控制台后重试。',
    },
    'roster_student_required': {
        'en': 'The request did not say which student it was for. Reload the roster and try again.',
        'zh-CN': '本次请求未指明学生。请刷新名单后重试。',
    },
    'roster_student_not_found': {
        'en': 'That student is no longer on the roster. Reload the roster.',
        'zh-CN': '该学生已不在名单中。请刷新名单。',
    },
    'roster_account_not_found': {
        'en': 'The account behind this roster entry could not be found, so nothing was changed. Reload the roster.',
        'zh-CN': '未找到该名单条目对应的账户，因此未作任何更改。请刷新名单。',
    },
    'roster_csv_empty': {
        'en': 'No roster data was provided. Choose a file, or paste the roster text, then upload again.',
        'zh-CN': '未提供名单数据。请选择文件或粘贴名单文本，然后重新上传。',
    },
    'roster_row_needs_identity': {
        'en': 'This row has neither a student number nor an email address, so no student was created from it.',
        'zh-CN': '该行既没有学号也没有邮箱，因此未据此创建学生。',
    },
    'roster_row_failed': {
        'en': 'This row could not be saved, so no student was created from it. Check the row and upload it again; if it keeps failing, contact support.',
        'zh-CN': '该行无法保存，因此未据此创建学生。请检查该行后重新上传；如持续失败，请联系技术支持。',
    },
    'roster_identity_required': {
        'en': 'Enter a student number or an email address for the student.',
        'zh-CN': '请输入该学生的学号或邮箱。',
    },
    'roster_add_failed': {
        'en': 'The student could not be added. Check the details and try again; if it keeps failing, contact support.',
        'zh-CN': '无法添加该学生。请检查信息后重试；如持续失败，请联系技术支持。',
    },

    # -- team management -----------------------------------------------------
    'team_management_unknown_action': {
        'en': 'The console asked team management for something it cannot do. Reload the console and try again.',
        'zh-CN': '控制台向团队管理发出了无法执行的请求。请刷新控制台后重试。',
    },
    'assignments_required': {
        'en': 'No team assignments were included in this request, so nothing was changed.',
        'zh-CN': '本次请求未包含任何团队分配，因此未作任何更改。',
    },
    'team_rename_incomplete': {
        'en': 'Choose a team and enter its new name.',
        'zh-CN': '请选择团队并输入新名称。',
    },
    'team_not_found': {
        'en': 'That team no longer exists. Reload the console.',
        'zh-CN': '该团队已不存在。请刷新控制台。',
    },

    # -- round schedule ------------------------------------------------------
    'schedule_rounds_required': {
        'en': 'No rounds were included in this schedule, so nothing was scheduled.',
        'zh-CN': '该日程未包含任何回合，因此未安排任何日程。',
    },
    'schedule_round_not_in_game': {
        'en': 'One of the rounds in this schedule is not part of this game.',
        'zh-CN': '该日程中有回合不属于该游戏。',
    },
    'schedule_round_frozen': {
        'en': 'Round {round} is {status}; its schedule can no longer change.',
        'zh-CN': '第 {round} 回合{status}；其日程不能再更改。',
    },
    'schedule_invalid_time': {
        'en': 'Round {round} has a time that could not be read as a date and time.',
        'zh-CN': '第 {round} 回合有一个时间无法识别为日期和时间。',
    },
    'schedule_rejected_guidance': {
        'en': 'Nothing was scheduled. Fix the listed rounds and resend the whole schedule.',
        'zh-CN': '未安排任何日程。请修正所列回合后重新提交整个日程。',
    },

    # -- grading -------------------------------------------------------------
    'grading_course_required': {
        'en': 'Choose a course first. The request did not say which course it was for.',
        'zh-CN': '请先选择课程。本次请求未指明课程。',
    },
    'grading_game_and_course_required': {
        'en': 'Choose a game and a course first. The request did not say which it was for.',
        'zh-CN': '请先选择游戏和课程。本次请求未指明游戏或课程。',
    },
    'grading_game_required': {
        'en': 'Choose a game first. The request did not say which game it was for.',
        'zh-CN': '请先选择游戏。本次请求未指明游戏。',
    },
    'grading_override_incomplete': {
        'en': 'Choose a game and a team, and enter the score, before overriding a grade.',
        'zh-CN': '修改成绩前，请先选择游戏和团队，并输入分数。',
    },
    'grading_clear_incomplete': {
        'en': 'Choose a game and a team before removing a grade override.',
        'zh-CN': '撤销成绩修改前，请先选择游戏和团队。',
    },
    'grade_not_found': {
        'en': 'There is no grade for that team yet. Calculate grades first.',
        'zh-CN': '该团队尚无成绩。请先计算成绩。',
    },

    # -- the 2026-09-21 remainder: unlock, supply-chain inject, legacy routes --
    'unlock_already_processed': {
        'en': 'Round {round} has already been processed; unlocking now would not change its results.',
        'zh-CN': '第 {round} 回合已结算；此时解锁不会改变其结果。',
    },
    'unlock_already_processed_guidance': {
        'en': 'Use the recovery workflow if a processed round must be corrected.',
        'zh-CN': '如需更正已结算的回合，请使用恢复流程。',
    },
    'submission_not_locked': {
        'en': 'Submission is not locked.',
        'zh-CN': '该提交未处于锁定状态。',
    },
    'submission_not_locked_guidance': {
        'en': 'Refresh — it may already have been unlocked.',
        'zh-CN': '请刷新——它可能已被解锁。',
    },
    'sc_inject_round_not_open': {
        'en': 'Round {round} is "{status}"; an event staged now would not fire in it.',
        'zh-CN': '第 {round} 回合{status}；此时安排的事件不会在该回合触发。',
    },
    'sc_inject_round_not_open_guidance': {
        'en': 'Inject into an open round, or advance first.',
        'zh-CN': '请在已开放的回合中注入事件，或先推进到下一回合。',
    },
    'no_active_round': {
        'en': 'No active round.',
        'zh-CN': '当前没有进行中的回合。',
    },
    'accounts_csv_empty': {
        'en': 'No account data was provided. Paste the account list, then upload again.',
        'zh-CN': '未提供账号数据。请粘贴账号列表后重新上传。',
    },
    'accounts_row_missing_username': {
        'en': 'This row has no username, so no account was created from it.',
        'zh-CN': '此行没有用户名，因此未据此创建账号。',
    },
    'accounts_row_invalid_team': {
        'en': 'This row names a team, "{value}", that is not a number, so no account was created from it.',
        'zh-CN': '此行填写的团队“{value}”不是数字，因此未据此创建账号。',
    },
    'game_creation_market_unknown': {
        'en': 'Market code "{code}" is not a market in scenario "{scenario}".',
        'zh-CN': '场景“{scenario}”中没有代码为“{code}”的市场。',
    },
    'game_creation_no_starter_profiles': {
        'en': 'Scenario "{scenario}" has no starter profiles, so no game can be created from it.',
        'zh-CN': '场景“{scenario}”没有初始企业档案，因此无法据此创建游戏。',
    },
    'game_creation_no_starting_platform': {
        'en': 'Scenario "{scenario}" has no starting platform generation, so no game can be created from it.',
        'zh-CN': '场景“{scenario}”没有初始平台代次，因此无法据此创建游戏。',
    },
    'game_creation_failed': {
        'en': 'The game could not be created: {detail}',
        'zh-CN': '无法创建游戏。系统给出的原因（英文）：{detail}',
    },
    'fire_events_failed': {
        'en': 'Events could not be fired: {detail}',
        'zh-CN': '无法触发事件。系统给出的原因（英文）：{detail}',
    },
    'password_blank': {
        'en': 'Password cannot be blank.',
        'zh-CN': '密码不能为空。',
    },
    'password_too_short': {
        'en': 'Password must be at least {minimum} characters.',
        'zh-CN': '密码至少需要 {minimum} 个字符。',
    },
    'fire_events_incomplete': {
        'en': 'Choose a game and a round before firing events.',
        'zh-CN': '请先选择游戏和回合，然后再触发事件。',
    },
    'fire_events_not_numbers': {
        'en': 'The game and the round must each be given as a whole number.',
        'zh-CN': '游戏和回合都必须以整数表示。',
    },

    # -- confirmations: what the console shows when an action SUCCEEDED -------
    # `done_` keys are never refusals and never travel as a code. Every
    # lifecycle confirmation names its game: several heats run at once on one
    # deployment, and acting on the wrong heat is unrecoverable.
    'done_round_closed': {
        'en': '{game}: round {round} closed. {count} submission(s) locked.',
        'zh-CN': '{game}：第 {round} 回合已关闭。已锁定 {count} 份提交。',
    },
    'done_round_reopened': {
        'en': '{game}: round {round} reopened. {count} submission(s) unlocked.',
        'zh-CN': '{game}：第 {round} 回合已重新开放。已解锁 {count} 份提交。',
    },
    'done_round_processed': {
        'en': '{game}: round {round} processed in {seconds}s. Results are available; narratives are generating in the background.',
        'zh-CN': '{game}：第 {round} 回合已结算，用时 {seconds} 秒。结果已可查看；叙述内容正在后台生成。',
    },
    'done_game_complete': {
        'en': '{game}: round {round} was the last round. Game complete.',
        'zh-CN': '{game}：第 {round} 回合是最后一个回合。游戏已结束。',
    },
    'done_advanced': {
        'en': '{game}: advanced to round {round}.',
        'zh-CN': '{game}：已进入第 {round} 回合。',
    },
    'done_deadline_updated': {
        'en': '{game}: deadline updated.',
        'zh-CN': '{game}：截止时间已更新。',
    },
    'done_deadline_cleared': {
        'en': '{game}: deadline cleared.',
        'zh-CN': '{game}：截止时间已清除。',
    },
    'done_deadline_in_past_warning': {
        'en': 'That deadline is in the past — the round will close within a minute.',
        'zh-CN': '该截止时间已过——回合将在一分钟内关闭。',
    },
    'done_deadline_extended': {
        'en': '{game}: deadline extended by {hours} hour(s).',
        'zh-CN': '{game}：截止时间已延长 {hours} 小时。',
    },
    'done_deadline_extended_and_reopened': {
        'en': '{game}: deadline extended by {hours} hour(s). The round was closed, so it has been reopened and {count} submission(s) unlocked.',
        'zh-CN': '{game}：截止时间已延长 {hours} 小时。该回合此前已关闭，现已重新开放，并已解锁 {count} 份提交。',
    },
    'done_legacy_advanced': {
        'en': '{game}: round advanced to {round}.',
        'zh-CN': '{game}：已推进到第 {round} 回合。',
    },
    'done_event_injected': {
        'en': 'Event "{event}" injected.',
        'zh-CN': '事件“{event}”已注入。',
    },
    'done_sc_event_queued': {
        'en': '"{event}" queued — fires when round {round} is advanced.',
        'zh-CN': '“{event}”已排入队列——将在第 {round} 回合推进时触发。',
    },
    'done_game_archived': {
        'en': 'Game archived. Section is now free for a new game.',
        'zh-CN': '游戏已归档。该班级现在可以开设新的游戏。',
    },
    'done_password_updated': {
        'en': 'Password updated for {username}.',
        'zh-CN': '已更新 {username} 的密码。',
    },
    'done_passwords_reset': {
        'en': 'Reset {count} password(s) to the student ID default.',
        'zh-CN': '已将 {count} 个密码重置为默认的学号密码。',
    },
    'done_password_skipped_no_identity': {
        'en': 'no student ID or username',
        'zh-CN': '没有学号或用户名',
    },
    'done_enrollment_removed': {
        'en': 'Enrollment removed.',
        'zh-CN': '已移除该注册记录。',
    },
}

# Codes that shipped before this catalogue and cover more than one sentence.
# The code is the API; the key is the sentence.
CODES = {
    'state_moved_round': 'state_moved',
    'state_moved_status': 'state_moved',
    'reopen_already_processed': 'round_already_processed',
    'process_already_processed': 'round_already_processed',
    'legacy_advance_already_processed': 'round_already_processed',
    'inject_already_processed': 'round_already_processed',
    'extend_already_processed': 'round_already_processed',
    'legacy_advance_failed': 'advance_failed',
    'unlock_already_processed': 'round_already_processed',
    'sc_inject_round_not_open': 'round_not_open',
}

# Refusals rendered by OTHER catalogues through `language_for_request`, which
# the console may therefore also show verbatim.
COHORT_BILINGUAL_CODES = (
    'competition_course_unowned', 'team_count_refused', 'section_full',
    'team_full',
    # Cohort ownership and game deletion (crv2-08-operator-route-ownership).
    'cohort_belongs_to_another_instructor', 'roster_add_failed',
    'competition_game_not_deletable', 'game_has_record',
    # Reset to Setup on a competition heat (W-CE-26).
    'competition_game_not_resettable',
)

# A refusal composed from several catalogue sentences rather than rendered
# from one key: the bulk schedule lists every round it refused.
COMPOSED_CODES = ('schedule_rejected',)
# ...and the sentences it is composed from, which never travel as a code.
COMPOSED_PARTS = ('schedule_round_not_in_game', 'schedule_round_frozen',
                  'schedule_invalid_time')

_GUIDANCE = '_guidance'
# A confirmation of something that succeeded. Not a refusal, so never a code.
_DONE = 'done_'


def operator_code(key):
    """The stable machine code that travels with `key`'s sentence."""
    return CODES.get(key, key)


def bilingual_codes():
    """Every code whose sentence reaches the console in the reader's language."""
    own = {operator_code(key) for key in MESSAGES
           if not key.endswith(_GUIDANCE) and not key.startswith(_DONE)
           and key not in COMPOSED_PARTS}
    return sorted(own | set(COHORT_BILINGUAL_CODES) | set(COMPOSED_CODES))


def round_status(status):
    """A round status as a value that renders in whichever language is asked."""
    return lambda language: _label(ROUND_STATUS_LABELS, status, language)


def stored_round_status(status):
    """The stored token in English, the label in any other language.

    For a refusal whose English sentence has always quoted the stored status
    (`Round 2 is "closed"; ...`): the operator audit row records the English
    rendering and must not change, while a Chinese sentence must not frame an
    English storage token.
    """
    return lambda language: (str(status) if language == 'en' else
                             _label(ROUND_STATUS_LABELS, status, language))


def game_status(status):
    return lambda language: _label(GAME_STATUS_LABELS, status, language)


def participation_status(status):
    return lambda language: _label(PARTICIPATION_STATUS_LABELS, status, language)


def submission_origin_label(origin, language='en'):
    """The drill-down's origin label; an unknown origin reads as its token."""
    return _label(SUBMISSION_ORIGIN_LABELS, origin, language)


def _label(table, status, language):
    labels = table.get(status)
    if labels is None:
        return str(status)
    return labels.get(language, labels['en'])


def _resolve(values, language):
    return {name: (value(language) if callable(value) else value)
            for name, value in values.items()}


def operator_message(key, *, language='en', **values):
    """Render a reviewed operator-facing sentence in the requested language."""
    try:
        entry = MESSAGES[key]
    except KeyError as error:
        raise KeyError(f'Unknown operator message {key!r}') from error
    template = entry.get(language) or entry['en']
    return template.format(**_resolve(values, language))


def localise_conflict(conflict, language='en'):
    """A stored conflict as the operator reading the log reads it (W-CE2-04).

    The audit row is English and stays English (R44). A row written by
    `OperatorAction.record_fault` carries the catalogue key it was built from
    and the technical cause, so its sentence can be rendered again for the
    reader without changing anything stored. Every other row -- a lifecycle
    refusal, whose values are not stored -- is returned exactly as it is.
    """
    if not isinstance(conflict, dict):
        return conflict
    key = conflict.get('message_key')
    if not key or key not in MESSAGES or language == 'en':
        return conflict
    try:
        return dict(conflict, detail=operator_message(
            key, language=language, detail=conflict.get('cause', '')))
    except Exception:
        return conflict


def operator_refusal(request, key, **values):
    """The response body for a plain (non-lifecycle) operator refusal."""
    return {
        'error': operator_message(
            key, language=language_for_request(request), **values),
        'code': operator_code(key),
    }


def lifecycle_refusal(error_class, key, *, guidance_key=None, **values):
    """A `LifecycleError` whose response is localised and whose audit is not.

    `detail` and `guidance` are the English rendering: that is what the
    operator audit row records and what the server log prints. `localise` lets
    `lifecycle_view` answer in the operator's language. The guidance line is
    `<key>_guidance` unless `guidance_key` names a shared one.
    """
    guidance_key = guidance_key or key + _GUIDANCE

    def render(language):
        guidance = (operator_message(guidance_key, language=language, **values)
                    if guidance_key in MESSAGES else '')
        return operator_message(key, language=language, **values), guidance

    detail, guidance = render('en')
    return error_class(detail, guidance=guidance, code=operator_code(key),
                       localise=render)


def composed_lifecycle_refusal(error_class, code, parts, *, guidance_key):
    """One refusal listing several catalogue sentences, e.g. a bulk schedule.

    `parts` is a list of `(key, values)`; they are joined in the reader's
    language, and in English for the audit row.
    """
    def render(language):
        detail = '; '.join(operator_message(key, language=language, **values)
                           for key, values in parts)
        return detail, operator_message(guidance_key, language=language)

    detail, guidance = render('en')
    return error_class(detail, guidance=guidance, code=code, localise=render)
