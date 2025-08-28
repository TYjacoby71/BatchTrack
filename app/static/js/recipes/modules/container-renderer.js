// Container Renderer - Handles all container display logic
export class ContainerRenderer {
    constructor(containerManager) {
        this.container = containerManager;
        // Ensure containerSelectionDiv is initialized, assuming it's a property of the class
        // or will be set later. If it's meant to be a DOM element, it should be selected or created.
        // For this fix, we assume it's a property that will be set or is available.
        // As a placeholder, let's assume it's managed elsewhere or will be selected in a method.
        this.containerSelectionDiv = document.getElementById('containerSelectionRows');
    }

    displayPlan() {
        console.log('🔍 CONTAINER RENDER: Displaying plan, auto-fill:', this.container.autoFill);

        if (!this.container.containerPlan) {
            this.displayContainerError('No container plan available');
            return;
        }

        if (this.container.autoFill) {
            this.renderAutoFillResults();
        } else {
            this.renderManualContainerOptions();
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

    // New or modified methods for manual selection
    renderManualContainerOptions() {
        const containerPlan = this.container.containerPlan;

        console.log('🔍 CONTAINER RENDER: Rendering manual options, plan:', containerPlan);

        // Clear existing content
        if (!this.containerSelectionDiv) {
            this.containerSelectionDiv = document.getElementById('containerSelectionRows');
        }
        this.containerSelectionDiv.innerHTML = '';

        // Get all available containers from the backend response
        // The backend should send all allowed containers, not just the selected ones
        let availableContainers = [];

        if (containerPlan.container_selection && containerPlan.container_selection.length > 0) {
            // Use selected containers from auto-fill as available options
            availableContainers = containerPlan.container_selection;
        } else if (containerPlan.available_containers) {
            // Use available containers list if provided
            availableContainers = containerPlan.available_containers;
        } else {
            this.displayContainerError('No container options available');
            return;
        }

        console.log('🔍 CONTAINER RENDER: Available containers:', availableContainers);

        // Create a dropdown with all available containers
        this.createManualContainerSelection(availableContainers);

        this.updateContainerSummary();
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
                                ${container.container_name} (${container.capacity} ${container.yield_unit})
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

        // Add event listeners
        containerRow.querySelector('.container-type-select').addEventListener('change', () => {
            this.updateContainerSummary();
        });

        containerRow.querySelector('.container-quantity').addEventListener('input', () => {
            this.updateContainerSummary();
        });

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
                                ${container.container_name} (${container.capacity} ${container.yield_unit})
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

        // Add event listeners
        containerRow.querySelector('.container-type-select').addEventListener('change', () => {
            this.updateContainerSummary();
        });

        containerRow.querySelector('.container-quantity').addEventListener('input', () => {
            this.updateContainerSummary();
        });

        containerRow.querySelector('.remove-container-row').addEventListener('click', () => {
            containerRow.remove();
            this.updateContainerSummary();
        });
    }

    updateContainerSummary() {
        // Calculate total capacity from manual selections
        const rows = this.containerSelectionDiv.querySelectorAll('.container-selection-row');
        let totalCapacity = 0;
        let validSelections = 0;

        rows.forEach(row => {
            const select = row.querySelector('.container-type-select');
            const quantity = row.querySelector('.container-quantity');

            if (select.value && quantity.value) {
                const selectedOption = select.options[select.selectedIndex];
                const capacity = parseFloat(selectedOption.dataset.capacity) || 0;
                const qty = parseInt(quantity.value) || 0;
                totalCapacity += capacity * qty;
                validSelections++;
            }
        });

        // Update summary display
        const summaryElement = document.querySelector('.container-summary');
        if (summaryElement && this.container.containerPlan) {
            // Assuming this.container.main.getYieldAmount() is correctly implemented and available
            const yieldAmount = this.container.main.getYieldAmount ? this.container.main.getYieldAmount() : 0;
            const containmentPercentage = yieldAmount > 0 ? (totalCapacity / yieldAmount) * 100 : 0;

            summaryElement.innerHTML = `
                <div class="alert ${containmentPercentage >= 100 ? 'alert-success' : 'alert-warning'}">
                    <strong>Manual Selection:</strong> 
                    ${containmentPercentage.toFixed(1)}% containment
                    (${totalCapacity.toFixed(2)} capacity vs ${yieldAmount.toFixed(2)} yield)
                    ${containmentPercentage >= 100 ? ' ✓' : ' ⚠️ Insufficient capacity'}
                </div>
            `;
        }
    }
}