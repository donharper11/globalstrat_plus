/**
 * The Operator Log's "Before → after", as words (W-CE-07).
 *
 * An operator audit row stores the state a lifecycle view read under its
 * lock and the state it left, as the view's own dictionaries: `round_number`,
 * `target_market: null`, `submissions_unlocked`. Those are storage names,
 * written for the dispute runbook, and the console used to print them as
 * JSON. This module turns two such dictionaries into the fields that changed
 * and each value into the catalogue's word for it.
 *
 * Every label and every status word is a literal `t()` key: the string gate
 * cannot resolve a key chosen at run time, so a field the table does not
 * know is shown with its name humanised, never through a computed key.
 */

// Console-internal values the round-control payload carries so a button can
// be enabled; they are not something an operator did.
const HIDDEN = new Set([
  'round_id', 'game_id', 'team_id', 'seconds_remaining', 'is_overdue',
  'next_action', 'narrative_generated', 'narrative_error',
  'phase_1_duration', 'phase_2_duration', 'withdrawn_by_id',
]);

const ROUND_STATUSES = new Set(['open', 'closed', 'processed', 'pending']);
const GAME_STATUSES = new Set(['setup', 'active', 'paused', 'completed', 'archived']);
const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const missing = (value) => value === null || value === undefined || value === '';

/**
 * The fields whose value differs between `before` and `after`, in `after`'s
 * order then `before`'s. A field that only `after` has is a fact the action
 * added (an injected event's template); a null added is nothing. A field
 * only `before` has is the state read, not a change, and is left out. A list
 * of entries (a schedule's rounds, a team table) is compared entry by entry
 * so that one deadline moved does not print ten rounds.
 */
export const changedFields = (before, after) => {
  const b = isObject(before) ? before : {};
  const a = isObject(after) ? after : {};
  const keys = [...Object.keys(a), ...Object.keys(b).filter((key) => !(key in a))];
  const rows = [];
  for (const key of keys) {
    if (HIDDEN.has(key)) continue;
    if (!(key in a)) continue;
    if (!(key in b)) {
      if (!missing(a[key])) rows.push({ key, before: undefined, after: a[key] });
      continue;
    }
    if (same(a[key], b[key])) continue;
    if (Array.isArray(a[key]) && Array.isArray(b[key])) {
      const length = Math.max(a[key].length, b[key].length);
      const beforeEntries = [];
      const afterEntries = [];
      for (let index = 0; index < length; index += 1) {
        if (!same(a[key][index], b[key][index])) {
          if (index < b[key].length) beforeEntries.push(b[key][index]);
          if (index < a[key].length) afterEntries.push(a[key][index]);
        }
      }
      rows.push({ key, before: beforeEntries, after: afterEntries });
      continue;
    }
    rows.push({ key, before: b[key], after: a[key] });
  }
  return rows;
};

/** The catalogue's label for a stored field; the field's name, spaced, otherwise. */
export const fieldLabel = (key, t) => {
  const labels = {
    round_number: t('instructor.round'),
    status: t('instructor.status'),
    deadline: t('instructor.deadline'),
    reason: t('instructor.reason'),
    name: t('instructor.game_name'),
    current_round: t('instructor.oplog_current_round'),
    event_template: t('instructor.event_template'),
    target_market: t('instructor.oplog_target_market'),
    rounds_reset: t('instructor.oplog_rounds_reset'),
    reopened: t('instructor.oplog_reopened'),
    submissions_unlocked: t('instructor.oplog_submissions_unlocked'),
    opened_at: t('instructor.oplog_opened_at'),
    closed_at: t('instructor.oplog_closed_at'),
    processed_at: t('instructor.oplog_processed_at'),
    close_reason: t('instructor.oplog_close_reason'),
    processing_status: t('instructor.oplog_processing_status'),
    teams_total: t('instructor.oplog_teams_total'),
    teams_locked: t('instructor.oplog_teams_locked'),
    teams_pending: t('instructor.oplog_teams_pending'),
    rounds: t('instructor.oplog_schedule'),
    teams: t('instructor.teams'),
    home_market: t('instructor.home_market'),
    participation_status: t('instructor.oplog_participation_status'),
    withdrawn_at: t('instructor.oplog_withdrawn_at'),
    withdrawal_reason: t('instructor.oplog_withdrawal_reason'),
    locked_at: t('instructor.oplog_locked_at'),
    locked_by: t('instructor.oplog_locked_by'),
    hours: t('instructor.oplog_hours'),
  };
  return labels[key] || String(key).replace(/_/g, ' ');
};

/** One stored value, in the reader's language. */
export const formatValue = (key, value, t) => {
  if (missing(value)) return '—';
  if (value === true) return t('instructor.yes');
  if (value === false) return t('instructor.no');
  if (key === 'status' && ROUND_STATUSES.has(value)) {
    return {
      open: t('instructor.rc_status_open'),
      closed: t('instructor.rc_status_closed'),
      processed: t('instructor.rc_status_processed'),
      pending: t('instructor.rc_status_pending'),
    }[value];
  }
  if (key === 'status' && GAME_STATUSES.has(value)) {
    return {
      setup: t('instructor.oplog_game_status_setup'),
      active: t('instructor.oplog_game_status_active'),
      paused: t('instructor.oplog_game_status_paused'),
      completed: t('instructor.oplog_game_status_completed'),
      archived: t('instructor.oplog_game_status_archived'),
    }[value];
  }
  if (key === 'processing_status') {
    return {
      PENDING: t('instructor.rc_processing_pending'),
      PROCESSING: t('instructor.rc_processing_running'),
      RESULTS_AVAILABLE: t('instructor.rc_processing_results'),
      FULLY_COMPLETE: t('instructor.rc_processing_complete'),
      FAILED: t('instructor.rc_processing_failed'),
    }[value] || String(value);
  }
  if (key === 'close_reason') {
    return value === 'deadline'
      ? t('instructor.rc_closed_by_deadline')
      : t('instructor.rc_closed_by_instructor');
  }
  if (key === 'participation_status') {
    return {
      active: t('instructor.oplog_participation_active'),
      withdrawn: t('instructor.oplog_participation_withdrawn'),
    }[value] || String(value);
  }
  if (typeof value === 'string' && ISO_DATETIME.test(value)) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  }
  if (Array.isArray(value)) {
    return value.map((entry) => formatValue(key, entry, t)).join('; ');
  }
  if (isObject(value)) {
    // One schedule row or one team row: "Round 3: <deadline>", "Aurora: HM".
    if ('round_number' in value) {
      const rest = Object.keys(value).filter((k) => k !== 'round_number' && !HIDDEN.has(k));
      return `${t('instructor.oplog_round_n', { round: value.round_number })}: ${
        rest.map((k) => formatValue(k, value[k], t)).join(', ')}`;
    }
    if ('name' in value) {
      const rest = Object.keys(value).filter((k) => k !== 'name' && !HIDDEN.has(k));
      return `${value.name}: ${rest.map((k) => formatValue(k, value[k], t)).join(', ')}`;
    }
    return Object.keys(value).filter((k) => !HIDDEN.has(k))
      .map((k) => `${fieldLabel(k, t)} ${formatValue(k, value[k], t)}`).join(', ');
  }
  return String(value);
};
