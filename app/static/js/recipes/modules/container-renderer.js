// Container Renderer - Handles all container display logic
export class ContainerRenderer {
    constructor(containerManager) {
        this.container = containerManager;
        this.autoFillMode = false; // Initialize autoFillMode
    }

    // Method to set auto-fill mode
    setAutoFillMode(mode) {
        this.autoFillMode = mode;
    }

    displayContainerPlan() {
        console.log('🔍 CONTAINER RENDER: Displaying plan, auto-fill:', this.autoFillMode);

        if (!this.container.containerPlan || !this.container.containerPlan.success) {
            this.clearResults();
            return;
        }

        const plan = this.container.containerPlan;
        console.log('🔍 CONTAINER RENDER: Plan data:', plan);

        if (this.autoFillMode && plan.container_selection && plan.container_selection.length > 0) {
            this.renderAutoFillResults(plan);
        } else if (!this.autoFillMode) {
            this.renderManualMode();
        } else {
            console.log('🔍 CONTAINER RENDER: No containers to display');
            this.clearResults();
        }
    }

    renderManualMode() {
        const containerResults = document.getElementById('containerResults');
        if (containerResults) {
            containerResults.innerHTML = '<p class="text-muted">Switch to auto-fill mode to see container recommendations, or add containers manually below.</p>';
        }
    }


    renderAutoFillResults(plan) {
        console.log('🔍 CONTAINER RENDER: Rendering auto-fill results for', plan.container_selection.length, 'containers');

        const resultsDiv = document.getElementById('autoFillResults');
        if (!resultsDiv) {
            console.error('🚨 CONTAINER RENDER: autoFillResults element not found');
            return;
        }

        let html = '<div class="container-plan-results">';

        // Header with containment info
        html += '<div class="d-flex justify-content-between align-items-center mb-3">';
        html += `<h6>Recommended Containers (${plan.containment_percentage.toFixed(1)}% contained)</h6>`;
        if (plan.container_selection.length > 0) {
            html += `<button class="btn btn-sm btn-success" onclick="window.planProductionApp.containerManager.selectRecommendedContainers()">
                        <i class="fas fa-check"></i> Select These
                     </button>`;
        }
        html += '</div>';

        // Container list with selection checkboxes
        html += '<div class="container-selection-list">';

        plan.container_selection.forEach((container, index) => {
            const totalCapacity = container.capacity * container.containers_needed;

            html += `
                <div class="container-item border rounded p-3 mb-2" data-container-id="${container.container_id}">
                    <div class="d-flex align-items-start">
                        <div class="form-check me-3">
                            <input class="form-check-input container-select-checkbox" 
                                   type="checkbox" 
                                   id="container_${container.container_id}" 
                                   data-container-id="${container.container_id}"
                                   data-containers-needed="${container.containers_needed}"
                                   checked>
                            <label class="form-check-label" for="container_${container.container_id}"></label>
                        </div>
                        <div class="flex-grow-1">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <strong>${container.container_name}</strong>
                                    <div class="text-muted small">
                                        ${container.containers_needed} × ${container.capacity.toFixed(2)} ${container.yield_unit} 
                                        = ${totalCapacity.toFixed(2)} ${container.yield_unit} total
                                    </div>
                                    <div class="text-muted small">
                                        Available: ${container.available_quantity} containers
                                    </div>
                                </div>
                                <div class="text-end">
                                    <span class="badge bg-primary">${container.containers_needed} needed</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';

        // Summary
        if (plan.containment_metrics) {
            if (plan.containment_metrics.is_contained) {
                html += '<div class="alert alert-success small">✅ Recipe fits in selected containers</div>';
            } else {
                html += `<div class="alert alert-warning small">⚠️ Need ${plan.containment_metrics.remaining_yield.toFixed(2)} ${plan.containment_metrics.yield_unit} more capacity</div>`;
            }
        }

        // Last container fill efficiency warning
        if (plan.last_container_fill_metrics && plan.last_container_fill_metrics.is_low_efficiency) {
            html += `<div class="alert alert-info small">
                        💡 The last ${plan.last_container_fill_metrics.container_name} will only be ${plan.last_container_fill_metrics.fill_percentage}% full. 
                        Consider using smaller containers for better efficiency.
                     </div>`;
        }

        html += '</div>';
        resultsDiv.innerHTML = html;

        // Add event listeners for checkboxes
        this.bindContainerCheckboxes();
    }

    bindContainerCheckboxes() {
        const checkboxes = document.querySelectorAll('.container-select-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                console.log('🔍 CONTAINER SELECT: Container', e.target.dataset.containerId, 'selected:', e.target.checked);
                this.updateContainerSelection();
            });
        });
    }

    updateContainerSelection() {
        const selectedContainers = [];
        const checkboxes = document.querySelectorAll('.container-select-checkbox:checked');

        checkboxes.forEach(checkbox => {
            selectedContainers.push({
                container_id: parseInt(checkbox.dataset.containerId),
                containers_needed: parseInt(checkbox.dataset.containersNeeded)
            });
        });

        console.log('🔍 CONTAINER SELECT: Updated selection:', selectedContainers);

        // Update the container manager's selection
        if (this.container.containerPlan) {
            this.container.containerPlan.selected_containers = selectedContainers;
        }
    }

    clearResults() {
        const containerResults = document.getElementById('containerResults');
        const autoFillResults = document.getElementById('autoFillResults');
        const containerRows = document.getElementById('containerSelectionRows');

        if (containerResults) {
            containerResults.innerHTML = '<p class="text-muted">Container management disabled</p>';
        }
        if (autoFillResults) {
            autoFillResults.innerHTML = '';
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