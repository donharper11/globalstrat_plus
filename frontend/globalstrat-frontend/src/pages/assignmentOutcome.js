import React from 'react';

/**
 * What a team-assignment request actually did (V2-104).
 *
 * `PUT /api/team-management/` answers 200 with `{updated, errors, ...}`. It is
 * a batch, and a batch can be partly refused, so the status never says what
 * happened: a sixth member refused by the cohort cap (R12) arrives as
 * `200 {"updated": 0, "errors": [...]}`. A caller that does not read `errors`
 * reports that refusal as a success. Every call site goes through here so the
 * response is read one way, and `assignmentCallSites.test.js` keeps it so.
 *
 * `assigned` is the number the SERVER wrote, never the number that was asked
 * for. A response that confirms nothing is `unconfirmed`, not a success.
 */
export const assignmentOutcome = (data) => {
  const refusals = (Array.isArray(data?.errors) ? data.errors : [])
    .map((entry) => entry?.error)
    .filter((text) => typeof text === 'string' && text.length > 0);
  const refusedCount = Array.isArray(data?.errors) ? data.errors.length : 0;
  const assigned = Number.isInteger(data?.updated) && data.updated > 0
    ? data.updated : 0;

  let kind;
  if (refusedCount > 0) kind = assigned > 0 ? 'partial' : 'refused';
  else kind = assigned > 0 ? 'assigned' : 'unconfirmed';
  return { kind, assigned, refusals };
};

/**
 * Tell the instructor. The refusal sentences are the server's own wording, in
 * the language the server resolved for this instructor (`cohort_messages`), and
 * are shown verbatim; only the heading is the interface's.
 *
 * `mode: 'unassign'` is removing a student from a team: it is quiet on success
 * (the roster redraws) and uses the removal wording when refused.
 */
export const announceAssignment = (outcome, { t, message, Modal, mode = 'assign' }) => {
  const removing = mode === 'unassign';
  if (outcome.kind === 'assigned') {
    if (!removing) {
      message.success(t('instructor.students_assigned', { count: outcome.assigned }));
    }
    return;
  }
  if (outcome.kind === 'unconfirmed') {
    message.warning(t('instructor.assign_unconfirmed'));
    return;
  }
  let title;
  if (removing) title = t('instructor.unassign_none');
  else if (outcome.kind === 'partial') {
    title = t('instructor.assign_partial', {
      assigned: outcome.assigned,
      refused: outcome.refusals.length || 1,
    });
  } else title = t('instructor.assign_none');

  Modal.warning({
    title,
    content: (
      <ul style={{ margin: 0, paddingLeft: 18 }}>
        {outcome.refusals.map((text, index) => <li key={index}>{text}</li>)}
      </ul>
    ),
  });
};
