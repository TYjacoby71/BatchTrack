
// Container Management Main Controller
export class ContainerManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.containerPlan = null;
        this.fetchingPlan = false;
        this.lastPlanResult = null;
        
        // Initialize sub-modules
        this.planFetcher = new ContainerPlanFetcher(this);
        this.renderer = new ContainerRenderer(this);
        this.progressBar = new ContainerProgressBar(this);
        this.manualMode = new ManualContainerMode(this);
        this.autoFillMode = new AutoFillContainerMode(this);
    }

    bindEvents() {
        console.log('🔍 CONTAINER MANAGER DEBUG: Binding events');

        // Add container button
        const addContainerBtn = document.getElementById('addContainerBtn');
        if (addContainerBtn) {
            addContainerBtn.addEventListener('click', () => this.manualMode.addContainerRow());
        }

        // Auto-fill toggle
        const autoFillToggle = document.getElementById('autoFillEnabled');
        if (autoFillToggle) {
            autoFillToggle.addEventListener('change', (e) => this.handleModeToggle(e.target.checked));
        }
    }

    handleModeToggle(autoFillEnabled) {
        console.log('🔍 AUTO-FILL TOGGLE:', autoFillEnabled);
        
        this.toggleContainerSections(autoFillEnabled);

        if (autoFillEnabled && this.main.requiresContainers) {
            this.autoFillMode.activate();
        } else if (!autoFillEnabled) {
            this.manualMode.activate();
        }
    }

    toggleContainerSections(autoFillEnabled) {
        const autoFillResults = document.getElementById('autoFillResults');
        const manualSection = document.getElementById('manualContainerSection');

        if (autoFillResults) {
            autoFillResults.style.display = autoFillEnabled ? 'block' : 'none';
        }

        if (manualSection) {
            manualSection.style.display = autoFillEnabled ? 'none' : 'block';
        }

        // When switching to manual mode, populate manual rows from auto-fill results
        if (!autoFillEnabled && this.containerPlan?.success && this.containerPlan.container_selection) {
            this.manualMode.populateFromAutoFill();
        }

        this.progressBar.update();
    }

    onContainerRequirementChange() {
        if (this.main.requiresContainers) {
            const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked ?? true;
            this.toggleContainerSections(autoFillEnabled);
            this.planFetcher.fetchContainerPlan();
        } else {
            this.containerPlan = null;
            this.renderer.clearResults();
        }
    }

    displayContainerPlan() {
        this.renderer.displayPlan();
        this.progressBar.update();
    }

    displayContainerError(message) {
        this.renderer.displayError(message);
    }
}

// Container Plan Fetcher Module
class ContainerPlanFetcher {
    constructor(containerManager) {
        this.container = containerManager;
    }

    async fetchContainerPlan() {
        console.log('🔍 CONTAINER DEBUG: fetchContainerPlan called');

        if (this.container.fetchingPlan) {
            console.log('🔍 CONTAINER DEBUG: Plan fetch already in progress, skipping');
            return this.container.lastPlanResult;
        }

        this.container.fetchingPlan = true;

        if (!this.container.main.recipe || !this.container.main.recipe.id) {
            console.error('🚨 CONTAINER DEBUG: Recipe data not available');
            this.container.fetchingPlan = false;
            return null;
        }

        if (!this.container.main.requiresContainers) {
            console.log('🔍 CONTAINER DEBUG: Recipe does not require containers');
            this.container.fetchingPlan = false;
            return null;
        }

        const scale = this.container.main.scale || parseFloat(document.getElementById('scaleInput')?.value) || 1;
        console.log('🔍 CONTAINER DEBUG: Fetching container plan for recipe', this.container.main.recipe.id, 'scale:', scale);

        const yieldAmount = (this.container.main.recipe.yield_amount || 1) * scale;
        console.log('🔍 CONTAINER DEBUG: Yield amount calculated:', yieldAmount);

        try {
            const data = await this.container.main.apiCall(`/recipes/${this.container.main.recipe.id}/auto-fill-containers`, {
                scale: scale,
                yield_amount: yieldAmount,
                yield_unit: this.container.main.unit
            });

            if (data.success) {
                console.log('🔍 CONTAINER DEBUG: Plan successful, displaying results');
                this.container.containerPlan = data;
                this.container.lastPlanResult = data;
                this.container.displayContainerPlan();
                this.container.fetchingPlan = false;
                return data;
            } else {
                console.log('🔍 CONTAINER DEBUG: Plan failed:', data.error);
                this.container.displayContainerError(data.error);
                this.container.fetchingPlan = false;
                return null;
            }
        } catch (error) {
            console.error('🚨 CONTAINER NETWORK ERROR:', error);
            this.container.displayContainerError('Network error while loading containers');
            this.container.fetchingPlan = false;
            return null;
        }
    }
}

// Container Renderer Module
class ContainerRenderer {
    constructor(containerManager) {
        this.container = containerManager;
    }

    displayPlan() {
        const containerResults = document.getElementById('containerResults');
        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;

        console.log('🔍 DISPLAY PLAN DEBUG: Container results element found:', !!containerResults);
        console.log('🔍 DISPLAY PLAN DEBUG: Container plan success:', this.container.containerPlan?.success);
        console.log('🔍 DISPLAY PLAN DEBUG: Auto-fill enabled:', autoFillEnabled);

        if (!containerResults || !this.container.containerPlan?.success) {
            console.log('🔍 DISPLAY PLAN DEBUG: Clearing results - no element or failed plan');
            this.clearResults();
            return;
        }

        const { container_selection } = this.container.containerPlan;
        console.log('🔍 DISPLAY PLAN DEBUG: Container selection data:', container_selection);

        if (!container_selection || container_selection.length === 0) {
            console.log('🔍 DISPLAY PLAN DEBUG: No containers in selection');
            containerResults.innerHTML = '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> No suitable containers found</div>';
            return;
        }

        console.log('🔍 DISPLAY PLAN DEBUG: Rendering', container_selection.length, 'containers, auto-fill:', autoFillEnabled);

        if (autoFillEnabled) {
            this.renderContainerResults(containerResults, container_selection, true);
        } else {
            containerResults.innerHTML = '<p class="text-muted">Switch to auto-fill mode to see container recommendations, or add containers manually below.</p>';
        }
    }

    renderContainerResults(containerResults, containers, isAutoFill = false) {
        console.log('🔍 RENDER CONTAINERS: Containers data:', containers, 'Auto-fill:', isAutoFill);

        if (!containers || containers.length === 0) {
            containerResults.innerHTML = '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> No containers found</div>';
            return;
        }

        const containerClass = isAutoFill ? 'bg-success bg-opacity-10' : 'bg-light';
        const resultClass = isAutoFill ? 'auto-fill-results' : 'manual-results';

        let html = `<div class="${resultClass}">`;

        if (isAutoFill && containers.length > 1) {
            html += `
                <div class="alert alert-info mb-3">
                    <i class="fas fa-puzzle-piece"></i> 
                    <strong>Multi-Container Optimization:</strong> 
                    Using ${containers.length} container types for optimal efficiency
                </div>
            `;
        }

        containers.forEach((container, index) => {
            html += this.renderSingleContainer(container, index, containerClass, isAutoFill);
        });

        html += '</div>';
        containerResults.innerHTML = html;
    }

    renderSingleContainer(container, index, containerClass, isAutoFill) {
        const stockQuantity = container.stock_qty || container.available_quantity || container.quantity || 0;
        const containerName = container.container_name || 'Unknown Container';
        const containerCapacity = container.capacity || 0;
        const containerUnit = container.unit || 'ml';
        const quantityNeeded = container.quantity || container.containers_needed || 0;

        let capacityDisplay = `${containerCapacity} ${containerUnit}`;
        if (container.capacity_in_yield_unit && container.yield_unit && container.conversion_successful) {
            capacityDisplay = `<strong>${container.capacity_in_yield_unit} ${container.yield_unit}</strong> (${containerCapacity} ${containerUnit})`;
        } else if (container.capacity_in_yield_unit && container.yield_unit) {
            capacityDisplay = `<strong>${container.capacity_in_yield_unit} ${container.yield_unit}</strong> (${containerCapacity} ${containerUnit})`;
        }

        let optimizationBadge = '';
        if (isAutoFill && index > 0) {
            optimizationBadge = `<div class="mt-1"><span class="badge bg-primary"><i class="fas fa-cog"></i> Optimized</span></div>`;
        }

        return `
            <div class="row align-items-center mb-3 p-3 border rounded ${containerClass}" data-${isAutoFill ? 'auto' : 'manual'}-container="${index}">
                <div class="col-md-3">
                    <label class="form-label small">Container Type</label>
                    <div class="form-control form-control-sm bg-light border-0">
                        <strong>${containerName}</strong>
                        ${optimizationBadge}
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
                    <div class="badge ${stockQuantity >= quantityNeeded ? 'bg-success' : 'bg-warning'} fs-6">${stockQuantity}</div>
                </div>
                <div class="col-md-1">
                    <div class="text-center">
                        <i class="fas fa-check-circle text-success" title="Optimal selection"></i>
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

// Container Progress Bar Module
class ContainerProgressBar {
    constructor(containerManager) {
        this.container = containerManager;
    }

    update() {
        if (!this.container.containerPlan?.success) return;

        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
        let containment_percentage = 0;

        if (!autoFillEnabled) {
            containment_percentage = this.calculateManualContainment();
        } else {
            containment_percentage = this.container.containerPlan.containment_percentage || 0;
        }

        this.updateProgressBar(containment_percentage);
    }

    calculateManualContainment() {
        const projectedYield = this.container.main.baseYield * this.container.main.scale;
        let totalCapacity = 0;

        document.querySelectorAll('[data-container-row]').forEach(row => {
            const select = row.querySelector('.container-select');
            const quantityInput = row.querySelector('.container-quantity');

            if (select && quantityInput && select.value) {
                const container = this.container.containerPlan?.container_selection?.find(c => c.container_id == select.value);
                if (container) {
                    const quantity = parseInt(quantityInput.value) || 0;
                    const capacityToUse = container.capacity_in_yield_unit || container.capacity;
                    totalCapacity += capacityToUse * quantity;
                }
            }
        });

        if (projectedYield > 0) {
            return Math.min((totalCapacity / projectedYield) * 100, 100);
        } else {
            return totalCapacity > 0 ? 100 : 0;
        }
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

        if (percentage >= 100) {
            message = '✅ Batch fully contained';
            className += ' text-success';
        } else if (percentage >= 97) {
            message = '✅ Batch contained within 3% tolerance';
            className += ' text-success';
        } else if (percentage > 0) {
            message = '⚠️ Partial containment - add more containers';
            className += ' text-warning';
        } else {
            message = '❌ No containment - add containers to proceed';
            className += ' text-danger';
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

// Manual Container Mode Module
class ManualContainerMode {
    constructor(containerManager) {
        this.container = containerManager;
    }

    activate() {
        console.log('🔍 MANUAL MODE: Activating manual container selection');
        this.container.renderer.clearResults();
    }

    populateFromAutoFill() {
        const containerRows = document.getElementById('containerSelectionRows');
        if (!containerRows || !this.container.containerPlan?.container_selection) return;

        containerRows.innerHTML = '';

        this.container.containerPlan.container_selection.forEach((container, index) => {
            const rowHtml = this.createContainerRowHTML(index);
            const rowDiv = document.createElement('div');
            rowDiv.innerHTML = rowHtml;
            const newRow = rowDiv.firstElementChild;

            if (newRow) {
                containerRows.appendChild(newRow);
                this.bindContainerRowEvents(index);

                const select = newRow.querySelector('.container-select');
                const quantityInput = newRow.querySelector('.container-quantity');

                if (select && quantityInput) {
                    select.value = container.container_id;
                    quantityInput.value = container.quantity || container.containers_needed || 1;
                    this.updateContainerRow(index);
                }
            }
        });

        console.log('🔍 MANUAL POPULATE: Pre-populated', this.container.containerPlan.container_selection.length, 'container rows from auto-fill');
    }

    addContainerRow() {
        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
        if (autoFillEnabled) {
            alert('Please uncheck Auto-Fill to add containers manually.');
            return;
        }

        if (!this.container.containerPlan?.container_selection || this.container.containerPlan.container_selection.length === 0) {
            alert('No containers available for this recipe.');
            return;
        }

        const rowsContainer = document.getElementById('containerSelectionRows');
        if (!rowsContainer) {
            console.error('🚨 Container rows container not found!');
            return;
        }

        const rowIndex = rowsContainer.children.length;
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
        const availableContainers = this.container.containerPlan?.container_selection || [];

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

        const stockQuantity = container.stock_qty || container.quantity || container.available_quantity || 0;
        stockBadge.textContent = stockQuantity;

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

// Auto-Fill Container Mode Module
class AutoFillContainerMode {
    constructor(containerManager) {
        this.container = containerManager;
    }

    activate() {
        console.log('🔍 AUTO-FILL MODE: Activating auto-fill container selection');
        this.container.planFetcher.fetchContainerPlan();
    }
}
