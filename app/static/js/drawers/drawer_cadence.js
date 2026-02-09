(function () {
  const isAuthenticated = typeof window !== 'undefined' && Boolean(window.__IS_AUTHENTICATED__);
  if (!isAuthenticated) {
    return;
  }

  const AUTH_PAGES = ['/auth/login', '/auth/signup', '/auth/oauth', '/auth/callback'];

  function shouldSkipCadence() {
    const path = window.location.pathname;
    return AUTH_PAGES.some((prefix) => path.startsWith(prefix));
  }

  async function pingDrawerCheck(include) {
    try {
      const query = include ? `?include=${encodeURIComponent(include)}` : '';
      const response = await fetch(`/api/drawers/check${query}`);
      if (!response.ok) {
        // Skip logging auth failures—they are expected on public routes
        if (response.status !== 401) {
          console.warn('DrawerCadence: check failed', response.status);
        }
        return;
      }
      // Consume the body so fetch callers can reuse the response if needed.
      await response.json().catch(() => ({}));
    } catch (err) {
      console.warn('DrawerCadence: request error', err);
    }
  }

  function runRetentionCheck() {
    pingDrawerCheck('retention');
  }

  function runGlobalLinkCheck() {
    const storageKeyBase = 'drawerCadence:global_link:lastCheck';
    const storageKey = (window.BT_STORAGE && typeof window.BT_STORAGE.key === 'function')
      ? window.BT_STORAGE.key(storageKeyBase)
      : storageKeyBase;
    const now = Date.now();
    const oneWeek = 7 * 24 * 60 * 60 * 1000;

    try {
      const lastCheck = Number(localStorage.getItem(storageKey) || 0);
      if (lastCheck && now - lastCheck < oneWeek) {
        return;
      }
      localStorage.setItem(storageKey, String(now));
    } catch (err) {
      console.warn('DrawerCadence: unable to store cadence window', err);
    }

    pingDrawerCheck('global_link');
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (shouldSkipCadence()) {
      return;
    }

    runRetentionCheck();
    runGlobalLinkCheck();
  });
})();
