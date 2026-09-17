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
let lastFailure = null;

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
  return /\/decisions\//.test(config?.url || '');
};

/** The request that was refused, so a retry re-sends the edit, not a guess. */
export const getLastFailedRequest = () => lastFailure;

export const publishSaveFailure = (error) => {
  lastFailure = error?.config || null;
  listeners.forEach(fn => fn({ type: 'failed', error }));
};

export const publishSaveSuccess = () => {
  lastFailure = null;
  listeners.forEach(fn => fn({ type: 'saved' }));
};

export const subscribeToSaves = (listener) => {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
};

/** Test seam: the module holds process-wide state. */
export const resetSaveFailures = () => {
  listeners.clear();
  lastFailure = null;
};
