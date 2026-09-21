import React from 'react';
import { Alert } from 'antd';

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
 *
 * `underMinimum` is the server's `under_minimum` report (R12: teams of 3-5),
 * one sentence per short team, already in the instructor's language. It is
 * advice, never a refusal, so it does not change `kind`.
 */
export const assignmentOutcome = (data) => {
  const refusals = (Array.isArray(data?.errors) ? data.errors : [])
    .map((entry) => entry?.error)
    .filter((text) => typeof text === 'string' && text.length > 0);
  const refusedCount = Array.isArray(data?.errors) ? data.errors.length : 0;
  const assigned = Number.isInteger(data?.updated) && data.updated > 0
    ? data.updated : 0;

  const underMinimum = (Array.isArray(data?.under_minimum) ? data.under_minimum : [])
    .map((entry) => entry?.detail)
    .filter((text) => typeof text === 'string' && text.length > 0);

  let kind;
  if (refusedCount > 0) kind = assigned > 0 ? 'partial' : 'refused';
  else kind = assigned > 0 ? 'assigned' : 'unconfirmed';
  return { kind, assigned, refusals, underMinimum };
};

/**
 * Tell the instructor. The refusal sentences are the server's own wording, in
 * the language the server resolved for this instructor (`cohort_messages`), and
 * are shown verbatim; only the heading is the interface's.
 *
 * `mode: 'unassign'` is removing a student from a team: it is quiet on success
 * (the roster redraws) and uses the removal wording when refused.
 *
 * `onUnderMinimum` receives the short-team sentences for `UnderMinimumNotice`.
 * It is deliberately not a toast or a modal: a team is short for the whole time
 * it is being filled, so an interruption on every click would be noise, and a
 * toast would be gone before the roster was finished.
 */
export const announceAssignment = (
  outcome, { t, message, Modal, mode = 'assign', onUnderMinimum },
) => {
  const removing = mode === 'unassign';
  // The short-team report replaces the standing notice on every response the
  // server actually gave -- including an empty one, which withdraws it. A
  // response that confirmed nothing says nothing about team sizes either.
  if (typeof onUnderMinimum === 'function' && outcome.kind !== 'unconfirmed') {
    onUnderMinimum(outcome.underMinimum || []);
  }
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

/**
 * The standing, non-blocking notice on the roster: which teams are still below
 * the section's minimum size. The sentences are the server's
 * (`cohort_messages.team_under_minimum`), shown verbatim.
 */
export const UnderMinimumNotice = ({ notices, t }) => {
  if (!Array.isArray(notices) || notices.length === 0) return null;
  return (
    <Alert
      type="warning"
      showIcon
      style={{ marginBottom: 12 }}
      message={t('instructor.teams_under_minimum', { count: notices.length })}
      description={(
        <>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {notices.map((text, index) => <li key={index}>{text}</li>)}
          </ul>
          <div style={{ marginTop: 6 }}>{t('instructor.teams_under_minimum_note')}</div>
        </>
      )}
    />
  );
};
