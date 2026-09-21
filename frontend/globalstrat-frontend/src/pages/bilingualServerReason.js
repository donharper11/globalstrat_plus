/**
 * The server's own reason for a refusal -- but only when the server wrote it
 * in the instructor's language.
 *
 * The operator routes the console calls during a live round refuse through
 * `core/utils/operator_messages.py` (and the cohort caps through
 * `core/utils/cohort_messages.py`), in the request's language, each with a
 * stable machine `code`. Those codes are listed here, and a sentence carrying
 * one is shown exactly as the server wrote it. Routes not yet converted still
 * refuse in English only (DRF's `'This field is required.'`, the game-creation
 * and student-account routes), sometimes naming storage fields; a catch block
 * that has a catalogue sentence keeps it unless the refusal carries one of
 * these codes.
 *
 * This list is not free-hand: the backend test
 * `core.tests.test_operator_refusal_language` fails unless it is exactly
 * `operator_messages.bilingual_codes()`. Add a code here only by adding the
 * bilingual sentence there.
 */
export const BILINGUAL_REFUSAL_CODES = Object.freeze([
  'advance_failed',
  'advance_refused',
  'assignments_required',
  'competition_course_unowned',
  'deadline_in_past',
  'deadline_required',
  'deadline_unparseable',
  'expected_round_not_a_number',
  'game_already_archived',
  'game_belongs_to_another_instructor',
  'game_not_active',
  'game_not_found',
  'game_not_in_setup',
  'game_not_paused',
  'grade_not_found',
  'grading_clear_incomplete',
  'grading_course_required',
  'grading_game_and_course_required',
  'grading_game_required',
  'grading_override_incomplete',
  'hours_not_a_number',
  'minutes_not_a_number',
  'processing_failed',
  'reason_required',
  'roster_account_not_found',
  'roster_add_failed',
  'roster_csv_empty',
  'roster_identity_required',
  'roster_row_failed',
  'roster_row_needs_identity',
  'roster_student_not_found',
  'roster_student_required',
  'roster_unknown_action',
  'round_1_started',
  'round_already_closed',
  'round_already_open',
  'round_already_processed',
  'round_missing',
  'round_not_open',
  'round_not_processed',
  'round_not_ready',
  'round_one_missing',
  'round_still_open',
  'scenario_has_no_markets',
  'schedule_rejected',
  'schedule_rounds_required',
  'section_full',
  'section_not_found',
  'section_required',
  'state_moved',
  'team_config_invalid_market',
  'team_config_no_teams',
  'team_config_team_not_in_game',
  'team_count_refused',
  'team_full',
  'team_management_unknown_action',
  'team_not_found',
  'team_not_locked',
  'team_rename_incomplete',
]);

const text = (value) => (typeof value === 'string' && value.length > 0 ? value : null);

/**
 * The bilingual sentence, followed by the server's "what to do next" line when
 * a lifecycle refusal carries one (`guidance` is localised with `error`).
 */
export const bilingualServerReason = (err) => {
  const data = err?.response?.data;
  if (!data || typeof data !== 'object') return null;
  if (!BILINGUAL_REFUSAL_CODES.includes(data.code)) return null;
  const reason = text(data.error);
  if (!reason) return null;
  const guidance = text(data.guidance);
  return guidance ? `${reason} ${guidance}` : reason;
};

/**
 * For the toasts that have always shown the server's reason first: the
 * bilingual sentence (with its guidance) when there is one, otherwise whatever
 * the server said. An English reason is kept rather than replaced by "Failed
 * to save": it is wrong in language but right in content, and the generic
 * sentence would be the reverse.
 */
export const serverReason = (err) => (
  bilingualServerReason(err) || text(err?.response?.data?.error)
);
