
// Container Renderer - Handles all container display logic
export class ContainerRenderer {
    constructor(containerManager) {
        this.container = containerManager;
    }

    displayPlan() {
        const containerResults = document.getElementById('containerResults');
        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;

        console.log('🔍 CONTAINER RENDER: Displaying plan, auto-fill:', autoFillEnabled);

        if (!containerResults || !this.container.containerPlan?.success) {
            this.clearResults();
            return;
        }

        const { container_selection } = this.container.containerPlan;

        if (!container_selection || container_selection.length === 0) {
            containerResults.innerHTML = '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> No suitable containers found</div>';
            return;
        }

        if (autoFillEnabled) {
            this.renderAutoFillResults(containerResults, container_selection);
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
        const stockQuantity = container.stock_qty || container.available_quantity || container.quantity || 0;
        const containerName = container.container_name || 'Unknown Container';
        const quantityNeeded = container.quantity || container.containers_needed || 0;

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
        const capacity = container.capacity || 0;
        const unit = container.unit || 'ml';

        if (container.capacity_in_yield_unit && container.yield_unit && container.conversion_successful) {
            return `<strong>${container.capacity_in_yield_unit} ${container.yield_unit}</strong> (${capacity} ${unit})`;
        } else if (container.capacity_in_yield_unit && container.yield_unit) {
            return `<strong>${container.capacity_in_yield_unit} ${container.yield_unit}</strong> (${capacity} ${unit})`;
        }

        return `${capacity} ${unit}`;
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
