// Global Drawer Interceptor
// Wrap window.fetch to automatically open drawers when a response contains drawer_payload
(function() {
    if (window.__drawerInterceptorInstalled) return;
    window.__drawerInterceptorInstalled = true;

    const originalFetch = window.fetch.bind(window);
    const activeCorrelations = new Set();

    window.fetch = async function(input, init) {
        const response = await originalFetch(input, init);

        try {
            // Clone so we can read the body without consuming the original
            const clone = response.clone();
            const contentType = clone.headers.get('content-type') || '';
            if (!contentType.includes('application/json')) {
                return response;
            }

            const data = await clone.json();
            const payload = data && (data.drawer_payload || (data.data && data.data.drawer_payload));

            if (payload && window.drawerProtocol) {
                const correlationId = payload.correlation_id || `${payload.error_type || 'generic'}:${payload.error_code || 'unknown'}`;
                if (!activeCorrelations.has(correlationId)) {
                    activeCorrelations.add(correlationId);
                    const detail = {
                        ...payload,
                        // Default retry falls back to reloading current page section if none provided
                        retry_callback: payload.retry_callback || null
                    };
                    window.dispatchEvent(new CustomEvent('openDrawer', { detail }));
                    // Clean up the correlation after some time to allow re-open if needed later
                    setTimeout(() => activeCorrelations.delete(correlationId), 60_000);
                }
            }
        } catch (e) {
            // Non-fatal: logging for diagnostics
            console.warn('DrawerInterceptor: failed to inspect response', e);
        }

        return response;
    };
})();

