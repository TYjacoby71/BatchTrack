// DrawerPayloadHandler: explicit helper for opening drawers from API responses.
//
// This keeps drawer behavior opt-in at callsites instead of monkey-patching fetch.

import { appCache } from './CacheManager.js';

function normalizePayload(responseData) {
    return responseData && (responseData.drawer_payload || (responseData.data && responseData.data.drawer_payload));
}

function dispatchDrawerPayload(payload) {
    if (!payload || !window.drawerProtocol) {
        return false;
    }

    const correlationId = payload.correlation_id || `${payload.error_type || 'generic'}:${payload.error_code || 'unknown'}`;
    const destination = payload.modal_url || payload.redirect_url || 'none';
    const cacheKey = `drawer:${payload.error_type || 'generic'}:${payload.error_code || 'unknown'}:${destination}`;

    if (appCache.get(cacheKey)) {
        return false;
    }

    appCache.set(cacheKey, true, 30000);
    window.dispatchEvent(new CustomEvent('openDrawer', { detail: payload }));
    setTimeout(() => appCache.delete(cacheKey), 60000);
    return correlationId.length > 0;
}

function handleDrawerPayloadFromResponse(responseData) {
    const payload = normalizePayload(responseData);
    if (!payload) {
        return false;
    }
    return dispatchDrawerPayload(payload);
}

window.handleDrawerPayloadFromResponse = handleDrawerPayloadFromResponse;
window.dispatchDrawerPayload = dispatchDrawerPayload;

export { dispatchDrawerPayload, handleDrawerPayloadFromResponse };
