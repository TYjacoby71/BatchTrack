(function(){
  async function checkAndOpenGlobalLinkDrawer() {
    try {
      const res = await fetch('/global-link/api/check');
      const data = await res.json();
      if (data && data.needs_drawer && data.drawer_payload && window.drawerProtocol) {
        // Use universal protocol
        window.dispatchEvent(new CustomEvent('openDrawer', { detail: data.drawer_payload }));
      }
    } catch (e) {
      console.warn('GlobalLinkDrawer: check failed', e);
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    // Weekly cadence trigger: run on first page load daily, with cache gate to once/week
    try {
      const key = 'gl:last_check';
      const last = localStorage.getItem(key);
      const now = Date.now();
      const oneWeekMs = 7 * 24 * 60 * 60 * 1000;
      if (!last || (now - Number(last)) > oneWeekMs) {
        localStorage.setItem(key, String(now));
        checkAndOpenGlobalLinkDrawer();
      }
    } catch (e) {
      // Fallback: still try once
      checkAndOpenGlobalLinkDrawer();
    }
  });
})();

