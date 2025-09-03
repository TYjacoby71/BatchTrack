// Global Drawer Interceptor
// Wrap window.fetch to automatically open drawers when a response contains drawer_payload
(function() {
    if (window.__drawerInterceptorInstalled) return;
    window.__drawerInterceptorInstalled = true;

    const originalFetch = window.fetch.bind(window);
    const activeCorrelations = new Set();
    const drawerCache = new Map(); // Cache drawer requests

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
            console.log('🔍 DRAWER INTERCEPTOR: Inspecting response data:', data);
            const payload = data && (data.drawer_payload || (data.data && data.data.drawer_payload));
            console.log('🔍 DRAWER INTERCEPTOR: Extracted drawer payload:', payload);

            if (payload && window.drawerProtocol) {
                console.log('🔍 DRAWER INTERCEPTOR: Found drawer payload, dispatching to protocol');
                const correlationId = payload.correlation_id || `${payload.error_type || 'generic'}:${payload.error_code || 'unknown'}`;
                console.log('🔍 DRAWER INTERCEPTOR: Correlation ID:', correlationId);
                console.log('🔍 DRAWER INTERCEPTOR: Active correlations:', Array.from(activeCorrelations));
                
                const cacheKey = `${payload.error_type}:${payload.error_code}:${payload.modal_url}`;
                const now = Date.now();
                
                // Check cache first (cache for 30 seconds)
                if (drawerCache.has(cacheKey)) {
                    const cached = drawerCache.get(cacheKey);
                    if (now - cached.timestamp < 30000) {
                        console.log('🔍 DRAWER INTERCEPTOR: Using cached drawer request');
                        return response;
                    }
                }
                
                if (!activeCorrelations.has(correlationId)) {
                    console.log('🔍 DRAWER INTERCEPTOR: New correlation, dispatching drawer event');
                    activeCorrelations.add(correlationId);
                    drawerCache.set(cacheKey, { timestamp: now });
                    
                    const detail = {
                        ...payload,
                        // Default retry falls back to reloading current page section if none provided
                        retry_callback: payload.retry_callback || null
                    };
                    console.log('🔍 DRAWER INTERCEPTOR: Dispatching openDrawer event with detail:', detail);
                    window.dispatchEvent(new CustomEvent('openDrawer', { detail }));
                    // Clean up the correlation after some time to allow re-open if needed later
                    setTimeout(() => {
                        activeCorrelations.delete(correlationId);
                        drawerCache.delete(cacheKey);
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

