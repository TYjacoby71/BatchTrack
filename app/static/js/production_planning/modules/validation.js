// Form Validation Module
export class ValidationManager {
    constructor(mainManager) {
        this.main = mainManager;
    }

    bindEvents() {
        // No specific events to bind for validation
    }

    updateValidation() {
        const validationStatus = document.getElementById('validationStatus');
        const batchActionsCard = document.getElementById('batchActionsCard');
        const startBatchBtn = document.getElementById('startBatchBtn');
        const startBatchText = document.getElementById('startBatchText');

        if (!validationStatus || !batchActionsCard || !startBatchBtn) return;

        const issues = [];

        // Check basic configuration
        if (!this.main.batchType) {
            issues.push('Please select a batch type');
        }

        if (this.main.scale <= 0) {
            issues.push('Please enter a valid batch scale');
        }

        // Check container requirements
        if (this.main.requiresContainers) {
            if (!this.main.containerManager?.hasValidContainerSelection()) {
                issues.push('Please configure containers for this batch');
            }
        }

        // Always show the batch actions card
        batchActionsCard.style.display = 'block';

        // Determine button state based on validation and stock check
        if (issues.length === 0) {
            if (this.main.stockChecked) {
                if (this.main.stockCheckPassed) {
                    // Stock check passed - ready to go
                    validationStatus.innerHTML = '<div class="alert alert-success"><i class="fas fa-check-circle"></i> Ready to start batch</div>';
                    startBatchBtn.disabled = false;
                    startBatchBtn.className = 'btn btn-success';
                    startBatchText.textContent = 'Start Batch';
                } else {
                    // Stock check failed - ingredients needed
                    validationStatus.innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-circle"></i> Ingredients needed - stock check failed</div>';
                    startBatchBtn.disabled = true;
                    startBatchBtn.className = 'btn btn-danger';
                    startBatchText.textContent = 'Ingredients Needed';
                }
            } else {
                // Configuration valid but no stock check yet
                validationStatus.innerHTML = '<div class="alert alert-info"><i class="fas fa-info-circle"></i> Configuration complete - run stock check to proceed</div>';
                startBatchBtn.disabled = true;
                startBatchBtn.className = 'btn btn-secondary';
                startBatchText.textContent = 'Check Stock First';
            }
        } else {
            // Missing requirements
            const issueList = issues.map(issue => `<li>${issue}</li>`).join('');
            validationStatus.innerHTML = `
                <div class="alert alert-warning">
                    <i class="fas fa-exclamation-triangle"></i> Please complete the following:
                    <ul class="mb-0 mt-2">${issueList}</ul>
                </div>
            `;
            startBatchBtn.disabled = true;
            startBatchBtn.className = 'btn btn-secondary';
            startBatchText.textContent = 'Complete Setup';
        }
    }
}
// Simple alias for legacy usage
export const FormValidator = ValidationManager;
export default ValidationManager;