import React from 'react';

/**
 * What a CSV roster upload actually did (D6 of 2026-09-21; the V2-104 defect
 * shape, on the roster).
 *
 * `POST /api/roster/ {action: 'upload'}` answers 201 with
 * `{created, updated, errors: [{row, error, code}]}`. It is a batch, and a
 * batch can be partly refused: a row past the section's capacity (R12), a row
 * with neither a student number nor an email, a row the database would not
 * take. The status is 201 either way, so a caller that reads only `created`
 * announces "Created 3 students" while seven rows were refused and says
 * nothing about them. Both upload controls go through here so the response is
 * read one way, and `rosterUploadCallSites.test.js` keeps it so.
 *
 * `created` and `existing` are the numbers the SERVER reported, never the
 * number of rows that were sent. `existing` is the server's `updated`: rows
 * whose student was already on this roster, which a re-upload legitimately
 * contains. Both count as accepted. A response that confirms nothing is
 * `unconfirmed`, not a success.
 *
 * Each refusal keeps its row number (the header is row 1, as in a
 * spreadsheet) and the server's own sentence, which the server writes in the
 * instructor's language (`core/utils/operator_messages.py`, `cohort_messages`).
 */
const count = (value) => (Number.isInteger(value) && value > 0 ? value : 0);

export const rosterUploadOutcome = (data) => {
  const rows = Array.isArray(data?.errors) ? data.errors : [];
  const refusals = rows.map((entry) => ({
    row: Number.isInteger(entry?.row) ? entry.row : null,
    text: typeof entry?.error === 'string' && entry.error.length > 0
      ? entry.error : null,
  }));
  const created = count(data?.created);
  const existing = count(data?.updated);
  const accepted = created + existing;

  let kind;
  if (refusals.length > 0) kind = accepted > 0 ? 'partial' : 'refused';
  else kind = accepted > 0 ? 'uploaded' : 'unconfirmed';
  return { kind, created, existing, accepted, refusals };
};

/**
 * Tell the instructor, and hand the outcome back so the caller can decide
 * what to keep on screen (the pasted text survives anything but a clean
 * upload, so the refused rows can be corrected and sent again).
 *
 * A clean upload is a toast. Anything refused is a modal that stays until it
 * is dismissed: a list of rows is not something to read in three seconds.
 */
export const announceRosterUpload = (outcome, { t, message, Modal, fileName }) => {
  if (outcome.kind === 'uploaded') {
    message.success(outcome.existing > 0
      ? t('instructor.roster_upload_added_existing', {
        created: outcome.created, existing: outcome.existing,
      })
      : t('instructor.roster_upload_added', { created: outcome.created }));
    return outcome;
  }
  if (outcome.kind === 'unconfirmed') {
    message.warning(t('instructor.roster_upload_unconfirmed'));
    return outcome;
  }

  const title = outcome.kind === 'partial'
    ? t('instructor.roster_upload_partial', {
      accepted: outcome.accepted, refused: outcome.refusals.length,
    })
    : t('instructor.roster_upload_none', { refused: outcome.refusals.length });

  Modal.warning({
    title,
    width: 560,
    content: (
      <div data-testid="roster-upload-refusals">
        {fileName
          ? <div style={{ marginBottom: 6 }}>{t('instructor.roster_upload_file', { file: fileName })}</div>
          : null}
        {outcome.kind === 'partial' ? (
          <div style={{ marginBottom: 6 }}>
            {t('instructor.roster_upload_accepted_detail', {
              created: outcome.created, existing: outcome.existing,
            })}
          </div>
        ) : null}
        <ul style={{ margin: 0, paddingLeft: 18, maxHeight: 280, overflowY: 'auto' }}>
          {outcome.refusals.map((refusal, index) => {
            const reason = refusal.text || t('instructor.roster_upload_no_reason');
            return (
              <li key={index}>
                {refusal.row === null
                  ? reason
                  : t('instructor.roster_upload_row', { row: refusal.row, reason })}
              </li>
            );
          })}
        </ul>
        <div style={{ marginTop: 6 }}>{t('instructor.roster_upload_fix_note')}</div>
      </div>
    ),
  });
  return outcome;
};
