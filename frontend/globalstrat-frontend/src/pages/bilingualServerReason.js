/**
 * The server's own reason for a refusal -- but only when the server wrote it
 * in the instructor's language.
 *
 * Most operator routes still refuse in English only (`'rounds list is
 * required.'`, DRF's `'This field is required.'`), and some name storage
 * fields. Showing those to an instructor working in Chinese is the defect the
 * catalogue strings exist to avoid, so a catch block that has a catalogue
 * sentence keeps it unless the refusal carries one of the codes below. Each
 * code is a refusal rendered through `core/utils/cohort_messages.py` with
 * `language_for_request()`; add a code here only when that is true of it.
 */
export const BILINGUAL_REFUSAL_CODES = Object.freeze([
  'competition_course_unowned', // lifecycle boundary, every game-scoped write
  'team_count_refused',         // game creation, R12 team-count cap
  'section_full',               // roster add, section capacity
]);

export const bilingualServerReason = (err) => {
  const data = err?.response?.data;
  if (!data || typeof data !== 'object') return null;
  if (!BILINGUAL_REFUSAL_CODES.includes(data.code)) return null;
  return typeof data.error === 'string' && data.error.length > 0
    ? data.error : null;
};
