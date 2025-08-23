// Form Validation Module
export class ValidationManager {
    constructor(mainManager) {
        this.main = mainManager;
    }

    bindEvents() {
        // No specific events for validation currently
    }

    updateValidation() {
        const reasons = [];
        const warnings = [];

        // Check batch type
        if (!this.main.batchType) {
            reasons.push('Select batch type');
        }

        // Container validation
        if (this.main.requiresContainers && this.main.containerManager) {
            const containerValidation = this.main.containerManager.validateContainers();
            if (!containerValidation.valid) {
                reasons.push(...containerValidation.reasons);
            }
            warnings.push(...containerValidation.warnings);
        }

        const isValid = reasons.length === 0;

        this.updateUI(isValid, reasons, warnings);
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