// Form Validation Module
export class ValidationManager {
    constructor(mainManager) {
        this.main = mainManager;
    }

    validateForm() {
        const startBatchBtn = document.getElementById('startBatchBtn');
        if (!startBatchBtn) return;

        let isValid = true;
        let reasons = [];
        let warnings = [];

        console.log('🔍 VALIDATION: Checking form validity...');

        // Check batch type - REQUIRED
        if (!this.main.batchType) {
            isValid = false;
            reasons.push('Select batch type');
        }

        // Check stock availability - REQUIRED
        if (this.main.stockManager.stockCheckResults && !this.main.stockManager.stockCheckResults.all_available) {
            isValid = false;
            reasons.push('Insufficient ingredients');
        }

        // Container validation - allows bypass with warnings
        if (this.main.requiresContainers) {
            const containerPlan = this.main.containerManager.containerPlan;
            
            if (!containerPlan?.success) {
                warnings.push('No containers available - product will be uncontained');
            } else if (containerPlan.containment_percentage < 100) {
                const uncontained = this.main.baseYield * this.main.scale - (containerPlan.total_capacity || 0);
                warnings.push(`Incomplete containment: ${uncontained.toFixed(2)} ${this.main.unit} will be uncontained`);
            }
        }

        console.log('🔍 VALIDATION: Valid:', isValid, 'Reasons:', reasons, 'Warnings:', warnings);

        // Only disable button for critical validation failures
        startBatchBtn.disabled = !isValid;

        // Update button appearance based on validation state
        this.updateButtonState(startBatchBtn, isValid, reasons, warnings);
    }

    updateButtonState(button, isValid, reasons, warnings) {
        if (isValid) {
            if (warnings.length > 0) {
                button.textContent = 'Start Batch (with containment issues)';
                button.classList.remove('btn-secondary', 'btn-success');
                button.classList.add('btn-warning');
                button.title = 'Warning: ' + warnings.join('; ');
            } else {
                button.textContent = 'Start Batch';
                button.classList.remove('btn-secondary', 'btn-warning');
                button.classList.add('btn-success');
                button.title = '';
            }
        } else {
            button.textContent = `Cannot Start: ${reasons[0]}`;
            button.classList.remove('btn-success', 'btn-warning');
            button.classList.add('btn-secondary');
            button.title = 'Required: ' + reasons.join('; ');
        }
    }
}