/**
 * Retention Drawer Service
 *
 * Orchestrates the blocking retention notice drawer:
 * - On app load, checks /retention/api/check for at-risk items
 * - If needed, triggers Universal DrawerProtocol to open /retention/api/modal
 * - Modal offers: Upgrade, Buy Storage, Export (CSV/JSON), Acknowledge
 * - Acknowledge queues items for deletion (retention + 15d) via /retention/api/acknowledge
 * - Nothing is deleted until user acknowledges; only non batch-linked recipes are included
 */
(function() {
  // Helper function to initialize the retention drawer check
  function initializeRetentionDrawer() {
    async function checkAndOpenRetentionDrawer() {
      try {
        if (!window.drawerProtocol) return;
        const res = await fetch('/retention/api/check');
        if (!res.ok) {
          // Handle non-OK responses, potentially based on status code
          if (res.status === 401) {
            console.log('User not authenticated, skipping retention drawer check.');
            return;
          }
          console.warn('Retention drawer check returned an error:', res.status, await res.text());
          return;
        }
        const data = await res.json();
        if (data.needs_drawer) {
          window.dispatchEvent(new CustomEvent('openDrawer', {
            detail: {
              modal_url: '/retention/api/modal',
              success_event: 'retention.acknowledged',
              error_type: 'retention_notice'
            }
          }));
        }
      } catch (e) {
        // Only log actual errors, not expected auth failures
        if (e.status && e.status !== 401) {
          console.warn('Retention drawer check failed:', e.status, e.message);
        }
        // Silently skip for auth failures - this is expected on public pages
        return;
      }
    }
    checkAndOpenRetentionDrawer();
  }

  document.addEventListener('DOMContentLoaded', function() {
    // Removed debug noise - only log actual problems

    // Skip retention drawer on authentication pages
    const authPages = ['/auth/login', '/auth/signup', '/auth/oauth', '/auth/callback'];
    const currentPath = window.location.pathname;

    if (authPages.some(page => currentPath.startsWith(page))) {
        return; // Skip retention drawer on auth pages
    }

    // Initialize retention drawer check only for authenticated pages
    initializeRetentionDrawer();
  });
})();