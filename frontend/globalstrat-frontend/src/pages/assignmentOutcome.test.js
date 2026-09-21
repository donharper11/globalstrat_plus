import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import {
  assignmentOutcome, announceAssignment, UnderMinimumNotice,
} from './assignmentOutcome';

/**
 * V2-104. `PUT /api/team-management/` answers 200 with a per-item `errors`
 * list, because a batch can be partly refused. The status therefore never says
 * what happened, and a caller that does not read `errors` reports a refused
 * assignment as a success -- which is what the dashboard did.
 *
 * The add-to-team paths were repaired at 1855b25, inline and untested. These
 * tests pin the one reading of the response every call site now shares;
 * `assignmentCallSites.test.js` is the guard that no call site discards it.
 */

const REFUSAL_EN = 'Zenith Hardware already has 5 members, the maximum this '
  + 'section allows. Choose another team, or raise the team size limit.';
const REFUSAL_ZH = 'Zenith Hardware 已有 5 名成员，已达本班级允许的上限。'
  + '请选择其他团队，或提高团队人数上限。';

describe('assignmentOutcome', () => {
  test('a wholly refused batch is a refusal, whatever the status said', () => {
    const outcome = assignmentOutcome(
      { updated: 0, errors: [{ item: {}, error: REFUSAL_EN }] });
    expect(outcome).toEqual({
      kind: 'refused', assigned: 0, refusals: [REFUSAL_EN], underMinimum: [],
    });
  });

  test('a partly refused batch reports both halves accurately', () => {
    const outcome = assignmentOutcome({
      updated: 2,
      errors: [{ item: {}, error: REFUSAL_ZH }],
    });
    expect(outcome.kind).toBe('partial');
    expect(outcome.assigned).toBe(2);
    expect(outcome.refusals).toEqual([REFUSAL_ZH]);
  });

  test('a clean batch is a success for exactly the number the server wrote', () => {
    expect(assignmentOutcome({ updated: 3, errors: [], under_minimum: [] }))
      .toEqual({ kind: 'assigned', assigned: 3, refusals: [], underMinimum: [] });
  });

  test('a response that confirms nothing is not reported as a success', () => {
    // The old code fell back to the number it had ASKED for.
    for (const data of [undefined, null, {}, { errors: [] }, { updated: 0, errors: [] }]) {
      expect(assignmentOutcome(data).kind).toBe('unconfirmed');
    }
  });
});

describe('announceAssignment', () => {
  const ui = () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
    message: { success: jest.fn(), warning: jest.fn(), error: jest.fn() },
    Modal: { warning: jest.fn() },
  });

  test('a refusal raises the server’s own wording and no success toast', () => {
    const io = ui();
    announceAssignment(
      assignmentOutcome({ updated: 0, errors: [{ error: REFUSAL_ZH }] }), io);

    expect(io.message.success).not.toHaveBeenCalled();
    expect(io.Modal.warning).toHaveBeenCalledTimes(1);
    const shown = io.Modal.warning.mock.calls[0][0];
    expect(shown.title).toBe('instructor.assign_none');
    // The cap's wording is the server's, shown verbatim in the language the
    // server chose for this instructor.
    const { container } = render(shown.content);
    expect(container).toHaveTextContent(REFUSAL_ZH);
  });

  test('a partial result names how many were seated and how many were not', () => {
    const io = ui();
    announceAssignment(assignmentOutcome({
      updated: 2, errors: [{ error: REFUSAL_EN }],
    }), io);

    expect(io.message.success).not.toHaveBeenCalled();
    expect(io.Modal.warning.mock.calls[0][0].title)
      .toBe('instructor.assign_partial {"assigned":2,"refused":1}');
  });

  test('a success counts what the server wrote', () => {
    const io = ui();
    announceAssignment(assignmentOutcome({ updated: 3, errors: [] }), io);
    expect(io.message.success)
      .toHaveBeenCalledWith('instructor.students_assigned {"count":3}');
    expect(io.Modal.warning).not.toHaveBeenCalled();
  });

  test('removing a student uses the removal wording, and is quiet on success', () => {
    const io = ui();
    announceAssignment(
      assignmentOutcome({ updated: 1, errors: [] }), { ...io, mode: 'unassign' });
    expect(io.message.success).not.toHaveBeenCalled();
    expect(io.Modal.warning).not.toHaveBeenCalled();

    announceAssignment(
      assignmentOutcome({ updated: 0, errors: [{ error: 'x' }] }),
      { ...io, mode: 'unassign' });
    expect(io.Modal.warning.mock.calls[0][0].title).toBe('instructor.unassign_none');
  });

  test('an unconfirmed result is a warning, never a success', () => {
    const io = ui();
    announceAssignment(assignmentOutcome({}), io);
    expect(io.message.success).not.toHaveBeenCalled();
    expect(io.message.warning).toHaveBeenCalledWith('instructor.assign_unconfirmed');
  });
});

/**
 * R12 / V2-042: teams are 3-5 members. The maximum is refused; the minimum is
 * only reported, because a team is legitimately short for the whole time it is
 * being filled. The server has returned `under_minimum` since the cap was
 * enforced and its comment said the console showed it. Nothing read it.
 */
const SHORT_EN = 'Zenith Hardware has 1 member(s); this section expects at '
  + 'least 3. Add members before the game starts.';
const SHORT_ZH = 'Apex Devices 目前有 2 名成员；本班级要求至少 3 名。请在比赛开始前补充成员。';
const underMinimum = [
  { team_id: 7, team_name: 'Zenith Hardware', member_count: 1, minimum: 3, detail: SHORT_EN },
  { team_id: 8, team_name: 'Apex Devices', member_count: 2, minimum: 3, detail: SHORT_ZH },
];

describe('teams below the minimum size', () => {
  const ui = () => ({
    t: (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key),
    message: { success: jest.fn(), warning: jest.fn(), error: jest.fn() },
    Modal: { warning: jest.fn() },
    onUnderMinimum: jest.fn(),
  });

  test('the server’s sentences are read from the response, verbatim', () => {
    const outcome = assignmentOutcome({ updated: 1, errors: [], under_minimum: underMinimum });
    expect(outcome.kind).toBe('assigned');
    expect(outcome.underMinimum).toEqual([SHORT_EN, SHORT_ZH]);
  });

  test('a malformed list is no notice, not a crash', () => {
    for (const value of [undefined, null, 'x', [{}], [{ detail: '' }], [null]]) {
      expect(assignmentOutcome({ updated: 1, errors: [], under_minimum: value })
        .underMinimum).toEqual([]);
    }
  });

  test('it does not block: the assignment is still announced as a success', () => {
    const io = ui();
    announceAssignment(
      assignmentOutcome({ updated: 1, errors: [], under_minimum: underMinimum }), io);
    expect(io.message.success).toHaveBeenCalledTimes(1);
    expect(io.Modal.warning).not.toHaveBeenCalled();
    expect(io.onUnderMinimum).toHaveBeenCalledWith([SHORT_EN, SHORT_ZH]);
  });

  test('the notice is withdrawn when the server stops reporting the team', () => {
    const io = ui();
    announceAssignment(
      assignmentOutcome({ updated: 1, errors: [], under_minimum: [] }), io);
    expect(io.onUnderMinimum).toHaveBeenCalledWith([]);
  });

  test('a refused batch still reports the short teams', () => {
    const io = ui();
    announceAssignment(assignmentOutcome({
      updated: 0, errors: [{ item: {}, error: REFUSAL_EN }], under_minimum: underMinimum,
    }), io);
    expect(io.Modal.warning).toHaveBeenCalledTimes(1);
    expect(io.onUnderMinimum).toHaveBeenCalledWith([SHORT_EN, SHORT_ZH]);
  });

  test('a response that confirms nothing leaves the standing notice alone', () => {
    const io = ui();
    announceAssignment(assignmentOutcome(undefined), io);
    expect(io.onUnderMinimum).not.toHaveBeenCalled();
  });

  test('the notice shows each sentence as a warning, and nothing when there is none', () => {
    const t = (key, values) => (values ? `${key} ${JSON.stringify(values)}` : key);
    const { container, rerender } = render(
      <UnderMinimumNotice notices={[SHORT_EN, SHORT_ZH]} t={t} />);
    expect(container).toHaveTextContent('instructor.teams_under_minimum {"count":2}');
    expect(container).toHaveTextContent('instructor.teams_under_minimum_note');
    expect(container).toHaveTextContent(SHORT_EN);
    expect(container).toHaveTextContent(SHORT_ZH);
    expect(container.querySelector('.ant-alert-warning')).not.toBeNull();

    rerender(<UnderMinimumNotice notices={[]} t={t} />);
    expect(container).toBeEmptyDOMElement();
  });
});
