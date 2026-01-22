// Form Validation Module
export class ValidationManager {
    constructor(mainManager) {
        this.main = mainManager;
    }

    bindEvents() {
        // No specific events for validation currently
    }

    updateValidation() {
        // Form validation check
        const issues = [];
        const warnings = [];

        // Check batch type
        if (!this.main.batchType) {
            issues.push('Select batch type');
        }

        // Enforce stock check execution
        if (!this.main.stockChecked) {
            issues.push('Run stock check');
        } else if (!this.main.stockCheckPassed) {
            warnings.push('Stock shortages detected - confirmation required');
        }

        // Check container requirements if enabled
        if (this.main.requiresContainers && this.main.containerManager.containerPlan) {
            const containmentPercentage = this.main.containerManager.containerPlan.containment_percentage || 0;
            if (containmentPercentage < 50) {
                warnings.push('Low container coverage');
            }
        }

        const isValid = issues.length === 0;

        this.updateValidationUI(isValid, issues, warnings);
        return isValid;
    }

    updateValidationUI(isValid, issues, warnings) {
        const startBatchBtn = document.getElementById('startBatchBtn');
        if (startBatchBtn) {
            startBatchBtn.disabled = !isValid;

            if (isValid) {
                startBatchBtn.innerHTML = '<i class="fas fa-play me-2"></i>Start Batch';
                startBatchBtn.className = 'btn btn-primary btn-lg w-100';
                startBatchBtn.title = warnings.length > 0 ? 'Warnings: ' + warnings.join(', ') : '';
            } else {
                startBatchBtn.innerHTML = '<i class="fas fa-play me-2"></i>' + issues[0];
                startBatchBtn.className = 'btn btn-secondary btn-lg w-100';
                startBatchBtn.title = 'Issues: ' + issues.join(', ');
            }
        }

        const queueBatchBtn = document.getElementById('queueBatchBtn');
        if (queueBatchBtn) {
            const queueIssues = [...issues];
            if (this.main.stockChecked && !this.main.stockCheckPassed) {
                queueIssues.push('Resolve stock shortages for queue');
            }
            const queueValid = queueIssues.length === 0;
            queueBatchBtn.disabled = !queueValid;

            if (queueValid) {
                queueBatchBtn.innerHTML = '<i class="fas fa-list me-2"></i>Add to Queue';
                queueBatchBtn.className = 'btn btn-outline-primary btn-lg w-100';
                queueBatchBtn.title = '';
            } else {
                queueBatchBtn.innerHTML = '<i class="fas fa-list me-2"></i>' + queueIssues[0];
                queueBatchBtn.className = 'btn btn-secondary btn-lg w-100';
                queueBatchBtn.title = 'Issues: ' + queueIssues.join(', ');
            }
        }

        // Update validation message display
        const validationMsg = document.getElementById('validationMessage');
        if (validationMsg) {
            if (!isValid) {
                validationMsg.innerHTML = `<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> ${issues.join(', ')}</div>`;
            } else if (warnings.length > 0) {
                validationMsg.innerHTML = `<div class="alert alert-info"><i class="fas fa-info-circle"></i> ${warnings.join(', ')}</div>`;
            } else {
                validationMsg.innerHTML = '';
            }
        }
    }
}
// Simple alias for legacy usage
export const FormValidator = ValidationManager;
export default ValidationManager;