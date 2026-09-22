import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { useGame } from './GameContext';
import { useAuth } from '../AuthContext';
import { getDecisions, saveDecisions } from '../api/decisions';
import client from '../api/client';
import {
  subscribeToSaves, getLastFailedRequest, reportUnpublishedFailure,
} from '../api/saveFailures';

const DecisionContext = createContext(null);

/**
 * The code the decision-write boundary returns when an exclusive operator
 * action holds the game lock (`core/views/decisions.py`,
 * `CompetitionDecisionWriteMixin._lifecycle_busy_response`).
 *
 * It is matched on the `code`, never on the sentence. The sentence is
 * participant copy and is expected to change -- R17 ruled that it must stop
 * claiming the round is being processed -- while the code is the contract.
 */
export const LIFECYCLE_CONFLICT_CODE = 'lifecycle_in_progress';

/** How many times a transient refusal re-attempts on its own, and how soon. */
const LIFECYCLE_RETRY_DELAYS_MS = [2000, 5000, 10000];

/**
 * Why a save was refused, and whether retrying it on a timer can help.
 *
 * The two cases need different handling and different words, and telling them
 * apart is the whole point:
 *
 *   lifecycle  -- an instructor held the exclusive game lock (extend deadline,
 *                 inject event, close, advance...). The write was refused
 *                 BEFORE any handler ran -- `test_competition_locks` asserts
 *                 the handler's call count is zero -- so nothing was validated,
 *                 nothing was written, and nothing is wrong with the edit.
 *                 Operator actions are short, so the same bytes will be
 *                 accepted in a moment: this retries itself, and retrying
 *                 cannot double-write because the first attempt did nothing.
 *   validation -- the server read the edit and objected to it. A timer will
 *                 never fix that; the team must change something, so the
 *                 server's own sentences are shown and the retry is manual.
 *   network    -- nothing answered. Retried like a lifecycle conflict, but
 *                 worded as a connection problem rather than an operator.
 */
export const classifyFailure = (err) => {
  const response = err?.response;
  if (!response) return { kind: 'network', messages: [] };
  if (response.status === 409
      && response.data?.code === LIFECYCLE_CONFLICT_CODE) {
    return { kind: 'lifecycle', messages: [] };
  }
  return { kind: 'validation', messages: describeRefusal(response.data) };
};

export const DecisionProvider = ({ children }) => {
  const { gameId, teamId, currentRound, refreshBudgets } = useGame();
  const { user } = useAuth();
  const isDemo = user?.is_demo;
  const [draft, setDraft] = useState({});
  const [isDirty, setIsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState(null);
  const [locked, setLocked] = useState(false);
  const [loadingDraft, setLoadingDraft] = useState(true);
  // R17: a refused save must show the edit was NOT saved, and retry it.
  // `saveError` is null, or {kind, messages, retrying}.
  const [saveError, setSaveError] = useState(null);
  const autoSaveTimer = useRef(null);
  const retryTimer = useRef(null);
  const retryAttempt = useRef(0);
  // How to re-send whatever was refused. It differs by who issued the write --
  // this provider's own autosave, or a page going through the interceptor --
  // so the failing path supplies it rather than this one guessing.
  const retryRunner = useRef(null);
  const sendDraftRef = useRef(null);

  // Which game/team/round the draft in state belongs to.
  const draftOwner = useRef(null);

  /**
   * Load the stored submission: on mount, on a round change, and again on
   * every navigation between student screens (`DraftRefreshOnNavigate`).
   *
   * This provider sits above every student route, so it used to read the
   * draft exactly once per session. The pages rebuild "the whole list" of a
   * section from that draft on each save, so a second product created in one
   * sitting was sent as [second] and replaced the first, and a screen
   * revisited without a reload showed the round as it stood at login -- a save
   * that worked and was never read back.
   *
   * A refresh that FAILS keeps the draft it had. Blanking it is worse than
   * staleness: the next replace-style save built from an empty draft deletes
   * what the server holds. It is blanked only when it belongs to a different
   * game, team or round.
   */
  const loadDraft = useCallback(async () => {
    if (!gameId || !teamId || !currentRound) { setLoadingDraft(false); return; }
    const owner = `${gameId}/${teamId}/${currentRound}`;
    setLoadingDraft(true);
    try {
      const res = await getDecisions(gameId, teamId, currentRound);
      draftOwner.current = owner;
      const next = res.data || {};
      // Pages re-initialise from `draft` when its identity changes. A refresh
      // that found nothing new keeps the old object, so a page is not reset
      // (and an edit in flight not overwritten) for no change.
      setDraft(prev => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next));
      setLocked(isDemo || next.status === 'locked');
    } catch {
      if (draftOwner.current !== owner) {
        setDraft({});
        setLocked(false);
      }
    } finally {
      setLoadingDraft(false);
    }
  }, [gameId, teamId, currentRound]);

  useEffect(() => { loadDraft(); }, [loadDraft]);

  const noteSaved = useCallback(() => {
    clearTimeout(retryTimer.current);
    retryAttempt.current = 0;
    retryRunner.current = null;
    setSaveError(null);
    setLastSaved(new Date());
  }, []);

  const noteFailure = useCallback((err, runner) => {
    retryRunner.current = runner || null;
    const failure = classifyFailure(err);
    const transient = failure.kind !== 'validation';
    const delay = transient && retryRunner.current
      ? LIFECYCLE_RETRY_DELAYS_MS[retryAttempt.current]
      : undefined;
    // The edit stays dirty and `lastSaved` is left alone: the indicator must
    // not go on reporting a save that did not happen.
    setSaveError({
      kind: failure.kind,
      messages: failure.messages,
      retrying: Boolean(delay),
    });
    if (delay) {
      retryAttempt.current += 1;
      clearTimeout(retryTimer.current);
      retryTimer.current = setTimeout(() => {
        if (retryRunner.current) retryRunner.current();
      }, delay);
    }
  }, []);

  /** Re-send the request that was refused -- not whatever state holds now. */
  const resendRefusedRequest = useCallback(async () => {
    const config = getLastFailedRequest();
    if (!config) return;
    setSaving(true);
    try {
      await client.request(config);
    } catch (err) {
      // The interceptor republishes a refused retry and the subscription
      // below reacts to it, so there is nothing more to do for that case. A
      // failure that never became a request is announced here instead.
      reportUnpublishedFailure(err);
    } finally {
      setSaving(false);
    }
  }, []);

  /**
   * Every decision write in the product, whoever issued it.
   *
   * The pages each save through their own `patchDecision(...)` and most of
   * them discard the error, so this listens at the axios interceptor instead
   * of asking ten pages to remember. See api/saveFailures.js.
   */
  useEffect(() => subscribeToSaves((event) => {
    if (event.type === 'saved') noteSaved();
    else noteFailure(event.error, resendRefusedRequest);
  }), [noteSaved, noteFailure, resendRefusedRequest]);

  const sendDraft = useCallback(async (payload) => {
    setSaving(true);
    try {
      await saveDecisions(gameId, teamId, currentRound, payload);
      setIsDirty(false);
      noteSaved();
      refreshBudgets();
      return true;
    } catch (err) {
      // The runner re-sends THIS payload, so a retry cannot silently send a
      // later, different edit than the one that was refused.
      noteFailure(err, () => sendDraftRef.current(payload));
      return false;
    } finally {
      setSaving(false);
    }
  }, [gameId, teamId, currentRound, refreshBudgets, noteSaved, noteFailure]);

  useEffect(() => { sendDraftRef.current = sendDraft; }, [sendDraft]);

  const saveDraft = useCallback(async () => {
    if (!gameId || !teamId || !currentRound || locked) return;
    retryAttempt.current = 0;
    clearTimeout(retryTimer.current);
    return sendDraft(draft);
  }, [gameId, teamId, currentRound, draft, locked, sendDraft]);

  /** The student pressing "Retry now" on the refusal notice. */
  const retrySave = useCallback(async () => {
    if (locked) return;
    retryAttempt.current = 0;
    clearTimeout(retryTimer.current);
    if (retryRunner.current) return retryRunner.current();
    return saveDraft();
  }, [locked, saveDraft]);

  // Auto-save every 30s if dirty
  useEffect(() => {
    if (isDirty && !locked) {
      autoSaveTimer.current = setTimeout(() => {
        saveDraft();
      }, 30000);
    }
    return () => clearTimeout(autoSaveTimer.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDirty, draft]);

  useEffect(() => () => {
    clearTimeout(autoSaveTimer.current);
    clearTimeout(retryTimer.current);
  }, []);

  const updateDraft = useCallback((section, data) => {
    setDraft(prev => ({ ...prev, [section]: data }));
    setIsDirty(true);
  }, []);

  return (
    <DecisionContext.Provider value={{
      draft, isDirty, saving, lastSaved, locked, loadingDraft, saveError,
      updateDraft, saveDraft, loadDraft, setLocked, retrySave,
    }}>
      {children}
    </DecisionContext.Provider>
  );
};

/**
 * The server's own sentences, never its field names.
 *
 * DRF refusals arrive as {field: [sentence, ...]} or {detail: sentence}, and
 * the catalogue wording behind them is already participant copy in the
 * reader's language (GSP-CRV2-12). Restating the rule here would be a second
 * copy of it, which the authoring standard forbids.
 */
export function describeRefusal(data) {
  if (!data) return [];
  if (typeof data === 'string') return [data];
  if (data.detail) return [String(data.detail)];
  const out = [];
  const walk = (value) => {
    if (Array.isArray(value)) value.forEach(walk);
    else if (value && typeof value === 'object') Object.values(value).forEach(walk);
    else if (value != null) out.push(String(value));
  };
  walk(data);
  return out;
}

export const useDecisions = () => {
  const ctx = useContext(DecisionContext);
  if (!ctx) throw new Error('useDecisions must be used within DecisionProvider');
  return ctx;
};
