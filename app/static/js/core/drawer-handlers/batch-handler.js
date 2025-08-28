
/**
 * Batch Error Drawer Handler
 * Handles all batch-related drawer errors
 */
export class BatchDrawerHandler {
    constructor(drawerProtocol) {
        this.drawerProtocol = drawerProtocol;
    }

    async handleError(errorCode, errorData) {
        switch (errorCode) {
            case 'CONTAINER_SHORTAGE':
                return this.handleContainerShortage(errorData);
            
            case 'STUCK_BATCH':
                return this.handleStuckBatch(errorData);
            
            case 'VALIDATION_FAILED':
                return this.handleValidationFailed(errorData);
            
            default:
                console.warn(`🔧 BATCH DRAWER: Unhandled error code: ${errorCode}`);
                return false;
        }
    }

    async handleContainerShortage(errorData) {
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/batch/container-shortage-modal/' + errorData.batch_id,
            'containersUpdated'
        );
    }

    async handleStuckBatch(errorData) {
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/batch/stuck-batch-modal/' + errorData.batch_id,
            'batchUnstuck'
        );
    }

    async handleValidationFailed(errorData) {
        return this.drawerProtocol.openModal(
            '/api/drawer-actions/batch/validation-error-modal/' + errorData.batch_id,
            'batchValidationFixed'
        );
    }
}
