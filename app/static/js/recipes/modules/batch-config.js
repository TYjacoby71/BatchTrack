
// Batch Configuration Module
export class BatchConfig {
    constructor(mainApp) {
        this.main = mainApp;
    }

    bindEvents() {
        // Scale input
        const scaleInput = document.getElementById('batchScale');
        if (scaleInput) {
            scaleInput.addEventListener('input', () => {
                this.main.scale = parseFloat(scaleInput.value) || 1.0;
                this.updateProjectedYield();
                if (this.main.requiresContainers) {
                    this.main.containerManager.fetchContainerPlan();
                }
            });
        }

        // Batch type select
        const batchTypeSelect = document.getElementById('batchType');
        if (batchTypeSelect) {
            batchTypeSelect.addEventListener('change', () => {
                this.main.batchType = batchTypeSelect.value;
                this.main.validator.updateValidation();
            });
        }

        // Container requirement toggle
        const containerToggle = document.getElementById('requiresContainers');
        if (containerToggle) {
            containerToggle.addEventListener('change', () => {
                this.main.requiresContainers = containerToggle.checked;
                this.main.containerManager.onContainerRequirementChange();
            });
        }
    }

    updateProjectedYield() {
        const projectedYield = this.main.baseYield * this.main.scale;
        const yieldDisplay = document.getElementById('projectedYield');
        if (yieldDisplay) {
            yieldDisplay.textContent = projectedYield.toFixed(2) + ' ' + this.main.unit;
        }
    }
}
