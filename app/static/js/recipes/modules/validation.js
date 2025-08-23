
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
// Validation Management Module
export class ValidationManager {
    constructor(mainManager) {
        this.main = mainManager;
    }

    bindEvents() {
        // Validation events can be bound here if needed
    }

    updateValidation() {
        console.log('🔍 VALIDATION: Checking form validity...');
        
        const reasons = [];
        const warnings = [];
        
        if (!this.main.batchType) {
            reasons.push('Select batch type');
        }
        
        const isValid = reasons.length === 0;
        console.log('🔍 VALIDATION: Valid:', isValid, 'Reasons:', reasons, 'Warnings:', warnings);
        
        // Update submit button state
        const submitBtn = document.getElementById('submitBtn');
        if (submitBtn) {
            submitBtn.disabled = !isValid;
        }

        // Update any validation UI
        this.updateValidationUI(isValid, reasons, warnings);
    }

    updateValidationUI(isValid, reasons, warnings) {
        // Update validation messages in the UI
        const validationContainer = document.getElementById('validationMessages');
        if (validationContainer) {
            let html = '';
            
            if (reasons.length > 0) {
                html += '<div class="alert alert-danger"><ul class="mb-0">';
                reasons.forEach(reason => {
                    html += `<li>${reason}</li>`;
                });
                html += '</ul></div>';
            }
            
            if (warnings.length > 0) {
                html += '<div class="alert alert-warning"><ul class="mb-0">';
                warnings.forEach(warning => {
                    html += `<li>${warning}</li>`;
                });
                html += '</ul></div>';
            }
            
            validationContainer.innerHTML = html;
        }
    }
}
