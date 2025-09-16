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
  async function checkAndOpenRetentionDrawer() {
    try {
      if (!window.drawerProtocol) return;
      const res = await fetch('/retention/api/check');
      if (!res.ok) return;
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
      console.warn('Retention drawer check failed', e);
    }
  }

  document.addEventListener('DOMContentLoaded', checkAndOpenRetentionDrawer);
})();

