import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useDecisions } from '../contexts/DecisionContext';

/**
 * Re-read the stored submission whenever the student moves between screens.
 *
 * `DecisionProvider` sits above every student route, so it mounts once and
 * used to read the draft once. Every decision page initialises itself from
 * that draft, so a page revisited without a browser reload showed the round as
 * it stood at login, and its next save -- which replaces the whole section --
 * was built on that stale picture. To a student that is a save that worked and
 * was never read back.
 *
 * It lives here rather than inside the provider so the provider does not need
 * a router to be tested. Renders nothing.
 */
const DraftRefreshOnNavigate = () => {
  const { pathname } = useLocation();
  const { loadDraft } = useDecisions();
  const first = useRef(true);
  const load = useRef(loadDraft);
  load.current = loadDraft;

  useEffect(() => {
    // The provider has already loaded the draft for the first screen.
    if (first.current) { first.current = false; return; }
    load.current();
  }, [pathname]);

  return null;
};

export default DraftRefreshOnNavigate;
