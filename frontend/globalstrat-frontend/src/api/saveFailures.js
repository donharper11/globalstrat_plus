/**
 * Every refused decision write, in one place.
 *
 * R17 ruled that a contended save must tell the student and be retried. The
 * obvious home for that was DecisionContext's autosave -- except that
 * `updateDraft` is exported and called by nothing, so `isDirty` never becomes
 * true, the 30s autosave never arms and `saveDraft` never runs in the shipped
 * product. Every decision a team actually saves goes through a page's own
 * `patchDecision(...)` call, and eight of those pages end in
 * `catch { /* ignore *\/ }`.
 *
 * So the refusal is caught at the one point all of them share: the axios
 * response interceptor. A page cannot forget to use this, and a page added
 * tomorrow is covered without being told about it.
 *
 * This module is deliberately free of imports. `api/client.js` publishes to
 * it, `contexts/DecisionContext.js` subscribes to it, and if it imported the
 * client back the two would form a cycle.
 */

const listeners = new Set();
// Refused writes still outstanding, oldest first, keyed by method and URL.
// One per section rather than one in all: see `publishSaveSuccess`.
const failures = new Map();
// Errors already announced, so a page that also reports its own failure does
// not announce it a second time.
let announced = new WeakSet();

const keyOf = (config) => (
  `${(config?.method || 'get').toLowerCase()} ${config?.url || ''}`
);

/**
 * Student writes that are not under `/decisions/` but are decisions all the
 * same, and whose pages discarded the failure (2026-09-21): choosing a tax
 * structure, and the autosave of a stakeholder-communication draft. Both are
 * replace-style, so re-sending one cannot apply it twice.
 */
const OTHER_DECISION_WRITES = [
  /\/context\/tax-structure\/?$/,
  /\/communications\/\d+\/draft\/?$/,
];

/**
 * Is this request a team saving a decision?
 *
 * Scoped by route and method rather than by which page called it. A GET that
 * fails is a read that can be retried by reloading; a refused write is an edit
 * the team believes it has made.
 */
export const isDecisionWrite = (config) => {
  const method = (config?.method || 'get').toLowerCase();
  if (method === 'get' || method === 'head' || method === 'options') return false;
  const url = config?.url || '';
  return /\/decisions\//.test(url)
    || OTHER_DECISION_WRITES.some(route => route.test(url));
};

/** The request that was refused, so a retry re-sends the edit, not a guess. */
export const getLastFailedRequest = () => {
  const outstanding = Array.from(failures.values());
  return outstanding.length
    ? outstanding[outstanding.length - 1]?.config || null
    : null;
};

export const publishSaveFailure = (error) => {
  if (error && typeof error === 'object') announced.add(error);
  if (error?.config) {
    // Retained until THIS request is accepted. Re-inserted so the newest
    // refusal is the one shown and retried. A failure with no request behind
    // it is announced but not retained: there is nothing to re-send, and
    // nothing that could ever clear it.
    const key = keyOf(error.config);
    failures.delete(key);
    failures.set(key, error);
  }
  listeners.forEach(fn => fn({ type: 'failed', error }));
};

/**
 * A decision write was accepted.
 *
 * It clears the refusal of THAT request and no other. Two pages save several
 * sections each; when any success cleared the notice, a refused staff
 * allocation followed by an accepted ESG save left the allocation unsaved and
 * the screen silent -- the loss R17 forbids, by way of the repair for it. With
 * a refusal still outstanding the listeners are told so again instead of being
 * told everything is saved.
 *
 * Called with no config it clears everything, which is what a caller that
 * saved the whole submission means.
 */
export const publishSaveSuccess = (config) => {
  if (config) failures.delete(keyOf(config));
  else failures.clear();
  const outstanding = Array.from(failures.values());
  if (outstanding.length) {
    const error = outstanding[outstanding.length - 1];
    listeners.forEach(fn => fn({ type: 'failed', error, carried: true }));
    return;
  }
  listeners.forEach(fn => fn({ type: 'saved' }));
};

/**
 * For a page's own catch block: announce a save failure the interceptor never
 * saw. An error thrown before axios sends anything -- a payload that could not
 * be built, a cancelled request -- has no response and passed no interceptor,
 * so without this it is silent however careful the interceptor is.
 */
export const reportUnpublishedFailure = (error) => {
  if (error && typeof error === 'object' && announced.has(error)) return;
  publishSaveFailure(error);
};

export const subscribeToSaves = (listener) => {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
};

/** Test seam: the module holds process-wide state. */
export const resetSaveFailures = () => {
  listeners.clear();
  failures.clear();
  announced = new WeakSet();
};
