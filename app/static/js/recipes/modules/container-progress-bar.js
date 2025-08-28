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
        // Only calculate if we have container plan data and we're in manual mode
        if (!this.containerManager.containerPlan?.container_selection) return 100;

        const containers = this.getSelectedContainersFromDOM();
        if (containers.length === 0) return 100;

        const projectedYield = this.containerManager.main.baseYield * this.containerManager.main.scale;
        console.log('🔍 FILL CALC: Starting with yield', projectedYield, 'containers:', containers.length);

        // Calculate how much yield goes into each container type
        let remainingYieldToAllocate = projectedYield;

        for (let i = 0; i < containers.length; i++) {
            const container = containers[i];

            if (i === containers.length - 1) {
                // Last container type - calculate partial fill
                const fullContainersOfThisType = container.quantity - 1;
                const yieldInFullContainers = fullContainersOfThisType * container.capacity;
                remainingYieldToAllocate -= yieldInFullContainers;

                // The remaining yield goes into the final container
                if (remainingYieldToAllocate > 0 && container.capacity > 0) {
                    const lastContainerFillPercentage = (remainingYieldToAllocate / container.capacity) * 100;
                    console.log('🔍 FILL CALC: Last container fill:', lastContainerFillPercentage.toFixed(1), '%');
                    return Math.min(100, Math.max(0, lastContainerFillPercentage));
                }
                break;
            } else {
                // For non-last containers, all are filled completely
                const yieldInThisContainerType = container.quantity * container.capacity;
                remainingYieldToAllocate -= yieldInThisContainerType;
            }
        }

        console.log('🔍 FILL CALC: Last container fill:', '100.0', '%');
        return 100;
    }

    // Local method to get containers from DOM safely
    getSelectedContainersFromDOM() {
        const containers = [];

        try {
            document.querySelectorAll('[data-container-row]').forEach(row => {
                const select = row.querySelector('.container-select');
                const quantityInput = row.querySelector('.container-quantity');

                if (select && quantityInput && select.value) {
                    const container = this.containerManager.containerPlan?.container_selection?.find(c => c.container_id == select.value);
                    if (container) {
                        const quantity = parseInt(quantityInput.value) || 1;
                        containers.push({
                            ...container,
                            quantity: quantity
                        });
                    }
                }
            });
        } catch (error) {
            console.log('🔍 FILL CALC: Error getting containers from DOM:', error);
        }

        return containers;
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
        // This logic should work for BOTH auto-fill and manual modes
        let fillEfficiencyMessage = '';
        let fillEfficiencyClass = '';

        if (percentage >= 97) {  // Only show fill efficiency if we have containment
            // Check if we're in auto-fill mode and have backend warnings
            const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;

            if (autoFillEnabled && this.containerManager.containerPlan?.warnings) {
                // Use backend warnings for auto-fill mode
                const backendFillWarnings = this.containerManager.containerPlan.warnings.filter(warning => 
                    warning.includes('partially filled') || warning.includes('Partial fill warning')
                );

                if (backendFillWarnings.length > 0) {
                    // Use the first fill efficiency warning from backend
                    const warning = backendFillWarnings[0];
                    if (warning.includes('less than 75%')) {
                        fillEfficiencyMessage = ` • ⚠️ ${warning}`;
                        fillEfficiencyClass = 'text-danger';
                    } else {
                        fillEfficiencyMessage = ` • ⚠️ ${warning}`;
                        fillEfficiencyClass = 'text-warning';
                    }
                }
            } else {
                // Calculate frontend fill efficiency for manual mode (or auto-fill fallback)
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

    displayWarnings(containerPlan) {
        const warningsContainer = this.container.containerCard.querySelector('.container-warnings');
        if (!warningsContainer) return;

        const warnings = [];

        // Generate containment warnings
        if (containerPlan.containment_metrics && !containerPlan.containment_metrics.is_contained) {
            const remaining = containerPlan.containment_metrics.remaining_yield;
            const unit = containerPlan.containment_metrics.yield_unit;
            warnings.push({
                type: 'danger',
                icon: 'fas fa-exclamation-circle',
                message: `Insufficient capacity: ${remaining.toFixed(1)} ${unit} remaining`
            });
        }

        // Generate fill efficiency warnings
        if (containerPlan.last_container_fill_metrics) {
            const fillMetrics = containerPlan.last_container_fill_metrics;
            if (fillMetrics.is_partial) {
                if (fillMetrics.is_low_efficiency) {
                    warnings.push({
                        type: 'warning',
                        icon: 'fas fa-exclamation-triangle',
                        message: `Partial fill warning: last ${fillMetrics.container_name} will be ${fillMetrics.fill_percentage}% filled - consider using other containers`
                    });
                } else {
                    warnings.push({
                        type: 'info',
                        icon: 'fas fa-info-circle',
                        message: `Last ${fillMetrics.container_name} will be ${fillMetrics.fill_percentage}% filled`
                    });
                }
            }
        }

        if (warnings.length === 0) {
            warningsContainer.innerHTML = '';
            warningsContainer.style.display = 'none';
            return;
        }

        const warningsHtml = warnings.map(warning => 
            `<div class="alert alert-${warning.type} alert-sm mb-2">
                <i class="${warning.icon} me-2"></i>
                ${warning.message}
            </div>`
        ).join('');

        warningsContainer.innerHTML = warningsHtml;
        warningsContainer.style.display = 'block';
    }
}