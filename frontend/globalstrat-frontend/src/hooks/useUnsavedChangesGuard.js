import { useEffect, useRef } from 'react';

// BrowserRouter does not expose React Router's data-router blocker API. Keep a
// same-URL sentinel in browser history while the page is dirty so Back can be
// confirmed before the current route is actually left. Same-origin links are
// likewise delayed until the sentinel has been removed.
export default function useUnsavedChangesGuard(when, message) {
  const active = useRef(false);
  const leaving = useRef(false);

  useEffect(() => {
    if (!when) return undefined;

    active.current = true;
    leaving.current = false;
    const marker = `gs-unsaved-${Date.now()}-${Math.random()}`;
    window.history.pushState({ ...(window.history.state || {}), gsUnsavedMarker: marker }, '', window.location.href);

    const removeSentinel = (after) => {
      active.current = false;
      leaving.current = true;
      const finish = () => {
        window.removeEventListener('popstate', finish);
        after?.();
      };
      window.addEventListener('popstate', finish);
      window.history.back();
    };

    const beforeUnload = (event) => {
      if (!active.current) return;
      event.preventDefault();
      event.returnValue = message;
    };

    const onClick = (event) => {
      if (!active.current || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = event.target.closest?.('a[href]');
      if (!anchor || anchor.target === '_blank' || anchor.hasAttribute('download')) return;
      const target = new URL(anchor.href, window.location.href);
      if (target.origin !== window.location.origin || target.href === window.location.href) return;
      event.preventDefault();
      event.stopPropagation();
      if (window.confirm(message)) removeSentinel(() => window.location.assign(target.href));
    };

    const onPopState = () => {
      if (!active.current || leaving.current) return;
      if (window.confirm(message)) {
        active.current = false;
        leaving.current = true;
        window.history.back();
      } else {
        window.history.forward();
      }
    };

    window.addEventListener('beforeunload', beforeUnload);
    window.addEventListener('popstate', onPopState);
    document.addEventListener('click', onClick, true);
    return () => {
      window.removeEventListener('beforeunload', beforeUnload);
      window.removeEventListener('popstate', onPopState);
      document.removeEventListener('click', onClick, true);
      if (active.current && window.history.state?.gsUnsavedMarker === marker) {
        active.current = false;
        window.history.back();
      }
    };
  }, [when, message]);
}
