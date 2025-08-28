// Container Progress Bar - Handles containment percentage calculations and display
export class ContainerProgressBar {
    constructor(containerManager) {
        this.containerManager = containerManager; // Renamed from 'container' to 'containerManager' for clarity
    }

    update() {
        if (!this.containerManager.containerPlan?.success) {
            this.clear();
            return;
        }

        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
        let containment_percentage;

        if (autoFillEnabled) {
            containment_percentage = this.containerManager.containerPlan.containment_percentage || 0;
        } else {
            containment_percentage = this.calculateManualContainment();
        }

        this.updateProgressBar(containment_percentage);
    }

    calculateManualContainment() {
        const projectedYield = this.containerManager.main.baseYield * this.containerManager.main.scale;
        let totalCapacity = 0;

        console.log('🔍 CONTAINMENT: Calculating for yield', projectedYield);

        document.querySelectorAll('[data-container-row]').forEach(row => {
            const select = row.querySelector('.container-select');
            const quantityInput = row.querySelector('.container-quantity');

            if (select && quantityInput && select.value) {
                const container = this.containerManager.containerPlan?.container_selection?.find(c => c.container_id == select.value);
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

    // Add method to calculate last container fill percentage
    calculateLastContainerFillPercentage() {
        const containers = this.containerManager.getSelectedContainers ? this.containerManager.getSelectedContainers() : [];
        if (containers.length === 0) return 100;

        const projectedYield = this.containerManager.main.baseYield * this.containerManager.main.scale;
        let remainingYield = projectedYield;

        console.log('🔍 FILL CALC: Starting with yield', projectedYield, 'containers:', containers.length);

        // Calculate how much goes into each container except the last
        for (let i = 0; i < containers.length - 1; i++) {
            const container = containers[i];
            const containerCapacity = parseFloat(container.capacity_in_yield_unit || container.capacity) || 0;
            const quantity = parseInt(container.quantity) || 1;
            const containerTotal = containerCapacity * quantity;
            remainingYield -= containerTotal;
            console.log('🔍 FILL CALC: Container', i, 'uses', containerTotal, 'remaining:', remainingYield);
        }

        // Calculate fill percentage for the last container
        const lastContainer = containers[containers.length - 1];
        const lastContainerCapacity = parseFloat(lastContainer.capacity_in_yield_unit || lastContainer.capacity) || 0;
        const lastQuantity = parseInt(lastContainer.quantity) || 1;

        console.log('🔍 FILL CALC: Last container capacity:', lastContainerCapacity, 'quantity:', lastQuantity);

        if (lastContainerCapacity === 0) return 100;

        // Calculate fill percentage for ONE unit of the last container type
        const fillPercentage = (remainingYield / lastContainerCapacity) * 100;
        const result = Math.min(100, Math.max(0, fillPercentage));

        console.log('🔍 FILL CALC: Last container fill:', result.toFixed(1), '%');
        return result;
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

        // CONTAINMENT MESSAGE (primary concern)
        let containmentMessage = '';
        let containmentClass = '';

        if (percentage >= 97) {  // Within 3% tolerance = 100% containment
            containmentMessage = '✅ Batch fully contained';
            containmentClass = 'text-success';
        } else {
            containmentMessage = '⚠️ Partial containment - add more containers';
            containmentClass = 'text-danger';
        }

        // FILL EFFICIENCY MESSAGE (secondary concern - only if contained)
        let fillEfficiencyMessage = '';
        let fillEfficiencyClass = '';

        if (percentage >= 97) {  // Only show fill efficiency if we have containment
            // Calculate last container fill efficiency
            const lastContainerFill = this.calculateLastContainerFillPercentage();

            if (lastContainerFill < 100) {
                if (lastContainerFill < 75) {
                    // RED - Critical fill efficiency issue
                    fillEfficiencyMessage = ` • ⚠️ Partial fill warning: last container will be filled less than 75% - consider using other containers`;
                    fillEfficiencyClass = 'text-danger';
                } else {
                    // YELLOW - Moderate fill efficiency issue  
                    fillEfficiencyMessage = ` • ⚠️ Last container partially filled to ${lastContainerFill.toFixed(1)}%`;
                    fillEfficiencyClass = 'text-warning';
                }
            }
        }

        // Combine messages
        message = containmentMessage + fillEfficiencyMessage;

        // Set class priority: danger > warning > success
        if (containmentClass === 'text-danger' || fillEfficiencyClass === 'text-danger') {
            className += ' text-danger';
        } else if (fillEfficiencyClass === 'text-warning') {
            className += ' text-warning';
        } else {
            className += ' ' + containmentClass;
        }

        // Fallback for old logic compatibility
        if (percentage >= 97) {
            // message already set above
        } else if (percentage >= 97) {
            message = '✅ Batch contained within 3% tolerance';
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