import { useCallback, useEffect, useRef, useState } from 'react';
import { patchDecision } from '../api/decisions';
import { reportUnpublishedFailure } from '../api/saveFailures';

/**
 * Debounced autosave of one decision section at a time.
 *
 * Replaces the private `autoSave` three pages each carried. Two things were
 * wrong with those, and both lost decisions without a word:
 *
 *   - they ended in a catch block that discarded the error, so a refused save
 *     left the number on screen as though it had been stored;
 *   - they kept ONE timer for the whole page, so an edit to a second section
 *     inside the debounce cancelled the pending save of the first. Choose an
 *     entry mode, type a compliance amount within two seconds, and the entry
 *     mode was never sent.
 *
 * Here each section has its own timer. A refused save is already announced to
 * the shared notice by the axios interceptor (api/client.js), which also owns
 * the retry; this hook adds the one case the interceptor cannot see -- an
 * error thrown before any request was made -- and records which sections are
 * currently unsaved for a page that wants to mark them.
 *
 * A pending save is deliberately NOT cancelled when the page unmounts: the
 * student has made the edit, and leaving the page must not lose it.
 */
const useSectionAutosave = ({
  gameId, teamId, currentRound, locked, onSaved, delay = 2000,
}) => {
  const [savingCount, setSavingCount] = useState(0);
  const [failedSections, setFailedSections] = useState([]);
  const timers = useRef({});
  const mounted = useRef(true);
  // Read at send time, so a save scheduled before the round was locked (or
  // before a teammate locked it) is not sent after.
  const latest = useRef({});
  latest.current = { gameId, teamId, currentRound, locked, onSaved };

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const send = useCallback(async (section, data) => {
    const now = latest.current;
    if (!now.gameId || !now.teamId || !now.currentRound || now.locked) return;
    if (mounted.current) setSavingCount(n => n + 1);
    try {
      await patchDecision(now.gameId, now.teamId, now.currentRound, section, data);
      if (mounted.current) {
        setFailedSections(prev => prev.filter(name => name !== section));
      }
      if (latest.current.onSaved) latest.current.onSaved(section);
    } catch (err) {
      reportUnpublishedFailure(err);
      if (mounted.current) {
        setFailedSections(prev => (
          prev.includes(section) ? prev : [...prev, section]));
      }
    } finally {
      if (mounted.current) setSavingCount(n => Math.max(0, n - 1));
    }
  }, []);

  const autoSave = useCallback((section, data) => {
    clearTimeout(timers.current[section]);
    timers.current[section] = setTimeout(() => {
      delete timers.current[section];
      send(section, data);
    }, delay);
  }, [send, delay]);

  return { autoSave, saving: savingCount > 0, failedSections };
};

export default useSectionAutosave;
