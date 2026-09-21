import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { assignmentOutcome, announceAssignment } from './assignmentOutcome';

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
    expect(outcome).toEqual({ kind: 'refused', assigned: 0, refusals: [REFUSAL_EN] });
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
      .toEqual({ kind: 'assigned', assigned: 3, refusals: [] });
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
