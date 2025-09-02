
/**
 * Container Renderer - Handles UI rendering for container options
 */
export class ContainerRenderer {
    constructor(containerManager) {
        this.containerManager = containerManager;
    }

    renderAutoFillStrategy(autoFillStrategy) {
        const autoSection = this.containerManager.container.querySelector('#autoContainerSection');
        if (!autoSection) return;

        if (!autoFillStrategy || !autoFillStrategy.container_selection) {
            autoSection.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                    <p>No container options available. Check your container inventory.</p>
                </div>
            `;
            return;
        }

        const containersHtml = autoFillStrategy.container_selection.map((container, index) => `
            <div class="container-item mb-2 p-2 border rounded">
                <div class="d-flex justify-content-between align-items-center">
                    <span><strong>${container.container_name}</strong></span>
                    <span class="text-muted">${container.capacity} ${container.capacity_unit || 'units'}</span>
                </div>
                <div class="progress mt-1" style="height: 8px;">
                    <div class="progress-bar" role="progressbar" 
                         style="width: ${(container.containers_needed * container.capacity / autoFillStrategy.total_capacity * 100).toFixed(1)}%"
                         aria-valuenow="${(container.containers_needed * container.capacity / autoFillStrategy.total_capacity * 100).toFixed(1)}" 
                         aria-valuemin="0" aria-valuemax="100">
                    </div>
                </div>
                <small class="text-muted">${container.containers_needed} containers needed</small>
            </div>
        `).join('');

        autoSection.innerHTML = `
            <h6>Recommended Container Selection:</h6>
            ${containersHtml}
        `;
    }

    renderManualSelection(allContainerOptions, onSelectionChange) {
        const manualSection = this.containerManager.container.querySelector('#manualContainerSection');
        if (!manualSection) return;

        if (!allContainerOptions || allContainerOptions.length === 0) {
            manualSection.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="fas fa-exclamation-triangle fa-2x mb-2"></i>
                    <p>No container options available. Check your container inventory.</p>
                </div>
            `;
            return;
        }

        const optionsHtml = allContainerOptions.map(option => `
            <div class="container-option mb-2 p-2 border rounded" data-container-id="${option.container_id}">
                <div class="d-flex justify-content-between align-items-center">
                    <label class="form-check-label">
                        <input type="checkbox" class="form-check-input me-2" 
                               value="${option.container_id}"
                               data-container-name="${option.container_name}"
                               data-capacity="${option.capacity}"
                               data-capacity-unit="${option.capacity_unit || 'units'}">
                        <strong>${option.container_name}</strong>
                    </label>
                    <span class="text-muted">${option.capacity} ${option.capacity_unit || 'units'}</span>
                </div>
                <div class="mt-1">
                    <small class="text-muted">
                        Needs ${option.containers_needed} container(s) | 
                        ${option.fill_percentage ? option.fill_percentage.toFixed(1) : 100}% efficiency
                    </small>
                </div>
            </div>
        `).join('');

        manualSection.innerHTML = `
            <h6>Select Containers Manually:</h6>
            ${optionsHtml}
            <div id="manualSelectionSummary" class="mt-3"></div>
        `;

        // Add event listeners for manual checkboxes
        const checkboxes = manualSection.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                const selectedContainers = this.getSelectedContainers(checkboxes, allContainerOptions);
                this.updateManualSummary(selectedContainers);
                onSelectionChange(selectedContainers);
            });
        });
    }

    getSelectedContainers(checkboxes, allContainerOptions) {
        const checkedBoxes = Array.from(checkboxes).filter(cb => cb.checked);
        return checkedBoxes.map(cb => {
            const containerId = parseInt(cb.value);
            const fullOption = allContainerOptions.find(option => option.container_id === containerId);
            
            return fullOption || {
                container_id: containerId,
                container_name: cb.dataset.containerName,
                capacity: parseFloat(cb.dataset.capacity),
                capacity_unit: cb.dataset.capacityUnit
            };
        }).filter(Boolean);
    }

    updateManualSummary(selectedContainers) {
        const summaryDiv = this.containerManager.container.querySelector('#manualSelectionSummary');
        if (!summaryDiv) return;

        if (selectedContainers.length > 0) {
            const totalCapacity = selectedContainers.reduce((sum, container) => sum + container.capacity, 0);
            summaryDiv.innerHTML = `
                <div class="alert alert-info">
                    <strong>Selected:</strong> ${selectedContainers.length} container type(s)<br>
                    <strong>Total Capacity:</strong> ${totalCapacity.toFixed(2)} ${selectedContainers[0]?.capacity_unit || 'units'}
                </div>
            `;
        } else {
            summaryDiv.innerHTML = '';
        }
    }
}
