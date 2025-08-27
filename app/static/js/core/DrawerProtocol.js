
/**
 * Universal Wall of Drawers Protocol
 * Handles ANY type of error across the entire application
 */
class DrawerProtocol {
    constructor() {
        this.activeDrawers = new Set();
        this.retryCallbacks = new Map();
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

        if (retryCallback) {
            this.retryCallbacks.set(`${errorType}.${errorCode}`, retryCallback);
        }

        switch (errorType) {
            case 'conversion':
                return this.handleConversionError(errorCode, errorData);
            case 'recipe':
                return this.handleRecipeError(errorCode, errorData);
            case 'batch':
                return this.handleBatchError(errorCode, errorData);
            case 'inventory':
                return this.handleInventoryError(errorCode, errorData);
            case 'product':
                return this.handleProductError(errorCode, errorData);
            default:
                console.error(`🚨 DRAWER PROTOCOL: Unknown error type: ${errorType}`);
                return false;
        }
    }

    async handleConversionError(errorCode, errorData) {
        switch (errorCode) {
            case 'MISSING_DENSITY':
                return this.openModal('/api/drawer-actions/conversion/density-modal/' + errorData.ingredient_id, 'densityUpdated');
            case 'MISSING_CUSTOM_MAPPING':
                const params = new URLSearchParams({
                    from_unit: errorData.from_unit,
                    to_unit: errorData.to_unit
                });
                return this.openModal('/api/drawer-actions/conversion/unit-mapping-modal?' + params, 'unitMappingCreated');
            case 'UNKNOWN_SOURCE_UNIT':
            case 'UNKNOWN_TARGET_UNIT':
                window.open('/conversion/units', '_blank');
                return true;
        }
    }

    async handleRecipeError(errorCode, errorData) {
        switch (errorCode) {
            case 'MISSING_INGREDIENT':
                return this.openModal('/api/drawer-actions/recipe/missing-ingredient-modal/' + errorData.recipe_id, 'ingredientAdded');
            case 'SCALING_VALIDATION':
                const params = new URLSearchParams({
                    scale: errorData.scale,
                    error_details: errorData.error_details
                });
                return this.openModal('/api/drawer-actions/recipe/scaling-validation-modal/' + errorData.recipe_id + '?' + params, 'recipeScalingFixed');
            case 'INVALID_YIELD':
                return this.openModal('/api/drawer-actions/recipe/yield-validation-modal/' + errorData.recipe_id, 'recipeYieldFixed');
        }
    }

    async handleBatchError(errorCode, errorData) {
        switch (errorCode) {
            case 'CONTAINER_SHORTAGE':
                return this.openModal('/api/drawer-actions/batch/container-shortage-modal/' + errorData.batch_id, 'containersUpdated');
            case 'STUCK_BATCH':
                return this.openModal('/api/drawer-actions/batch/stuck-batch-modal/' + errorData.batch_id, 'batchUnstuck');
            case 'VALIDATION_FAILED':
                return this.openModal('/api/drawer-actions/batch/validation-error-modal/' + errorData.batch_id, 'batchValidationFixed');
        }
    }

    async handleInventoryError(errorCode, errorData) {
        switch (errorCode) {
            case 'STOCK_SHORTAGE':
                const params = new URLSearchParams({
                    required_amount: errorData.required_amount
                });
                return this.openModal('/api/drawer-actions/inventory/stock-shortage-modal/' + errorData.item_id + '?' + params, 'inventoryRestocked');
            case 'LOT_EXPIRED':
                return this.openModal('/api/drawer-actions/inventory/expired-lot-modal/' + errorData.lot_id, 'expiredLotHandled');
            case 'FIFO_CONFLICT':
                return this.openModal('/api/drawer-actions/inventory/fifo-conflict-modal/' + errorData.item_id, 'fifoConflictResolved');
        }
    }

    async handleProductError(errorCode, errorData) {
        switch (errorCode) {
            case 'SKU_CONFLICT':
                const params = new URLSearchParams({
                    conflicting_sku: errorData.conflicting_sku
                });
                return this.openModal('/api/drawer-actions/product/sku-conflict-modal/' + errorData.product_id + '?' + params, 'skuConflictResolved');
            case 'PRICING_ERROR':
                return this.openModal('/api/drawer-actions/product/pricing-error-modal/' + errorData.product_id, 'pricingFixed');
        }
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
