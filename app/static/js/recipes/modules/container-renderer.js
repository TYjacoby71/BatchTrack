
// Container Renderer - Displays backend container results ONLY
export class ContainerRenderer {
    constructor(containerManager) {
        this.container = containerManager;
        this.containerSelectionDiv = document.getElementById('containerSelectionRows');
    }

    displayPlan() {
        console.log('🔍 CONTAINER RENDER: Displaying plan, auto-fill:', this.container.autoFill);

        if (!this.container.containerPlan) {
            this.displayError('No container plan available');
            return;
        }

        if (this.container.autoFill) {
            this.renderAutoFillResults();
        } else {
            this.renderManualContainerOptions();
        }
    }

    renderAutoFillResults() {
        const containerResults = document.getElementById('containerResults');
        const containers = this.container.containerPlan.container_selection || [];
        
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
        const stockQuantity = container.available_quantity || 0;
        const containerName = container.container_name || 'Unknown Container';
        const quantityNeeded = container.containers_needed || 0;

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
        // Use backend-provided display format
        if (container.capacity_in_yield_unit && container.yield_unit) {
            return `<strong>${container.capacity_in_yield_unit} ${container.yield_unit}</strong>`;
        }
        return `${container.capacity || 0} ${container.unit || 'ml'}`;
    }

    renderManualContainerOptions() {
        const containerPlan = this.container.containerPlan;
        console.log('🔍 CONTAINER RENDER: Rendering manual options, plan:', containerPlan);

        if (!this.containerSelectionDiv) {
            this.containerSelectionDiv = document.getElementById('containerSelectionRows');
        }
        this.containerSelectionDiv.innerHTML = '';

        // Use ALL available containers from backend
        const availableContainers = containerPlan.available_containers || [];
        
        if (availableContainers.length === 0) {
            this.displayError('No container options available');
            return;
        }

        console.log('🔍 CONTAINER RENDER: Available containers:', availableContainers);
        this.createManualContainerSelection(availableContainers);
    }

    createManualContainerSelection(availableContainers) {
        const containerRow = document.createElement('div');
        containerRow.className = 'container-selection-row mb-3';
        containerRow.innerHTML = `
            <div class="row align-items-center">
                <div class="col-md-6">
                    <label class="form-label">Select Container Type:</label>
                    <select class="form-select container-type-select" data-row="0">
                        <option value="">Choose a container...</option>
                        ${availableContainers.map(container => 
                            `<option value="${container.container_id}" 
                                data-capacity="${container.capacity}" 
                                data-name="${container.container_name}">
                                ${container.container_name} (${container.capacity} ${container.yield_unit || 'ml'})
                            </option>`
                        ).join('')}
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Quantity:</label>
                    <input type="number" class="form-control container-quantity" 
                           data-row="0" min="1" value="1">
                </div>
                <div class="col-md-3">
                    <button type="button" class="btn btn-outline-secondary add-container-row">
                        <i class="fas fa-plus"></i> Add Another
                    </button>
                </div>
            </div>
        `;

        this.containerSelectionDiv.appendChild(containerRow);

        // Add event listeners for manual mode only
        containerRow.querySelector('.add-container-row').addEventListener('click', () => {
            this.addContainerRow(availableContainers);
        });
    }

    addContainerRow(availableContainers) {
        const existingRows = this.containerSelectionDiv.querySelectorAll('.container-selection-row');
        const newRowIndex = existingRows.length;

        const containerRow = document.createElement('div');
        containerRow.className = 'container-selection-row mb-3';
        containerRow.innerHTML = `
            <div class="row align-items-center">
                <div class="col-md-6">
                    <select class="form-select container-type-select" data-row="${newRowIndex}">
                        <option value="">Choose a container...</option>
                        ${availableContainers.map(container => 
                            `<option value="${container.container_id}" 
                                data-capacity="${container.capacity}" 
                                data-name="${container.container_name}">
                                ${container.container_name} (${container.capacity} ${container.yield_unit || 'ml'})
                            </option>`
                        ).join('')}
                    </select>
                </div>
                <div class="col-md-3">
                    <input type="number" class="form-control container-quantity" 
                           data-row="${newRowIndex}" min="1" value="1">
                </div>
                <div class="col-md-3">
                    <button type="button" class="btn btn-outline-danger remove-container-row">
                        <i class="fas fa-trash"></i> Remove
                    </button>
                </div>
            </div>
        `;

        this.containerSelectionDiv.appendChild(containerRow);

        containerRow.querySelector('.remove-container-row').addEventListener('click', () => {
            containerRow.remove();
        });
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
