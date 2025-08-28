// Container Management Module
export class ContainerManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.containerPlan = null;
        this.fetchingPlan = false;
        this.lastPlanResult = null;
    }

    bindEvents() {
        console.log('🔍 CONTAINER MANAGER DEBUG: Binding events');

        // Add container button
        const addContainerBtn = document.getElementById('addContainerBtn');
        console.log('🔍 CONTAINER MANAGER DEBUG: Add container button found:', !!addContainerBtn);
        if (addContainerBtn) {
            addContainerBtn.addEventListener('click', () => this.addContainerRow());
        }

        // Auto-fill toggle
        const autoFillToggle = document.getElementById('autoFillEnabled');
        console.log('🔍 CONTAINER MANAGER DEBUG: Auto-fill toggle found:', !!autoFillToggle);
        if (autoFillToggle) {
            autoFillToggle.addEventListener('change', (e) => {
                console.log('🔍 AUTO-FILL TOGGLE:', e.target.checked);
                this.toggleContainerSections(e.target.checked);

                if (e.target.checked && this.main.requiresContainers) {
                    console.log('🔍 AUTO-FILL TOGGLE: Fetching container plan...');
                    this.fetchContainerPlan();
                } else if (!e.target.checked) {
                    // When switching to manual, preserve containers as editable rows
                    console.log('🔍 AUTO-FILL TOGGLE: Switching to manual mode, preserving container selection');
                    this.clearAutoFillResults();
                }
            });
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
            this.populateManualRowsFromAutoFill();
        }

        // Update progress bar when switching modes
        this.updateContainerProgress();
    }

    populateManualRowsFromAutoFill() {
        const containerRows = document.getElementById('containerSelectionRows');
        if (!containerRows || !this.containerPlan?.container_selection) return;

        // Clear existing manual rows first
        containerRows.innerHTML = '';

        // Add a row for each container from the auto-fill selection
        this.containerPlan.container_selection.forEach((container, index) => {
            const rowHtml = this.createContainerRowHTML(index);
            const rowDiv = document.createElement('div');
            rowDiv.innerHTML = rowHtml;
            const newRow = rowDiv.firstElementChild;

            if (newRow) {
                containerRows.appendChild(newRow);
                this.bindContainerRowEvents(index);

                // Pre-populate the row with auto-fill data
                const select = newRow.querySelector('.container-select');
                const quantityInput = newRow.querySelector('.container-quantity');

                if (select && quantityInput) {
                    select.value = container.container_id;
                    quantityInput.value = container.quantity || container.containers_needed || 1;
                    this.updateContainerRow(index);
                }
            }
        });

        console.log('🔍 MANUAL POPULATE: Pre-populated', this.containerPlan.container_selection.length, 'container rows from auto-fill');
    }

    clearAutoFillResults() {
        const containerResults = document.getElementById('containerResults');

        if (containerResults) {
            containerResults.innerHTML = '<p class="text-muted">Switch to manual container selection mode</p>';
        }

        // Don't clear manual rows anymore - let them persist
        // this.updateContainerProgress();
    }

    onContainerRequirementChange() {
        // Container card display is now handled in the main app
        if (this.main.requiresContainers) {
            // Initialize section visibility
            const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked ?? true;
            this.toggleContainerSections(autoFillEnabled);

            this.fetchContainerPlan();
        } else {
            this.containerPlan = null;
            this.clearContainerResults();
        }
    }

    async fetchContainerPlan() {
        console.log('🔍 CONTAINER DEBUG: fetchContainerPlan called');

        // Debounce multiple rapid calls
        if (this.fetchingPlan) {
            console.log('🔍 CONTAINER DEBUG: Plan fetch already in progress, skipping');
            return this.lastPlanResult;
        }

        this.fetchingPlan = true;

        if (!this.main.recipe || !this.main.recipe.id) {
            console.error('🚨 CONTAINER DEBUG: Recipe data not available');
            this.fetchingPlan = false;
            return null;
        }

        console.log('🔍 CONTAINER DEBUG: Recipe exists:', !!this.main.recipe);
        console.log('🔍 CONTAINER DEBUG: Requires containers:', this.main.requiresContainers);

        if (!this.main.requiresContainers) {
            console.log('🔍 CONTAINER DEBUG: Recipe does not require containers');
            this.fetchingPlan = false;
            return null;
        }

        const scale = this.main.scale || parseFloat(document.getElementById('scaleInput')?.value) || 1;
        console.log('🔍 CONTAINER DEBUG: Fetching container plan for recipe', this.main.recipe.id, 'scale:', scale);

        // Calculate yield amount
        const yieldAmount = (this.main.recipe.yield_amount || 1) * scale;
        console.log('🔍 CONTAINER DEBUG: Yield amount calculated:', yieldAmount);

        try {
            const data = await this.main.apiCall(`/recipes/${this.main.recipe.id}/auto-fill-containers`, {
                scale: scale,
                yield_amount: yieldAmount,
                yield_unit: this.main.unit
            });

            if (data.success) {
                console.log('🔍 CONTAINER DEBUG: Plan successful, displaying results');
                this.containerPlan = data;
                this.lastPlanResult = data;
                this.displayContainerPlan(data);
                this.fetchingPlan = false;
                return data;
            } else {
                console.log('🔍 CONTAINER DEBUG: Plan failed:', data.error);
                this.displayContainerError(data.error);
                this.fetchingPlan = false;
                return null;
            }
        } catch (error) {
            console.error('🚨 CONTAINER NETWORK ERROR:', error);
            this.displayContainerError('Network error while loading containers');
            this.fetchingPlan = false;
            return null;
        }
    }

    displayContainerPlan() {
        const containerResults = document.getElementById('containerResults');
        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;

        console.log('🔍 DISPLAY PLAN DEBUG: Container results element found:', !!containerResults);
        console.log('🔍 DISPLAY PLAN DEBUG: Container plan success:', this.containerPlan?.success);
        console.log('🔍 DISPLAY PLAN DEBUG: Auto-fill enabled:', autoFillEnabled);

        if (!containerResults || !this.containerPlan?.success) {
            console.log('🔍 DISPLAY PLAN DEBUG: Clearing results - no element or failed plan');
            this.clearContainerResults();
            return;
        }

        const { container_selection } = this.containerPlan;
        console.log('🔍 DISPLAY PLAN DEBUG: Container selection data:', container_selection);

        if (!container_selection || container_selection.length === 0) {
            console.log('🔍 DISPLAY PLAN DEBUG: No containers in selection');
            containerResults.innerHTML = '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> No suitable containers found</div>';
            return;
        }

        console.log('🔍 DISPLAY PLAN DEBUG: Rendering', container_selection.length, 'containers, auto-fill:', autoFillEnabled);

        if (autoFillEnabled) {
            this.renderContainerResults(containerResults, container_selection, true);
            // FIXED: Update progress bar immediately in auto-fill mode
            this.updateContainerProgress();
        } else {
            // Still show available containers in manual mode, just don't auto-fill
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

        // Add header for multi-container selections
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
            const stockQuantity = container.stock_qty || container.available_quantity || container.quantity || 0;
            const containerName = container.container_name || 'Unknown Container';
            const containerCapacity = container.capacity || 0;
            const containerUnit = container.unit || 'ml';
            const quantityNeeded = container.quantity || container.containers_needed || 0;

            // Show capacity with both units side by side if conversion available
            let capacityDisplay = `${containerCapacity} ${containerUnit}`;

            if (container.capacity_in_yield_unit && container.yield_unit && container.conversion_successful) {
                capacityDisplay = `<strong>${container.capacity_in_yield_unit} ${container.yield_unit}</strong> (${containerCapacity} ${containerUnit})`;
            } else if (container.capacity_in_yield_unit && container.yield_unit) {
                capacityDisplay = `<strong>${container.capacity_in_yield_unit} ${container.yield_unit}</strong> (${containerCapacity} ${containerUnit})`;
            }

            // Add optimization badge for multi-container selections
            let optimizationBadge = '';
            if (isAutoFill && containers.length > 1) {
                optimizationBadge = `<div class="mt-1"><span class="badge bg-primary"><i class="fas fa-cog"></i> Optimized</span></div>`;
            }

            html += `
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
                            ${containers.length > 1 ? 
                                '<i class="fas fa-puzzle-piece text-primary" title="Multi-container optimization"></i>' :
                                '<i class="fas fa-check-circle text-success" title="Optimal selection"></i>'
                            }
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';



        console.log('🔍 RENDER CONTAINERS: Setting HTML for', resultClass);
        containerResults.innerHTML = html;
    }

    addContainerRow() {
        console.log('🔍 ADD CONTAINER DEBUG: Add container row called');

        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
        console.log('🔍 ADD CONTAINER DEBUG: Auto-fill enabled:', autoFillEnabled);

        if (autoFillEnabled) {
            alert('Please uncheck Auto-Fill to add containers manually.');
            return;
        }

        if (!this.containerPlan?.container_selection || this.containerPlan.container_selection.length === 0) {
            console.log('🔍 ADD CONTAINER DEBUG: No containers available');
            alert('No containers available for this recipe.');
            return;
        }

        const rowsContainer = document.getElementById('containerSelectionRows');
        console.log('🔍 ADD CONTAINER DEBUG: Rows container found:', !!rowsContainer);

        if (!rowsContainer) {
            console.error('🚨 Container rows container not found!');
            return;
        }

        const rowIndex = rowsContainer.children.length;
        console.log('🔍 ADD CONTAINER DEBUG: Creating row index:', rowIndex);

        const rowHtml = this.createContainerRowHTML(rowIndex);
        console.log('🔍 ADD CONTAINER DEBUG: Row HTML created:', rowHtml.substring(0, 100) + '...');

        const rowDiv = document.createElement('div');
        rowDiv.innerHTML = rowHtml;
        const newRow = rowDiv.firstElementChild;

        if (newRow) {
            rowsContainer.appendChild(newRow);
            console.log('🔍 ADD CONTAINER DEBUG: Row appended successfully');
            this.bindContainerRowEvents(rowIndex);
        } else {
            console.error('🚨 Failed to create new row element');
        }
    }

    createContainerRowHTML(index) {
        const availableContainers = this.containerPlan?.container_selection || [];

        let optionsHTML = '<option value="">Select Container</option>';
        availableContainers.forEach(container => {
            const containerName = container.container_name || 'Unknown Container';
            // Show just the container name in the dropdown, not capacity details
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
            quantityInput.addEventListener('input', () => this.updateContainerProgress());
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

        const container = this.containerPlan?.container_selection?.find(c => c.container_id == selectedId);
        if (!container) {
            stockBadge.textContent = '-';
            if (capacityDiv) capacityDiv.textContent = '-';
            return;
        }

        // Look for stock quantity in various possible properties from the server response
        const stockQuantity = container.stock_qty || container.quantity || container.available_quantity || 0;
        console.log('🔍 STOCK DISPLAY DEBUG: Container:', container.name, 'Stock:', stockQuantity);
        stockBadge.textContent = stockQuantity;

        // Update capacity display to match auto-fill format exactly
        if (capacityDiv) {
            // Always show the converted capacity first, then original in parentheses if different
            let capacityDisplay = `${container.capacity || 0} ${container.original_unit || container.unit || 'ml'}`;

            // This matches the auto-fill display format from renderContainerResults
            if (container.capacity_in_yield_unit && container.yield_unit && container.conversion_successful) {
                capacityDisplay = `<strong>${container.capacity_in_yield_unit} ${container.yield_unit}</strong> (${container.original_capacity || container.capacity} ${container.original_unit || container.unit})`;
            } else if (container.capacity_in_yield_unit && container.yield_unit) {
                capacityDisplay = `<strong>${container.capacity_in_yield_unit} ${container.yield_unit}</strong> (${container.original_capacity || container.capacity} ${container.original_unit || container.unit})`;
            }

            capacityDiv.innerHTML = capacityDisplay;
        }

        this.updateContainerProgress();
    }

    removeContainerRow(rowIndex) {
        const row = document.querySelector(`[data-container-row="${rowIndex}"]`);
        if (row) {
            row.remove();
            this.updateContainerProgress();
        }
    }

    updateContainerProgress() {
        if (!this.containerPlan?.success) return;

        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
        let containment_percentage = 0;

        if (!autoFillEnabled) {
            // Calculate CONTAINMENT from manual container rows - can total capacity hold the yield?
            const projectedYield = this.main.baseYield * this.main.scale;
            let totalCapacity = 0;

            document.querySelectorAll('[data-container-row]').forEach(row => {
                const select = row.querySelector('.container-select');
                const quantityInput = row.querySelector('.container-quantity');

                if (select && quantityInput && select.value) {
                    const container = this.containerPlan?.container_selection?.find(c => c.container_id == select.value);
                    if (container) {
                        const quantity = parseInt(quantityInput.value) || 0;
                        // Use converted capacity for containment calculation
                        const capacityToUse = container.capacity_in_yield_unit || container.capacity;
                        totalCapacity += capacityToUse * quantity;
                        console.log(`🔍 CONTAINMENT DEBUG: Container ${container.container_name} x${quantity} = ${capacityToUse * quantity} capacity`);
                    }
                }
            });

            // FIXED: Containment = Can the total capacity hold the yield? 
            // This should be (totalCapacity / projectedYield) * 100, NOT the reverse
            if (projectedYield > 0) {
                containment_percentage = Math.min((totalCapacity / projectedYield) * 100, 100);
            } else {
                containment_percentage = totalCapacity > 0 ? 100 : 0;
            }
            console.log(`🔍 CONTAINMENT DEBUG: Yield needed: ${projectedYield}, Total capacity: ${totalCapacity}, Containment: ${containment_percentage.toFixed(1)}%`);
        } else {
            // Auto-fill should return proper containment percentage from server
            containment_percentage = this.containerPlan.containment_percentage || 0;
        }

        this.updateProgressBar(containment_percentage);
    }

    updateProgressBar(percentage) {
        const progressBar = document.getElementById('containmentProgressBar');
        const percentSpan = document.getElementById('containmentPercent');
        const messageSpan = document.getElementById('liveContainmentMessage');

        // Cap display percentage at 100% for progress bar visual
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
            let message = '';
            let className = 'form-text mt-1';

            // Containment message (primary concern)
            if (actualPercentage >= 100) {
                message = '✅ Batch fully contained';
                className += ' text-success';
            } else if (actualPercentage >= 97) {
                message = '✅ Batch contained within 3% tolerance';
                className += ' text-success';
            } else if (actualPercentage > 0) {
                message = '⚠️ Partial containment - add more containers';
                className += ' text-warning';
            } else {
                message = '❌ No containment - add containers to proceed';
                className += ' text-danger';
            }

            // Add fill efficiency warnings separately (optimization suggestions only)
            const warnings = this.containerPlan?.warnings || [];
            const fillWarnings = warnings.filter(w => w.includes('partially filled') || w.includes('overfilled'));
            if (fillWarnings.length > 0 && actualPercentage >= 95) {
                message += ` • ${fillWarnings.join(' • ')}`;
            }

            messageSpan.textContent = message;
            messageSpan.className = className;
        }
    }

    clearContainerResults() {
        const containerResults = document.getElementById('containerResults');
        const containerRows = document.getElementById('containerSelectionRows');

        if (containerResults) {
            containerResults.innerHTML = '<p class="text-muted">Container management disabled</p>';
        }

        if (containerRows) {
            containerRows.innerHTML = '';
        }

        this.clearProgressBar();
    }

    clearProgressBar() {
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

    displayContainerError(message) {
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