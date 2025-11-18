/**
 * DrawerProtocol: universal handler for drawer payloads.
 *
 * Responsibilities:
 *  - Listen for `openDrawer` events.
 *  - Fetch and render drawer modals.
 *  - Store retry callbacks and execute them after success events.
 *  - Support redirect-only payloads.
 */
class DrawerProtocol {
    constructor() {
        this.activeDrawers = new Set();
        this.retryCallbacks = new Map();
        this.debugEnabled = window.location.search.includes('drawerDebug=true');

        window.addEventListener('openDrawer', (event) => {
            this.handleDrawerRequest(event.detail || {});
        });
    }

    log(...args) {
        if (this.debugEnabled) {
            console.debug('[DrawerProtocol]', ...args);
        }
    }

    handleDrawerRequest(detail) {
        if (!detail) {
            return;
        }

        this.log('Handling drawer request', detail);
        this.storeRetry(detail);

        if (detail.redirect_url) {
            window.open(detail.redirect_url, '_blank');
            return;
        }

        if (!detail.modal_url) {
            if (detail.error_message) {
                alert(detail.error_message);
            }
            return;
        }

        this.openModal(detail.modal_url, detail.success_event, detail);
    }

    storeRetry(detail) {
        const successEvent = detail.success_event || detail.error_type || 'drawer';
        const key = this.buildRetryKey(successEvent, detail);

        if (typeof detail.retry_callback === 'function') {
            this.retryCallbacks.set(key, detail.retry_callback);
            return;
        }

        if (detail.retry && detail.retry.operation) {
            this.retryCallbacks.set(key, () => {
                this.executeRetryOperation(detail.retry.operation, detail.retry.data || {});
            });
            return;
        }

        if (detail.retry_operation && detail.retry_data) {
            this.retryCallbacks.set(key, () => {
                this.executeRetryOperation(detail.retry_operation, detail.retry_data);
            });
        }
    }

    buildRetryKey(successEvent, detail) {
        return `${successEvent || 'drawer'}.${detail.error_code || 'generic'}.${detail.correlation_id || 'na'}`;
    }

    async openModal(url, successEvent, originalDetail) {
        try {
            this.clearExistingDrawer();

            const response = await fetch(url);
            const data = await response.json();

            if (!data.success) {
                console.error('DrawerProtocol: Failed to load modal', data.error);
                return false;
            }

            const wrapper = document.createElement('div');
            wrapper.className = 'drawer-wrapper';
            wrapper.innerHTML = data.modal_html;
            document.body.appendChild(wrapper);

            this.rehydrateScripts(wrapper);

            const modalElement = wrapper.querySelector('.modal');
            if (!modalElement) {
                wrapper.remove();
                return false;
            }

            const modal = new bootstrap.Modal(modalElement);
            if (modalElement.id) {
                this.activeDrawers.add(modalElement.id);
            }

            if (successEvent) {
                window.addEventListener(
                    successEvent,
                    (event) => this.handleSuccess(successEvent, event.detail),
                    { once: true },
                );
            }

            modalElement.addEventListener(
                'hidden.bs.modal',
                () => {
                    if (modalElement.id) {
                        this.activeDrawers.delete(modalElement.id);
                    }
                    wrapper.remove();
                },
                { once: true },
            );

            modal.show();
            this.emitAnalyticsEvent('open', originalDetail);
            return true;
        } catch (error) {
            console.error('DrawerProtocol: Error opening modal', error);
            return false;
        }
    }

    clearExistingDrawer() {
        const wrapper = document.querySelector('.drawer-wrapper');
        if (wrapper) {
            wrapper.remove();
        }
    }

    rehydrateScripts(root) {
        const scripts = root.querySelectorAll('script');
        console.log('🔧 DRAWER PROTOCOL: Found', scripts.length, 'scripts to rehydrate');
        
        scripts.forEach((script, index) => {
            console.log('🔧 DRAWER PROTOCOL: Rehydrating script', index, 'with content length:', script.textContent?.length);
            console.log('🔧 DRAWER PROTOCOL: Script content preview:', script.textContent?.substring(0, 200));
            
            const replacement = document.createElement('script');
            for (const { name, value } of Array.from(script.attributes)) {
                replacement.setAttribute(name, value);
            }
            replacement.textContent = script.textContent;
            
            try {
                script.replaceWith(replacement);
                console.log('🔧 DRAWER PROTOCOL: Successfully rehydrated script', index);
            } catch (error) {
                console.error('🔧 DRAWER PROTOCOL: Error rehydrating script', index, error);
                console.log('🔧 DRAWER PROTOCOL: Problematic script content:', script.textContent);
            }
        });
    }

    handleSuccess(successEvent, eventDetail) {
        const prefix = `${successEvent}.`;

        for (const [key, callback] of this.retryCallbacks.entries()) {
            if (key.startsWith(prefix) || key.includes(successEvent)) {
                this.invokeRetryCallback(key, callback, eventDetail);
                return;
            }
        }

        const fallback = this.retryCallbacks.entries().next();
        if (!fallback.done) {
            const [key, callback] = fallback.value;
            this.invokeRetryCallback(key, callback, eventDetail);
        }
    }

    invokeRetryCallback(key, callback, detail) {
        try {
            callback(detail);
        } catch (err) {
            console.error('DrawerProtocol: Retry callback failed', err);
        } finally {
            this.retryCallbacks.delete(key);
        }
    }

    async executeRetryOperation(operation, data) {
        this.log('Executing retry operation', operation, data);

        switch (operation) {
            case 'stock_check':
                if (window.stockChecker && typeof window.stockChecker.performStockCheck === 'function') {
                    window.stockChecker.performStockCheck();
                } else {
                    console.warn('DrawerProtocol: Stock checker not available for retry');
                }
                break;

            case 'retention.refresh':
                window.location.reload();
                break;

            default:
                console.warn('DrawerProtocol: Unknown retry operation', operation);
        }
    }

    emitAnalyticsEvent(action, detail) {
        try {
            window.dispatchEvent(
                new CustomEvent('drawer.analytics', {
                    detail: {
                        action,
                        error_type: detail?.error_type,
                        error_code: detail?.error_code,
                        correlation_id: detail?.correlation_id,
                    },
                }),
            );
        } catch (err) {
            this.log('Analytics dispatch failed', err);
        }
    }

    hasActiveDrawers() {
        return this.activeDrawers.size > 0;
    }

    getActiveDrawerCount() {
        return this.activeDrawers.size;
    }
}

if (!window.drawerProtocol) {
    window.drawerProtocol = new DrawerProtocol();
}

export { DrawerProtocol };