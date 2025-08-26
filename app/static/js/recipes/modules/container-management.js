
// Container Management Module
export class ContainerManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.containerPlan = null;
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
                    // Clear auto-fill results when switching to manual
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

        // Update progress bar when switching modes
        this.updateContainerProgress();
    }

    clearAutoFillResults() {
        const containerResults = document.getElementById('containerResults');
        const containerRows = document.getElementById('containerSelectionRows');
        
        if (containerResults) {
            containerResults.innerHTML = '<p class="text-muted">Switch to manual container selection mode</p>';
        }
        
        if (containerRows) {
            containerRows.innerHTML = '';
        }
        
        // Clear progress bar when switching to manual
        this.updateContainerProgress();
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
        console.log('🔍 CONTAINER DEBUG: Recipe exists:', !!this.main.recipe);
        console.log('🔍 CONTAINER DEBUG: Requires containers:', this.main.requiresContainers);
        
        if (!this.main.recipe || !this.main.requiresContainers) {
            console.log('🔍 CONTAINER DEBUG: Skipping fetch - recipe or requirement missing');
            return;
        }

        console.log('🔍 CONTAINER DEBUG: Fetching container plan for recipe', this.main.recipe.id, 'scale:', this.main.scale);

        try {
            const yieldAmount = this.main.baseYield * this.main.scale;
            console.log('🔍 CONTAINER DEBUG: Yield amount calculated:', yieldAmount);

            this.containerPlan = await this.main.apiCall(`/recipes/${this.main.recipe.id}/auto-fill-containers`, {
                scale: this.main.scale,
                yield_amount: yieldAmount,
                yield_unit: this.main.unit
            });

            console.log('🔍 CONTAINER DEBUG: Server response:', this.containerPlan);

            if (this.containerPlan.success) {
                console.log('🔍 CONTAINER DEBUG: Plan successful, displaying results');
                this.displayContainerPlan();
                this.updateContainerProgress();
            } else {
                console.log('🔍 CONTAINER DEBUG: Plan failed:', this.containerPlan.error);
                this.displayContainerError(this.containerPlan.error || 'Failed to load containers');
            }
        } catch (error) {
            console.error('🚨 CONTAINER NETWORK ERROR:', error);
            this.displayContainerError('Network error while loading containers');
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
        
        containers.forEach((container, index) => {
            const stockQuantity = container.stock_qty || container.available_quantity || container.quantity || 0;
            const containerName = container.name || 'Unknown Container';
            const containerCapacity = container.capacity || 0;
            const containerUnit = container.unit || 'ml';
            const quantityNeeded = container.quantity || 0;
            
            html += `
                <div class="row align-items-center mb-3 p-3 border rounded ${containerClass}" data-${isAutoFill ? 'auto' : 'manual'}-container="${index}">
                    <div class="col-md-5">
                        <label class="form-label small">Container Type</label>
                        <div class="form-control form-control-sm bg-light border-0">
                            <strong>${containerName}</strong>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label small">Quantity Needed</label>
                        <div class="form-control form-control-sm bg-light border-0">
                            <strong>${quantityNeeded}</strong>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label small">Capacity Each</label>
                        <div class="form-control form-control-sm bg-light border-0">
                            ${containerCapacity} ${containerUnit}
                        </div>
                    </div>
                    <div class="col-md-1">
                        <label class="form-label small">Available Stock</label>
                        <div class="badge ${stockQuantity >= quantityNeeded ? 'bg-success' : 'bg-warning'} fs-6">${stockQuantity}</div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        
        if (isAutoFill) {
            const efficiency = this.containerPlan.containment_percentage || 0;
            html += `<div class="mt-2"><small class="text-muted"><i class="fas fa-info-circle"></i> Auto-fill efficiency: ${efficiency.toFixed(1)}%</small></div>`;
        }
        
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
            optionsHTML += `<option value="${container.id}">${container.name} (${container.capacity} ${container.unit})</option>`;
        });

        return `
            <div class="row align-items-center mb-3 p-3 border rounded bg-light" data-container-row="${index}">
                <div class="col-md-5">
                    <label class="form-label small">Container Type</label>
                    <select class="form-select form-select-sm container-select" data-row="${index}">
                        ${optionsHTML}
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label small">Quantity</label>
                    <input type="number" min="1" class="form-control form-control-sm container-quantity" 
                           data-row="${index}" value="1">
                </div>
                <div class="col-md-3">
                    <label class="form-label small">Capacity Each</label>
                    <div class="form-control form-control-sm bg-light border-0 container-capacity" data-row="${index}">-</div>
                </div>
                <div class="col-md-1">
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

        const container = this.containerPlan?.container_selection?.find(c => c.id == selectedId);
        if (!container) {
            stockBadge.textContent = '-';
            if (capacityDiv) capacityDiv.textContent = '-';
            return;
        }

        // Look for stock quantity in various possible properties from the server response
        const stockQuantity = container.stock_qty || container.quantity || container.available_quantity || 0;
        console.log('🔍 STOCK DISPLAY DEBUG: Container:', container.name, 'Stock:', stockQuantity);
        stockBadge.textContent = stockQuantity;

        // Update capacity display
        if (capacityDiv) {
            capacityDiv.textContent = `${container.capacity || 0} ${container.unit || 'ml'}`;
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
            // Calculate from manual container rows
            const projectedYield = this.main.baseYield * this.main.scale;
            let totalContained = 0;

            document.querySelectorAll('[data-container-row]').forEach(row => {
                const select = row.querySelector('.container-select');
                const quantityInput = row.querySelector('.container-quantity');
                
                if (select && quantityInput && select.value) {
                    const container = this.containerPlan?.container_selection?.find(c => c.id == select.value);
                    if (container) {
                        const quantity = parseInt(quantityInput.value) || 0;
                        totalContained += container.capacity * quantity;
                    }
                }
            });

            containment_percentage = projectedYield > 0 ? Math.min((totalContained / projectedYield) * 100, 100) : 0;
        } else {
            containment_percentage = this.containerPlan.containment_percentage || 0;
        }
        
        this.updateProgressBar(containment_percentage);
    }

    updateProgressBar(percentage) {
        const progressBar = document.getElementById('containmentProgressBar');
        const percentSpan = document.getElementById('containmentPercent');
        const messageSpan = document.getElementById('liveContainmentMessage');

        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
            progressBar.textContent = `${percentage.toFixed(1)}%`;
            progressBar.className = `progress-bar ${percentage >= 100 ? 'bg-success' : 'bg-warning'}`;
        }

        if (percentSpan) {
            percentSpan.textContent = `${percentage.toFixed(1)}%`;
        }

        if (messageSpan) {
            if (percentage >= 100) {
                messageSpan.textContent = 'Full containment achieved';
                messageSpan.className = 'form-text text-success mt-1';
            } else if (percentage > 0) {
                messageSpan.textContent = 'Partial containment (batch can still proceed)';
                messageSpan.className = 'form-text text-warning mt-1';
            } else {
                messageSpan.textContent = 'No containers - manual containment required (batch can still proceed)';
                messageSpan.className = 'form-text text-warning mt-1';
            }
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
