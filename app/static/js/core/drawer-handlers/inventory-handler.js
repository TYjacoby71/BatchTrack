
/**
 * Inventory Error Drawer Handler
 * Handles all inventory-related drawer errors
 */
export class InventoryDrawerHandler {
    constructor(drawerProtocol) {
        this.drawerProtocol = drawerProtocol;
    }

    async handleError(errorCode, errorData) {
        switch (errorCode) {
            case 'STOCK_SHORTAGE':
                return this.handleStockShortage(errorData);
            
            case 'LOT_EXPIRED':
                return this.handleExpiredLot(errorData);
            
            case 'FIFO_CONFLICT':
                return this.handleFifoConflict(errorData);
            
            default:
                console.warn(`🔧 INVENTORY DRAWER: Unhandled error code: ${errorCode}`);
                return false;
        }
    }

    async handleStockShortage(errorData) {
        const params = new URLSearchParams({
            required_amount: errorData.required_amount
        });
        
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/inventory/stock-shortage-modal/' + errorData.item_id + '?' + params,
            'inventoryRestocked'
        );
    }

    async handleExpiredLot(errorData) {
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/inventory/expired-lot-modal/' + errorData.lot_id,
            'expiredLotHandled'
        );
    }

    async handleFifoConflict(errorData) {
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/inventory/fifo-conflict-modal/' + errorData.item_id,
            'fifoConflictResolved'
        );
    }
}
