
// Container Progress Bar - Handles containment percentage calculations and display
export class ContainerProgressBar {
    constructor(containerManager) {
        this.container = containerManager;
    }

    update() {
        if (!this.container.containerPlan?.success) {
            this.clear();
            return;
        }

        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
        let containment_percentage;

        if (autoFillEnabled) {
            containment_percentage = this.container.containerPlan.containment_percentage || 0;
        } else {
            containment_percentage = this.calculateManualContainment();
        }

        this.updateProgressBar(containment_percentage);
    }

    calculateManualContainment() {
        const projectedYield = this.container.main.baseYield * this.container.main.scale;
        let totalCapacity = 0;

        console.log('🔍 CONTAINMENT: Calculating for yield', projectedYield);

        document.querySelectorAll('[data-container-row]').forEach(row => {
            const select = row.querySelector('.container-select');
            const quantityInput = row.querySelector('.container-quantity');

            if (select && quantityInput && select.value) {
                const container = this.container.containerPlan?.container_selection?.find(c => c.container_id == select.value);
                if (container) {
                    const quantity = parseInt(quantityInput.value) || 0;
                    const capacityToUse = container.capacity_in_yield_unit || container.capacity;
                    const containerTotal = capacityToUse * quantity;
                    totalCapacity += containerTotal;

                    console.log('🔍 CONTAINMENT: Container', container.container_name, 'x', quantity, '=', containerTotal);
                }
            }
        });

        const containmentPercent = projectedYield > 0 ? (totalCapacity / projectedYield) * 100 : (totalCapacity > 0 ? 100 : 0);
        console.log('🔍 CONTAINMENT: Total capacity', totalCapacity, 'vs yield', projectedYield, '=', containmentPercent.toFixed(1), '%');

        return Math.min(containmentPercent, 100);
    }

    updateProgressBar(percentage) {
        const progressBar = document.getElementById('containmentProgressBar');
        const percentSpan = document.getElementById('containmentPercent');
        const messageSpan = document.getElementById('liveContainmentMessage');

        const displayPercentage = Math.min(percentage, 100);
        const actualPercentage = percentage;

        if (progressBar) {
            progressBar.style.width = `${displayPercentage}%`;
            progressBar.textContent = `${actualPercentage.toFixed(1)}%`;
            progressBar.className = `progress-bar ${actualPercentage >= 100 ? 'bg-success' : 'bg-warning'}`;
        }

        if (percentSpan) {
            percentSpan.textContent = `${actualPercentage.toFixed(1)}%`;
        }

        if (messageSpan) {
            const message = this.getContainmentMessage(actualPercentage);
            messageSpan.textContent = message.text;
            messageSpan.className = message.className;
        }
    }

    getContainmentMessage(percentage) {
        let message = '';
        let className = 'form-text mt-1';

        if (percentage >= 100) {
            message = '✅ Batch fully contained';
            className += ' text-success';
        } else if (percentage >= 97) {
            message = '✅ Batch contained within 3% tolerance';
            className += ' text-success';
        } else if (percentage > 0) {
            message = '⚠️ Partial containment - add more containers';
            className += ' text-warning';
        } else {
            message = '❌ No containment - add containers to proceed';
            className += ' text-danger';
        }

        // Add efficiency warnings if available
        const warnings = this.container.containerPlan?.warnings || [];
        const fillWarnings = warnings.filter(w => w.includes('partially filled') || w.includes('overfilled'));
        if (fillWarnings.length > 0 && percentage >= 95) {
            message += ` • ${fillWarnings.join(' • ')}`;
        }

        return { text: message, className };
    }

    clear() {
        const progressBar = document.getElementById('containmentProgressBar');
        const percentSpan = document.getElementById('containmentPercent');
        const messageSpan = document.getElementById('liveContainmentMessage');

        if (progressBar) {
            progressBar.style.width = '0%';
            progressBar.textContent = '0%';
            progressBar.className = 'progress-bar bg-warning';
        }

        if (percentSpan) percentSpan.textContent = '0%';
        if (messageSpan) messageSpan.textContent = '';
    }
}
