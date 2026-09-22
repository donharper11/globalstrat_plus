import fs from 'fs';
import path from 'path';
import {
  bilingualServerReason, serverReason, BILINGUAL_REFUSAL_CODES,
} from './bilingualServerReason';

const refusal = (data) => ({ response: { status: 400, data } });
const UNOWNED_ZH = 'Heat 1 是一场竞赛，但尚未指定负责教师，因此无法开启或修改。'
  + '请先为其所属课程指定教师，然后重试。';

describe('bilingualServerReason', () => {
  test('a refusal the server wrote in both languages is shown as written', () => {
    expect(bilingualServerReason(refusal({
      error: UNOWNED_ZH, code: 'competition_course_unowned',
    }))).toBe(UNOWNED_ZH);
  });

  test('an English-only refusal is not shown; the catalogue sentence stands', () => {
    for (const data of [
      { error: 'rounds list is required.', code: 'LifecyclePrecondition' },
      { error: 'scenario_id is required.' },
      { error: 'Only an admin can reset an instructor password.', code: 'not_listed' },
      { course_code: ['This field must be unique.'] },
    ]) expect(bilingualServerReason(refusal(data))).toBeNull();
  });

  test('anything that is not a refusal body is no reason at all', () => {
    for (const err of [undefined, null, new Error('Network Error'),
      refusal(undefined), refusal('<html>502</html>'),
      refusal({ code: 'section_full' }), refusal({ code: 'section_full', error: '' })]) {
      expect(bilingualServerReason(err)).toBeNull();
    }
  });
});

describe('operator refusals that are now bilingual (D3)', () => {
  const CLOSED_ZH = '第 2 回合已关闭。';
  const REFRESH_ZH = '请刷新控制台——截止时间调度程序或另一位操作者已先行关闭该回合。';

  test('a lifecycle refusal is shown with the guidance the server sent', () => {
    expect(bilingualServerReason(refusal({
      error: CLOSED_ZH, guidance: REFRESH_ZH, code: 'round_already_closed',
    }))).toBe(`${CLOSED_ZH} ${REFRESH_ZH}`);
  });

  test.each(['round_already_closed', 'state_moved', 'reason_required',
    'deadline_required', 'game_not_active', 'game_not_paused',
    'schedule_rejected', 'roster_student_required', 'section_required',
    'assignments_required', 'team_not_found', 'grading_course_required',
    'team_config_no_teams', 'round_1_started', 'team_full',
  ])('%s is a code the console may show verbatim', (code) => {
    expect(BILINGUAL_REFUSAL_CODES).toContain(code);
    expect(bilingualServerReason(refusal({ error: '中文', code }))).toBe('中文');
  });

  test('serverReason prefers the bilingual sentence and keeps an English one', () => {
    expect(serverReason(refusal({
      error: CLOSED_ZH, guidance: REFRESH_ZH, code: 'round_already_closed',
    }))).toBe(`${CLOSED_ZH} ${REFRESH_ZH}`);
    // Not converted yet: wrong language, right content, so it is kept.
    expect(serverReason(refusal({ error: 'scenario_id is required.' })))
      .toBe('scenario_id is required.');
    for (const err of [undefined, new Error('Network Error'), refusal({}),
      refusal({ error: '' }), refusal({ error: { nested: true } })]) {
      expect(serverReason(err)).toBeNull();
    }
  });
});

describe('the dashboard’s server reasons', () => {
  const source = fs.readFileSync(
    path.join(__dirname, 'InstructorDashboard.js'), 'utf8');

  test('no toast reads the raw error field past the shared reading', () => {
    expect(source).not.toMatch(/err\.response\?\.data\?\.error/);
    // 19 until 2026-09-22: the lifecycle card's advance-round refusal moved
    // to `components/instructor/AdvanceRoundControl.js` (W-CE-24), where its
    // own test pins the same reading.
    expect((source.match(/serverReason\(err\) \|\| t\('/g) || []).length)
      .toBeGreaterThanOrEqual(18);
  });

  test('catch blocks on converted routes no longer discard the reason', () => {
    const surfaced = [
      "bilingualServerReason(err) || t('instructor.msg_seed_rubric_failed')",
      "bilingualServerReason(err) || t('instructor.msg_update_student_failed')",
      "bilingualServerReason(err) || t('instructor.assign_failed')",
      "bilingualServerReason(err) || t('instructor.unassign_failed')",
    ];
    for (const call of surfaced) {
      expect(source).toContain(call);
      expect(source).not.toContain(
        call.replace('bilingualServerReason(err) || ', 'catch { message.error('));
    }
  });
});

describe('the dashboard’s schedule save', () => {
  const source = fs.readFileSync(
    path.join(__dirname, 'InstructorDashboard.js'), 'utf8');

  test('both ways of saving a schedule show a bilingual refusal when there is one', () => {
    // A competition game with no instructor of record refuses the schedule in
    // the instructor's language and says what to do; both catch blocks used to
    // drop that for a generic sentence.
    const saves = source.match(/await updateRoundSchedule\(/g) || [];
    const surfaced = source.match(
      /bilingualServerReason\(err\) \|\| t\('instructor\.msg_schedule_(save_failed|generated_not_saved)'\)/g) || [];
    // Three call sites; the third is the deadline field's save-on-blur, which
    // is silent by design ("Save button still available") and announces nothing.
    expect(saves.length).toBe(3);
    expect(surfaced.length).toBe(2);
  });
});
