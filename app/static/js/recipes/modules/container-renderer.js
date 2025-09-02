
/**
 * Container Renderer - Pure Display Logic Only
 * 
 * Handles only the visual rendering of container data received from backend.
 * No business logic calculations - just display what the backend provides.
 */
export class ContainerRenderer {
    constructor(containerManager) {
        this.containerManager = containerManager;
    }

    displayPlan() {
        const containerResults = document.getElementById('containerResults');
        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;

        console.log('🔍 CONTAINER RENDER: Displaying plan, auto-fill:', autoFillEnabled);
        console.log('🔍 CONTAINER RENDER: Container data:', this.containerManager.containerPlan);

        if (!containerResults) {
            console.warn('🔍 CONTAINER RENDER: containerResults element not found');
            return;
        }

        // Check if we have valid data from backend
        if (!this.containerManager.containerPlan?.success) {
            console.warn('🔍 CONTAINER RENDER: No successful container plan data');
            this.showNoData();
            return;
        }

        if (autoFillEnabled) {
            this.renderAutoFillMode();
        } else {
            this.renderManualMode();
        }
    }

    renderAutoFillMode() {
        const containerResults = document.getElementById('containerResults');
        const strategy = this.containerManager.containerPlan?.auto_fill_strategy;

        console.log('🔍 CONTAINER RENDER: Auto-fill strategy:', strategy);
        console.log('🔍 CONTAINER RENDER: Full container plan:', this.containerManager.containerPlan);

        if (!strategy || !strategy.container_selection || strategy.container_selection.length === 0) {
            containerResults.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> 
                    No auto-fill strategy available. Try refreshing container options.
                    <br><small class="text-muted">Debug: Strategy exists: ${!!strategy}, Container selection: ${strategy?.container_selection?.length || 0}</small>
                </div>
            `;
            return;
        }

        let html = '<div class="auto-fill-results">';

        // Multi-container notification
        if (strategy.container_selection.length > 1) {
            html += `
                <div class="alert alert-info mb-3">
                    <i class="fas fa-puzzle-piece"></i> 
                    <strong>Multi-Container Optimization:</strong> 
                    Using ${strategy.container_selection.length} container types for optimal efficiency
                </div>
            `;
        }

        // Render each container
        strategy.container_selection.forEach((container, index) => {
            html += this.renderContainerCard(container, index, true);
        });

        html += '</div>';
        containerResults.innerHTML = html;
    }

    renderManualMode() {
        const containerResults = document.getElementById('containerResults');
        const options = this.containerManager.containerPlan?.all_container_options || [];

        if (options.length === 0) {
            containerResults.innerHTML = `
                <p class="text-muted">
                    Switch to auto-fill mode to see container recommendations, or add containers manually below.
                </p>
            `;
            return;
        }

        containerResults.innerHTML = `
            <p class="text-muted">
                Manual mode enabled. Use the manual selection tools below to choose containers.
            </p>
        `;
    }

    renderContainerCard(container, index, isAutoFill = false) {
        // Extract data with safe defaults
        const containerName = container.container_name || 'Unknown Container';
        const quantityNeeded = container.containers_needed || container.quantity || 0;
        const availableStock = container.available_quantity || 0;
        const capacity = container.capacity || 0;
        const capacityUnit = container.capacity_unit || 'units';

        // Determine styling
        const stockBadgeClass = availableStock >= quantityNeeded ? 'bg-success' : 'bg-warning';
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
                        ${capacity} ${capacityUnit}
                    </div>
                </div>
                <div class="col-md-2">
                    <label class="form-label small">Available Stock</label>
                    <div class="badge ${stockBadgeClass} fs-6">${availableStock}</div>
                </div>
                <div class="col-md-1">
                    <div class="text-center">
                        <i class="fas fa-check-circle text-success" title="Optimal selection"></i>
                    </div>
                </div>
            </div>
        `;
    }

    renderManualContainerOptions(targetElement, allContainerOptions) {
        console.log('🔍 MANUAL RENDER: Rendering manual options for', allContainerOptions?.length || 0, 'containers');

        if (!allContainerOptions || allContainerOptions.length === 0) {
            targetElement.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                    <p>No container options available. Check your container inventory.</p>
                </div>
            `;
            return;
        }

        const optionsHtml = allContainerOptions.map(option => {
            const containerId = option.container_id || 0;
            const containerName = option.container_name || 'Unknown Container';
            const capacity = option.capacity || 0;
            const capacityUnit = option.capacity_unit || 'units';
            const containersNeeded = option.containers_needed || 1;
            const fillPercentage = option.fill_percentage || 100;
            
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

        targetElement.innerHTML = `
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
                this.updateManualSelectionSummary();
            });
        });
    }

    updateManualSelectionSummary() {
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
            const containerName = checkbox.dataset.containerName || 'Unknown';
            const unit = checkbox.dataset.capacityUnit || 'units';
            
            totalCapacity += capacity;
            
            return `
                <div class="d-flex justify-content-between align-items-center py-1">
                    <span>${containerName}</span>
                    <span class="text-muted">${capacity} ${unit}</span>
                </div>
            `;
        }).join('');

        const recipeData = window.recipeData;
        const scale = this.getCurrentScale();
        const targetYield = (recipeData?.yield_amount || 0) * scale;
        const fillPercentage = targetYield > 0 ? (targetYield / totalCapacity) * 100 : 0;
        const fillClass = fillPercentage > 100 ? 'text-danger' : fillPercentage > 90 ? 'text-warning' : 'text-success';

        summary.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <h6>Manual Selection Summary:</h6>
                    ${summaryHtml}
                    <hr>
                    <div class="d-flex justify-content-between">
                        <strong>Total Capacity:</strong>
                        <span>${totalCapacity} ${recipeData?.yield_unit || 'units'}</span>
                    </div>
                    <div class="d-flex justify-content-between">
                        <strong>Fill Percentage:</strong>
                        <span class="${fillClass}">${fillPercentage.toFixed(1)}%</span>
                    </div>
                </div>
            </div>
        `;
    }

    showNoData() {
        const containerResults = document.getElementById('containerResults');
        if (containerResults) {
            containerResults.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="fas fa-box fa-2x mb-2"></i>
                    <p>Click "Refresh Options" to load container recommendations</p>
                </div>
            `;
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

    clearResults() {
        const containerResults = document.getElementById('containerResults');
        if (containerResults) {
            containerResults.innerHTML = '<p class="text-muted">Container management disabled</p>';
        }
    }

    getCurrentScale() {
        const scaleInput = document.getElementById('scaleInput') || document.getElementById('scaleFactorInput');
        return scaleInput ? parseFloat(scaleInput.value) || 1.0 : 1.0;
    }
}
