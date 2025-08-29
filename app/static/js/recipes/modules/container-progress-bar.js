// Container Progress Bar - Handles containment percentage calculations
export class ContainerProgressBar {
    constructor(containerManager) {
        this.container = containerManager;
    }

    update() {
        const progressElement = document.getElementById('containerProgress');
        const progressText = document.getElementById('containerProgressText');

        if (!progressElement || !progressText) return;

        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
        let containmentData = null;

        if (autoFillEnabled && this.container.containerPlan?.success) {
            // Auto-fill mode: use backend calculation
            containmentData = this.getAutoFillContainment();
        } else {
            // Manual mode: calculate from manual selections using same logic as backend
            containmentData = this.getManualContainment();
        }

        this.displayProgress(progressElement, progressText, containmentData);
    }

    getAutoFillContainment() {
        const plan = this.container.containerPlan;
        return {
            percentage: plan.containment_percentage || 0,
            totalCapacity: plan.total_capacity || 0,
            yieldNeeded: this.container.main.getProjectedYield(),
            isContained: plan.containment_percentage >= 100,
            source: 'auto-fill'
        };
    }

    getManualContainment() {
        const containerRows = document.querySelectorAll('[data-container-row]');
        let totalCapacity = 0;
        const yieldNeeded = this.container.main.getProjectedYield();

        console.log('🔍 CONTAINMENT: Calculating for yield', yieldNeeded);

        containerRows.forEach(row => {
            const select = row.querySelector('.container-select');
            const quantityInput = row.querySelector('.container-quantity');

            if (!select?.value || !quantityInput?.value) return;

            const containerId = select.value;
            const quantity = parseInt(quantityInput.value) || 0;

            // Find container in plan data - check both container_selection and available options
            let container = this.container.containerPlan?.container_selection?.find(c => c.container_id == containerId);
            if (!container && this.container.containerPlan?.available_containers) {
                container = this.container.containerPlan.available_containers.find(c => c.container_id == containerId);
            }

            if (container && quantity > 0) {
                // Use same capacity calculation as backend - prefer capacity_in_yield_unit
                const capacity = container.capacity_in_yield_unit || container.capacity || 0;
                const containerCapacity = capacity * quantity;
                totalCapacity += containerCapacity;

                console.log('🔍 CONTAINMENT: Container', container.container_name, 'x', quantity, '=', containerCapacity);
            }
        });

        console.log('🔍 CONTAINMENT: Total capacity', totalCapacity, 'vs yield', yieldNeeded, '=', (totalCapacity / yieldNeeded * 100).toFixed(1), '%');

        // Use same calculation as backend
        let percentage = yieldNeeded > 0 ? (totalCapacity / yieldNeeded) * 100 : 0;

        // Apply same tolerance as backend - if 97% or more, show as 100%
        const displayPercentage = percentage >= 97.0 ? 100.0 : percentage;

        return {
            percentage: displayPercentage,
            rawPercentage: percentage,
            totalCapacity: totalCapacity,
            yieldNeeded: yieldNeeded,
            isContained: percentage >= 97.0, // Same tolerance as backend
            source: 'manual'
        };
    }

    displayProgress(progressElement, progressText, containmentData) {
        if (!containmentData) {
            progressElement.style.width = '0%';
            progressElement.className = 'progress-bar bg-secondary';
            progressText.textContent = 'No containers selected';
            return;
        }

        const { percentage, totalCapacity, yieldNeeded, isContained } = containmentData;
        const displayPercentage = Math.min(percentage, 100);

        // Update progress bar
        progressElement.style.width = `${displayPercentage}%`;

        // Color coding - consistent with backend expectations
        if (isContained) {
            progressElement.className = 'progress-bar bg-success';
        } else if (percentage >= 75) {
            progressElement.className = 'progress-bar bg-warning';
        } else {
            progressElement.className = 'progress-bar bg-danger';
        }

        // Update text - consistent messaging for auto-fill and manual
        if (isContained) {
            progressText.textContent = '✅ Fully Contained';
        } else {
            const shortfall = yieldNeeded - totalCapacity;
            const unit = this.container.main.unit || 'units';
            progressText.textContent = `⚠️ ${shortfall.toFixed(2)} ${unit} remaining`;
        }
    }
}