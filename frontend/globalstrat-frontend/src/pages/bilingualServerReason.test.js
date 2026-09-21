import fs from 'fs';
import path from 'path';
import { bilingualServerReason } from './bilingualServerReason';

const refusal = (data) => ({ response: { status: 400, data } });
const UNOWNED_ZH = 'Heat 1 是比赛场次，但尚未指定负责教师，因此无法开启或修改。'
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
      { error: 'Round 7 not found in game 3.', code: 'schedule_rejected' },
      { error: 'enrollment_id is required.' },
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
