/**
 * Universal Drawer Protocol
 * Simple listener that handles ANY drawer request from ANY service
 */
class DrawerProtocol {
    constructor() {
        this.activeDrawers = new Set();
        this.retryCallbacks = new Map();

        // Listen for universal drawer events
        window.addEventListener('openDrawer', (event) => {
            this.handleDrawerRequest(event.detail);
        });

        console.log('🔧 DRAWER PROTOCOL: Universal listener initialized');
    }

    /**
     * Handle any drawer request from any service
     * @param {Object} drawerData - Contains all info needed to open appropriate drawer
     */
    async handleDrawerRequest(drawerData) {
        console.log('🔧 DRAWER PROTOCOL: Drawer request received', drawerData);

        const {
            version,
            error_type,
            error_code,
            modal_url,
            redirect_url,
            success_event,
            retry_callback,
            retry,
            retry_operation,
            retry_data,
            error_message,
            correlation_id
        } = drawerData;

        // Store retry callback if provided
        if (retry_callback) {
            const callbackKey = `${success_event || error_type}.${error_code || 'generic'}.${correlation_id || 'na'}`;
            this.retryCallbacks.set(callbackKey, retry_callback);
        } else if (retry && retry.operation && retry.data) {
            const callbackKey = `${success_event || error_type}.${error_code || 'generic'}.${correlation_id || 'na'}`;
            this.retryCallbacks.set(callbackKey, () => {
                this.executeRetryOperation(retry.operation, retry.data);
            });
        } else if (retry_operation && retry_data) {
            const callbackKey = `${success_event || error_type}.${error_code || 'generic'}.${correlation_id || 'na'}`;
            this.retryCallbacks.set(callbackKey, () => {
                this.executeRetryOperation(retry_operation, retry_data);
            });
        }

        // Handle redirect (like unit manager)
        if (redirect_url) {
            console.log('🔧 DRAWER PROTOCOL: Redirecting to', redirect_url);
            window.open(redirect_url, '_blank');
            return true;
        }

        // Show user-friendly error message if no modal
        if (!modal_url) {
            console.warn('🔧 DRAWER PROTOCOL: No modal URL provided, showing alert');
            alert(error_message || 'An error occurred that requires attention');
            return false;
        }

        // Open the modal
        return this.openModal(modal_url, success_event);
    }

    /**
     * Execute retry operation based on backend-provided instructions
     */
    async executeRetryOperation(operation, data) {
        console.log(`🔧 DRAWER PROTOCOL: Executing retry operation: ${operation}`, data);
        
        switch (operation) {
            case 'stock_check':
                // Trigger stock check retry
                if (window.stockChecker && window.stockChecker.performStockCheck) {
                    window.stockChecker.performStockCheck();
                } else {
                    console.warn('🔧 DRAWER PROTOCOL: Stock checker not available for retry');
                }
                break;
            
            default:
                console.warn(`🔧 DRAWER PROTOCOL: Unknown retry operation: ${operation}`);
        }
    }

    async openModal(url, successEvent) {
        try {
            console.log(`🔧 DRAWER PROTOCOL: Opening modal from ${url}`);

            const response = await fetch(url);
            const data = await response.json();

            if (data.success) {
                // Inject modal HTML
                document.body.insertAdjacentHTML('beforeend', data.modal_html);

                // Get modal element (assumes consistent naming)
                const modalElement = document.body.lastElementChild.querySelector('.modal');

                if (!modalElement) {
                    console.error('🚨 DRAWER PROTOCOL: No modal element found in response');
                    return false;
                }

                const modal = new bootstrap.Modal(modalElement);

                // Track active drawer
                this.activeDrawers.add(modalElement.id);

                // Show modal
                modal.show();

                // Set up success listener
                if (successEvent) {
                    window.addEventListener(successEvent, (event) => {
                        console.log(`🔧 DRAWER PROTOCOL: ${successEvent} triggered`, event.detail);
                        this.handleSuccess(successEvent, event.detail);
                    }, { once: true });
                }

                // Clean up on close
                modalElement.addEventListener('hidden.bs.modal', () => {
                    this.activeDrawers.delete(modalElement.id);
                    modalElement.remove();
                }, { once: true });

                return true;
            } else {
                console.error('🚨 DRAWER PROTOCOL: Failed to load modal:', data.error);
                return false;
            }
        } catch (error) {
            console.error('🚨 DRAWER PROTOCOL: Error opening modal:', error);
            return false;
        }
    }

    handleSuccess(successEvent, eventDetail) {
        // Find and execute retry callback
        // Prefer exact key match using the event name first
        const exactKeyPrefix = `${successEvent}.`;
        if (this.retryCallbacks.has(exactKey)) {
            const cb = this.retryCallbacks.get(exactKey);
            console.log(`🔧 DRAWER PROTOCOL: Executing retry for ${exactKey}`);
            cb(eventDetail);
            this.retryCallbacks.delete(exactKey);
            return;
        }

        // Fallback: search by prefix of the event or error_type
        for (const [key, callback] of this.retryCallbacks.entries()) {
            if (key.startsWith(exactKeyPrefix) || key.includes(successEvent)) {
                console.log(`🔧 DRAWER PROTOCOL: Executing retry for ${key}`);
                callback(eventDetail);
                this.retryCallbacks.delete(key);
                break;
            }
        }
    }

    /**
     * Check if we have active drawers
     */
    hasActiveDrawers() {
        return this.activeDrawers.size > 0;
    }

    /**
     * Get count of active drawers
     */
    getActiveDrawerCount() {
        return this.activeDrawers.size;
    }
}

// Global instance
window.drawerProtocol = new DrawerProtocol();

// Export for modules
export { DrawerProtocol };