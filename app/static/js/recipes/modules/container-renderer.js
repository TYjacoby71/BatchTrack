
// Container Renderer - Handles all container display logic
export class ContainerRenderer {
    constructor(containerManager) {
        this.container = containerManager;
    }

    displayPlan() {
        const containerResults = document.getElementById('containerResults');
        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;

        console.log('🔍 CONTAINER RENDER: Displaying plan, auto-fill:', autoFillEnabled);
        console.log('🔍 CONTAINER RENDER: Container plan:', this.container.containerPlan);
        console.log('🔍 CONTAINER RENDER: Auto fill strategy:', this.container.autoFillStrategy);

        if (!containerResults) {
            console.warn('🔍 CONTAINER RENDER: containerResults element not found');
            return;
        }

        // Check if we have container plan data
        if (!this.container.containerPlan?.success) {
            this.clearResults();
            return;
        }

        if (autoFillEnabled) {
            // Use auto-fill strategy if available
            if (this.container.autoFillStrategy?.container_selection) {
                this.renderAutoFillResults(containerResults, this.container.autoFillStrategy.container_selection);
            } else {
                containerResults.innerHTML = '<div class="alert alert-info"><i class="fas fa-info-circle"></i> No auto-fill strategy available. Try refreshing container options.</div>';
            }
        } else {
            containerResults.innerHTML = '<p class="text-muted">Switch to auto-fill mode to see container recommendations, or add containers manually below.</p>';
        }
    }

    renderAutoFillResults(containerResults, containers) {
        console.log('🔍 CONTAINER RENDER: Rendering auto-fill results for', containers.length, 'containers');

        let html = '<div class="auto-fill-results">';

        if (containers.length > 1) {
            html += `
                <div class="alert alert-info mb-3">
                    <i class="fas fa-puzzle-piece"></i> 
                    <strong>Multi-Container Optimization:</strong> 
                    Using ${containers.length} container types for optimal efficiency
                </div>
            `;
        }

        containers.forEach((container, index) => {
            html += this.renderContainerCard(container, index, true);
        });

        html += '</div>';
        containerResults.innerHTML = html;
    }

    renderContainerCard(container, index, isAutoFill = false) {
        const stockQuantity = parseInt(container.stock_qty || container.available_quantity || container.quantity || 0);
        const containerName = (container.container_name || 'Unknown Container').toString();
        const quantityNeeded = parseInt(container.quantity || container.containers_needed || 0);

        const capacityDisplay = this.formatCapacityDisplay(container);
        const stockBadgeClass = stockQuantity >= quantityNeeded ? 'bg-success' : 'bg-warning';
        const containerClass = isAutoFill ? 'bg-success bg-opacity-10' : 'bg-light';

        return `
            <div class="row align-items-center mb-3 p-3 border rounded ${containerClass}" data-container-card="${index}">
                <div class="col-md-3">
                    <label class="form-label small">Container Type</label>
                    <div class="form-control form-control-sm bg-light border-0">
                        <strong>${containerName}</strong>
                    </div>
                </div>
                <div class="col-md-2">
                    <label class="form-label small">Quantity Needed</label>
                    <div class="form-control form-control-sm bg-light border-0">
                        <strong>${quantityNeeded}</strong>
                    </div>
                </div>
                <div class="col-md-4">
                    <label class="form-label small">Capacity Each</label>
                    <div class="form-control form-control-sm bg-light border-0">
                        ${capacityDisplay}
                    </div>
                </div>
                <div class="col-md-2">
                    <label class="form-label small">Available Stock</label>
                    <div class="badge ${stockBadgeClass} fs-6">${stockQuantity}</div>
                </div>
                <div class="col-md-1">
                    <div class="text-center">
                        <i class="fas fa-check-circle text-success" title="Optimal selection"></i>
                    </div>
                </div>
            </div>
        `;
    }

    formatCapacityDisplay(container) {
        const capacity = parseFloat(container.capacity || 0);
        const unit = (container.unit || container.capacity_unit || 'ml').toString();

        if (container.capacity_in_yield_unit && container.yield_unit && container.conversion_successful) {
            return `<strong>${parseFloat(container.capacity_in_yield_unit)} ${container.yield_unit}</strong> (${capacity} ${unit})`;
        } else if (container.capacity_in_yield_unit && container.yield_unit) {
            return `<strong>${parseFloat(container.capacity_in_yield_unit)} ${container.yield_unit}</strong> (${capacity} ${unit})`;
        }

        return `${capacity} ${unit}`;
    }

    renderManualContainerOptions(manualSection, allContainerOptions) {
        console.log('🔍 MANUAL RENDER: Rendering manual options for', allContainerOptions?.length || 0, 'containers');

        if (!allContainerOptions || allContainerOptions.length === 0) {
            manualSection.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                    <p>No container options available. Check your container inventory.</p>
                </div>
            `;
            return;
        }

        const optionsHtml = allContainerOptions.map(option => {
            const containerId = parseInt(option.container_id || 0);
            const containerName = (option.container_name || 'Unknown Container').toString();
            const capacity = parseFloat(option.capacity || 0);
            const capacityUnit = (option.capacity_unit || 'units').toString();
            const containersNeeded = parseInt(option.containers_needed || 1);
            const fillPercentage = parseFloat(option.fill_percentage || 100);
            
            return `
                <div class="container-option mb-2 p-2 border rounded" data-container-id="${containerId}">
                    <div class="d-flex justify-content-between align-items-center">
                        <label class="form-check-label">
                            <input type="checkbox" class="form-check-input me-2" 
                                   value="${containerId}"
                                   data-container-name="${containerName}"
                                   data-capacity="${capacity}"
                                   data-capacity-unit="${capacityUnit}">
                            <strong>${containerName}</strong>
                        </label>
                        <span class="text-muted">${capacity} ${capacityUnit}</span>
                    </div>
                    <div class="mt-1">
                        <small class="text-muted">
                            Needs ${containersNeeded} container(s) | 
                            ${fillPercentage.toFixed(1)}% efficiency
                        </small>
                    </div>
                </div>
            `;
        }).join('');

        manualSection.innerHTML = `
            <h6>Select Containers Manually:</h6>
            ${optionsHtml}
            <div id="manualSelectionSummary" class="mt-3"></div>
        `;

        this.attachManualSelectionListeners();
    }

    attachManualSelectionListeners() {
        const checkboxes = document.querySelectorAll('.container-option input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateManualSelection();
            });
        });
    }

    updateManualSelection() {
        const selected = Array.from(document.querySelectorAll('.container-option input[type="checkbox"]:checked'));
        const summary = document.getElementById('manualSelectionSummary');

        if (!summary) return;

        if (selected.length === 0) {
            summary.innerHTML = '<p class="text-muted">No containers selected</p>';
            return;
        }

        let totalCapacity = 0;
        const summaryHtml = selected.map(checkbox => {
            const capacity = parseFloat(checkbox.dataset.capacity || '0') || 0;
            const containerName = (checkbox.dataset.containerName || 'Unknown').toString();
            const unit = (checkbox.dataset.capacityUnit || 'units').toString();
            
            totalCapacity += capacity;
            
            return `
                <div class="d-flex justify-content-between align-items-center py-1">
                    <span>${containerName}</span>
                    <span class="text-muted">${capacity} ${unit}</span>
                </div>
            `;
        }).join('');

        const yieldAmount = parseFloat(window.recipeData?.yield_amount || 0);
        const fillPercentage = yieldAmount > 0 ? (yieldAmount / totalCapacity) * 100 : 0;
        const fillClass = fillPercentage > 100 ? 'text-danger' : fillPercentage > 90 ? 'text-warning' : 'text-success';

        summary.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <h6>Manual Selection Summary:</h6>
                    ${summaryHtml}
                    <hr>
                    <div class="d-flex justify-content-between">
                        <strong>Total Capacity:</strong>
                        <span>${totalCapacity} ${window.recipeData?.yield_unit || 'units'}</span>
                    </div>
                    <div class="d-flex justify-content-between">
                        <strong>Fill Percentage:</strong>
                        <span class="${fillClass}">${fillPercentage.toFixed(1)}%</span>
                    </div>
                </div>
            </div>
        `;
    }

    clearResults() {
        const containerResults = document.getElementById('containerResults');
        const containerRows = document.getElementById('containerSelectionRows');

        if (containerResults) {
            containerResults.innerHTML = '<p class="text-muted">Container management disabled</p>';
        }

        if (containerRows) {
            containerRows.innerHTML = '';
        }
    }

    displayError(message) {
        const containerResults = document.getElementById('containerResults');
        if (containerResults) {
            containerResults.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle"></i> ${message}
                    <hr>
                    <div class="d-flex justify-content-between align-items-center">
                        <small class="text-muted">Cannot find suitable containers for this recipe</small>
                        <button type="button" class="btn btn-sm btn-outline-secondary" onclick="document.getElementById('requiresContainers').click()">
                            <i class="fas fa-times"></i> Disable Container Requirement
                        </button>
                    </div>
                </div>
            `;
        }
    }
}
