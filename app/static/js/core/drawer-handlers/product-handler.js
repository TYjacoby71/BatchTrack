
/**
 * Product Error Drawer Handler
 * Handles all product-related drawer errors
 */
export class ProductDrawerHandler {
    constructor(drawerProtocol) {
        this.drawerProtocol = drawerProtocol;
    }

    async handleError(errorCode, errorData) {
        switch (errorCode) {
            case 'SKU_CONFLICT':
                return this.handleSkuConflict(errorData);
            
            case 'PRICING_ERROR':
                return this.handlePricingError(errorData);
            
            default:
                console.warn(`🔧 PRODUCT DRAWER: Unhandled error code: ${errorCode}`);
                return false;
        }
    }

    async handleSkuConflict(errorData) {
        const params = new URLSearchParams({
            conflicting_sku: errorData.conflicting_sku
        });
        
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/product/sku-conflict-modal/' + errorData.product_id + '?' + params,
            'skuConflictResolved'
        );
    }

    async handlePricingError(errorData) {
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/product/pricing-error-modal/' + errorData.product_id,
            'pricingFixed'
        );
    }
}
