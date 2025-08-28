/**
 * Universal Wall of Drawers Protocol
 * Handles ANY type of error across the entire application using modular handlers
 */
import { ConversionDrawerHandler } from './drawer-handlers/conversion-handler.js';
import { RecipeDrawerHandler } from './drawer-handlers/recipe-handler.js';
import { BatchDrawerHandler } from './drawer-handlers/batch-handler.js';
import { InventoryDrawerHandler } from './drawer-handlers/inventory-handler.js';
import { ProductDrawerHandler } from './drawer-handlers/product-handler.js';

class DrawerProtocol {
    constructor() {
        this.activeDrawers = new Set();
        this.retryCallbacks = new Map();

        // Initialize domain-specific handlers
        this.handlers = {
            conversion: new ConversionDrawerHandler(this),
            recipe: new RecipeDrawerHandler(this),
            batch: new BatchDrawerHandler(this),
            inventory: new InventoryDrawerHandler(this),
            product: new ProductDrawerHandler(this)
        };
    }

    /**
     * Handle any error that needs a drawer solution
     * @param {string} errorType - Type of error (conversion, recipe, batch, inventory, product)
     * @param {string} errorCode - Specific error code
     * @param {Object} errorData - Error context data
     * @param {Function} retryCallback - Function to call after fix
     */
    async handleError(errorType, errorCode, errorData, retryCallback = null) {
        console.log(`🔧 DRAWER PROTOCOL: Handling ${errorType}.${errorCode}`, errorData);

        // Only handle errors that explicitly require drawers
        if (!errorData.requires_drawer && !this.isKnownDrawerError(errorType, errorCode)) {
            console.log(`🔧 DRAWER PROTOCOL: Error ${errorType}.${errorCode} does not require drawer`);
            return false;
        }

        if (retryCallback) {
            this.retryCallbacks.set(`${errorType}.${errorCode}`, retryCallback);
        }

        // Delegate to appropriate handler
        const handler = this.handlers[errorType];
        if (handler) {
            return handler.handleError(errorCode, errorData);
        } else {
            console.error(`🚨 DRAWER PROTOCOL: Unknown error type: ${errorType}`);
            return false;
        }
    }

    /**
     * Check if this is a known drawer-requiring error
     */
    isKnownDrawerError(errorType, errorCode) {
        const drawerErrors = {
            'conversion': ['MISSING_DENSITY', 'MISSING_CUSTOM_MAPPING', 'UNSUPPORTED_CONVERSION', 'UNKNOWN_SOURCE_UNIT', 'UNKNOWN_TARGET_UNIT'],
            'recipe': ['MISSING_INGREDIENT', 'SCALING_VALIDATION', 'INVALID_YIELD'],
            'batch': ['CONTAINER_SHORTAGE', 'STUCK_BATCH', 'VALIDATION_FAILED'],
            'inventory': ['STOCK_SHORTAGE', 'LOW_STOCK_ALERT', 'LOT_EXPIRED', 'FIFO_CONFLICT'],
            'product': ['SKU_CONFLICT', 'VARIANT_ERROR', 'PRICING_ERROR']
        };

        return drawerErrors[errorType]?.includes(errorCode) || false;
    }

    async openModal(url, successEvent) {
        try {
            const response = await fetch(url);
            const data = await response.json();

            if (data.success) {
                // Inject modal HTML
                document.body.insertAdjacentHTML('beforeend', data.modal_html);

                // Get modal element (assumes consistent naming)
                const modalElement = document.body.lastElementChild.querySelector('.modal');
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
     * Universal retry mechanism
     * @param {string} operationType - Type of operation to retry
     * @param {Object} operationData - Data needed for retry
     */
    async retryOperation(operationType, operationData) {
        try {
            const response = await fetch('/api/drawer-actions/retry-operation', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    operation_type: operationType,
                    operation_data: operationData
                })
            });

            const result = await response.json();
            console.log(`🔧 DRAWER PROTOCOL: Retry result for ${operationType}:`, result);
            return result;

        } catch (error) {
            console.error(`🚨 DRAWER PROTOCOL: Retry failed for ${operationType}:`, error);
            return { success: false, error: error.message };
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