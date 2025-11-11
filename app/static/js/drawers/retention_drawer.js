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
        console.log('Retention drawer check failed', e);
        // If it's a 401 error, user might not be authenticated - don't retry
        if (e.status === 401) {
          console.log('User not authenticated, skipping retention drawer');
          return;
        }
        // Silently fail for other errors - don't show errors for retention checks
      }
    }
    checkAndOpenRetentionDrawer();
  }

  document.addEventListener('DOMContentLoaded', function() {
    console.log('🔧 DRAWER PROTOCOL: Universal listener initialized');
    console.log('Page loaded:', window.location.pathname);

    // Skip retention drawer on authentication pages
    const authPages = ['/auth/login', '/auth/signup', '/auth/oauth', '/auth/callback'];
    const currentPath = window.location.pathname;

    if (authPages.some(page => currentPath.startsWith(page))) {
        console.log('Skipping retention drawer on auth page:', currentPath);
        return;
    }

    // Initialize retention drawer check only for authenticated pages
    initializeRetentionDrawer();
  });
})();