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
            error_type,
            error_code,
            modal_url,
            success_event,
            retry_callback,
            error_message
        } = drawerData;

        // Store retry callback if provided
        if (retry_callback) {
            const callbackKey = `${error_type}.${error_code}`;
            this.retryCallbacks.set(callbackKey, retry_callback);
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
        for (const [key, callback] of this.retryCallbacks.entries()) {
            if (key.includes(successEvent.replace(/([A-Z])/g, '_$1').toLowerCase())) {
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