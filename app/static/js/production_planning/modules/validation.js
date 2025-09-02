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

            if (!isValid) {
                startBatchBtn.title = 'Issues: ' + issues.join(', ');
            } else {
                startBatchBtn.title = warnings.length > 0 ? 'Warnings: ' + warnings.join(', ') : '';
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