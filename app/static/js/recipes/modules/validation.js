// Validation Module
export class Validator {
    constructor(mainApp) {
        this.main = mainApp;
    }

    updateValidation() {
        const reasons = [];
        const warnings = [];

        if (!this.main.batchType) {
            reasons.push('Select batch type');
        }

        const isValid = reasons.length === 0;

        // Update submit button state
        const submitBtn = document.getElementById('submitBtn');
        if (submitBtn) {
            submitBtn.disabled = !isValid;
        }

        return { isValid, reasons, warnings };
    }
}