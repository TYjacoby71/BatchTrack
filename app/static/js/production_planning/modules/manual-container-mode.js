
// Manual Container Mode - Handles manual container row management
export class ManualContainerMode {
    constructor(containerManager) {
        this.container = containerManager;
    }

    activate() {
        console.log('🔍 MANUAL MODE: Switching to manual container selection');
        this.clearAutoFillResults();
    }

    clearAutoFillResults() {
        const containerResults = document.getElementById('containerResults');
        if (containerResults) {
            containerResults.innerHTML = '<p class="text-muted">Switch to auto-fill mode to see container recommendations, or add containers manually below.</p>';
        }
    }

    populateFromAutoFill() {
        if (!this.container.containerPlan?.container_selection) return;

        console.log('🔍 MANUAL MODE: Populating from auto-fill data');
        
        const containerRows = document.getElementById('containerSelectionRows');
        if (!containerRows) return;

        // Clear existing rows
        containerRows.innerHTML = '';

        // Add a row for each container from auto-fill
        this.container.containerPlan.container_selection.forEach((container, index) => {
            this.addPrefilledRow(container, index);
        });

        console.log('🔍 MANUAL MODE: Pre-populated', this.container.containerPlan.container_selection.length, 'rows');
    }

    addPrefilledRow(containerData, index) {
        const containerRows = document.getElementById('containerSelectionRows');
        if (!containerRows) return;

        const rowHtml = this.createContainerRowHTML(index);
        const rowDiv = document.createElement('div');
        rowDiv.innerHTML = rowHtml;
        const newRow = rowDiv.firstElementChild;

        if (newRow) {
            containerRows.appendChild(newRow);
            this.bindContainerRowEvents(index);

            // Pre-fill the data
            const select = newRow.querySelector('.container-select');
            const quantityInput = newRow.querySelector('.container-quantity');

            if (select && quantityInput) {
                select.value = containerData.container_id;
                quantityInput.value = containerData.quantity || containerData.containers_needed || 1;
                this.updateContainerRow(index);
            }
        }
    }

    addContainerRow() {
        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
        if (autoFillEnabled) {
            alert('Please uncheck Auto-Fill to add containers manually.');
            return;
        }

        if (!this.container.containerPlan?.container_selection?.length) {
            alert('No containers available for this recipe.');
            return;
        }

        const rowsContainer = document.getElementById('containerSelectionRows');
        if (!rowsContainer) {
            console.error('🚨 MANUAL MODE: Container rows container not found!');
            return;
        }

        const rowIndex = rowsContainer.children.length;
        console.log('🔍 MANUAL MODE: Adding row', rowIndex);

        const rowHtml = this.createContainerRowHTML(rowIndex);
        const rowDiv = document.createElement('div');
        rowDiv.innerHTML = rowHtml;
        const newRow = rowDiv.firstElementChild;

        if (newRow) {
            rowsContainer.appendChild(newRow);
            this.bindContainerRowEvents(rowIndex);
        }
    }

    createContainerRowHTML(index) {
        const availableContainers = this.container.containerPlan?.container_options || this.container.containerPlan?.container_selection || [];

        let optionsHTML = '<option value="">Select Container</option>';
        availableContainers.forEach(container => {
            const containerName = container.container_name || 'Unknown Container';
            optionsHTML += `<option value="${container.container_id}">${containerName}</option>`;
        });

        return `
            <div class="row align-items-center mb-3 p-3 border rounded bg-light" data-container-row="${index}">
                <div class="col-md-4">
                    <label class="form-label small">Container Type</label>
                    <select class="form-select form-select-sm container-select" data-row="${index}">
                        ${optionsHTML}
                    </select>
                </div>
                <div class="col-md-2">
                    <label class="form-label small">Quantity</label>
                    <input type="number" min="1" class="form-control form-control-sm container-quantity" 
                           data-row="${index}" value="1">
                </div>
                <div class="col-md-4">
                    <label class="form-label small">Capacity Each</label>
                    <div class="form-control form-control-sm bg-light border-0 container-capacity" data-row="${index}">-</div>
                </div>
                <div class="col-md-2">
                    <label class="form-label small">Available Stock</label>
                    <div class="badge bg-info fs-6 available-stock" data-row="${index}">-</div>
                </div>
            </div>
            <div class="row">
                <div class="col-12 text-end">
                    <button type="button" class="btn btn-danger btn-sm remove-container-btn" 
                            data-row="${index}">
                        <i class="fas fa-times"></i> Remove
                    </button>
                </div>
            </div>
        `;
    }

    bindContainerRowEvents(rowIndex) {
        const row = document.querySelector(`[data-container-row="${rowIndex}"]`);
        if (!row) return;

        const select = row.querySelector('.container-select');
        const quantityInput = row.querySelector('.container-quantity');
        const removeBtn = row.querySelector('.remove-container-btn');

        if (select) {
            select.addEventListener('change', () => this.updateContainerRow(rowIndex));
        }

        if (quantityInput) {
            quantityInput.addEventListener('input', () => this.container.progressBar.update());
        }

        if (removeBtn) {
            removeBtn.addEventListener('click', () => this.removeContainerRow(rowIndex));
        }

        this.updateContainerRow(rowIndex);
    }

    updateContainerRow(rowIndex) {
        const row = document.querySelector(`[data-container-row="${rowIndex}"]`);
        if (!row) return;

        const select = row.querySelector('.container-select');
        const stockBadge = row.querySelector('.available-stock');
        const capacityDiv = row.querySelector('.container-capacity');

        if (!select || !stockBadge) return;

        const selectedId = select.value;
        if (!selectedId) {
            stockBadge.textContent = '-';
            if (capacityDiv) capacityDiv.textContent = '-';
            return;
        }

        const container = this.container.containerPlan?.container_selection?.find(c => c.container_id == selectedId);
        if (!container) {
            stockBadge.textContent = '-';
            if (capacityDiv) capacityDiv.textContent = '-';
            return;
        }

        // Update stock display
        const stockQuantity = container.stock_qty || container.quantity || container.available_quantity || 0;
        stockBadge.textContent = stockQuantity;

        // Update capacity display
        if (capacityDiv) {
            let capacityDisplay = `${container.capacity || 0} ${container.original_unit || container.unit || 'ml'}`;

            if (container.capacity_in_yield_unit && container.yield_unit && container.conversion_successful) {
                capacityDisplay = `<strong>${container.capacity_in_yield_unit} ${container.yield_unit}</strong> (${container.original_capacity || container.capacity} ${container.original_unit || container.unit})`;
            } else if (container.capacity_in_yield_unit && container.yield_unit) {
                capacityDisplay = `<strong>${container.capacity_in_yield_unit} ${container.yield_unit}</strong> (${container.original_capacity || container.capacity} ${container.original_unit || container.unit})`;
            }

            capacityDiv.innerHTML = capacityDisplay;
        }

        this.container.progressBar.update();
    }

    removeContainerRow(rowIndex) {
        const row = document.querySelector(`[data-container-row="${rowIndex}"]`);
        if (row) {
            row.remove();
            this.container.progressBar.update();
        }
    }
}
