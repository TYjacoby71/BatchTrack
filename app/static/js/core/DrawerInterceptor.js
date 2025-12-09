// DrawerInterceptor: Fetch response watcher that auto-opens drawers
//
// - Wraps window.fetch; inspects JSON responses for drawer_payload
// - If payload found, dispatches 'openDrawer' to DrawerProtocol with deduplication
// - Uses a correlation set and small cache to prevent duplicate opens
// - Transparent pass-through for non-JSON or responses without drawer_payload
//
// Expected server response:
//   { drawer_payload: { modal_url, error_type, error_code, success_event, correlation_id?, retry_callback? } }
//
// Global Drawer Interceptor
// Wrap window.fetch to automatically open drawers when a response contains drawer_payload

import { appCache } from './CacheManager.js';

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

            // Handle timer completion responses (minimal logging)
            const requestUrl = typeof input === 'string' ? input : input.url;

            if (payload && window.drawerProtocol) {
                const correlationId = payload.correlation_id || `${payload.error_type || 'generic'}:${payload.error_code || 'unknown'}`;

                const cacheKey = `drawer:${payload.error_type}:${payload.error_code}:${payload.modal_url}`;
                const cached = appCache.get(cacheKey);
                if (cached) {
                    return response;
                }

                if (!activeCorrelations.has(correlationId)) {
                    activeCorrelations.add(correlationId);
                    appCache.set(cacheKey, true, 30000);

                    const detail = {
                        ...payload,
                        // Default retry falls back to reloading current page section if none provided
                        retry_callback: payload.retry_callback || null
                    };
                    window.dispatchEvent(new CustomEvent('openDrawer', { detail }));
                    // Clean up the correlation after some time to allow re-open if needed later
                    setTimeout(() => {
                        activeCorrelations.delete(correlationId);
                        appCache.delete(cacheKey);
                    }, 60_000);
                }
            }
        } catch (e) {
            // Non-fatal: logging for diagnostics
            console.warn('DrawerInterceptor: failed to inspect response', e);
        }

        return response;
    };
})();