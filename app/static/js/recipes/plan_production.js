// Plan Production JavaScript functionality
// This file provides form enhancements for the plan production page

console.log('Plan production JavaScript loaded');

class PlanProductionManager {
    constructor() {
        this.recipe = null;
        this.scale = 1.0;
        this.baseYield = 0;
        this.unit = 'units';
        this.batchType = '';
        this.requiresContainers = false;
        this.stockCheckResults = null;
        this.containerPlan = null;

        this.init();
    }

    init() {
        // Get recipe data from page
        const recipeElement = document.querySelector('[data-recipe-id]');
        if (recipeElement) {
            this.recipe = {
                id: parseInt(recipeElement.dataset.recipeId),
                name: recipeElement.dataset.recipeName || 'Unknown Recipe'
            };
            this.baseYield = parseFloat(recipeElement.dataset.baseYield) || 0;
            this.unit = recipeElement.dataset.yieldUnit || 'units';
        }

        this.bindEvents();
        this.updateProjectedYield();
    }

    bindEvents() {
        // Scale input changes
        const scaleInput = document.getElementById('scale');
        if (scaleInput) {
            scaleInput.addEventListener('input', (e) => {
                this.scale = parseFloat(e.target.value) || 1.0;
                this.updateProjectedYield();
                this.fetchStockCheck();
                if (this.requiresContainers) {
                    this.fetchContainerPlan();
                }
            });
        }

        // Batch type selection
        const batchTypeSelect = document.getElementById('batchType');
        if (batchTypeSelect) {
            batchTypeSelect.addEventListener('change', (e) => {
                this.batchType = e.target.value;
                this.validateForm();
            });
        }

        // Container requirement toggle
        const containerToggle = document.getElementById('requiresContainers');
        if (containerToggle) {
            containerToggle.addEventListener('change', (e) => {
                this.requiresContainers = e.target.checked;
                this.onContainerRequirementChange();
            });
        }

        // Stock check button
        const stockCheckBtn = document.getElementById('checkStockBtn');
        if (stockCheckBtn) {
            stockCheckBtn.addEventListener('click', () => this.fetchStockCheck());
        }

        // Add container button
        const addContainerBtn = document.getElementById('addContainerBtn');
        if (addContainerBtn) {
            addContainerBtn.addEventListener('click', () => this.addContainerRow());
        }

        // Auto-fill toggle
        const autoFillToggle = document.getElementById('autoFillEnabled');
        if (autoFillToggle) {
            autoFillToggle.addEventListener('change', (e) => {
                console.log('🔍 AUTO-FILL TOGGLE:', e.target.checked);
                if (e.target.checked && this.requiresContainers) {
                    this.fetchContainerPlan();
                }
            });
        }

        // Start batch button
        const startBatchBtn = document.getElementById('startBatchBtn');
        if (startBatchBtn) {
            startBatchBtn.addEventListener('click', () => this.startBatch());
        }

        // Initial stock check
        setTimeout(() => this.fetchStockCheck(), 500);
    }

    updateProjectedYield() {
        const projectedYieldElement = document.getElementById('projectedYield');
        if (projectedYieldElement) {
            const projectedYield = (this.baseYield * this.scale).toFixed(2);
            projectedYieldElement.textContent = `${projectedYield} ${this.unit}`;
        }
    }

    async fetchStockCheck() {
        if (!this.recipe) return;

        try {
            const response = await fetch('/api/stock-check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                },
                body: JSON.stringify({
                    recipe_id: this.recipe.id,
                    scale: this.scale
                })
            });

            if (response.ok) {
                this.stockCheckResults = await response.json();
                this.displayStockResults();
            } else {
                console.error('Stock check failed:', response.statusText);
                this.displayStockError('Failed to check stock availability');
            }
        } catch (error) {
            console.error('Stock check error:', error);
            this.displayStockError('Error checking stock availability');
        }
    }

    displayStockResults() {
        const resultsContainer = document.getElementById('stockCheckResults');
        if (!resultsContainer || !this.stockCheckResults) return;

        const { ingredients, all_available } = this.stockCheckResults;

        let html = '<div class="table-responsive"><table class="table table-sm">';
        html += '<thead><tr><th>Ingredient</th><th>Needed</th><th>Available</th><th>Status</th></tr></thead><tbody>';

        ingredients.forEach(ingredient => {
            const statusClass = this.getStatusClass(ingredient.status);
            const statusIcon = this.getStatusIcon(ingredient.status);

            html += `
                <tr class="table-${statusClass}">
                    <td>${ingredient.item_name}</td>
                    <td>${ingredient.needed_quantity} ${ingredient.unit}</td>
                    <td>${ingredient.available_quantity} ${ingredient.unit}</td>
                    <td><i class="fas ${statusIcon}"></i> ${ingredient.status}</td>
                </tr>
            `;
        });

        html += '</tbody></table></div>';

        // Update overall status
        const statusElement = document.getElementById('stockCheckStatus');
        if (statusElement) {
            statusElement.className = `alert ${all_available ? 'alert-success' : 'alert-warning'}`;
            statusElement.innerHTML = all_available 
                ? '<i class="fas fa-check-circle"></i> All ingredients available'
                : '<i class="fas fa-exclamation-triangle"></i> Some ingredients unavailable';
        }

        this.validateForm();
    }

    displayStockError(message) {
        const resultsContainer = document.getElementById('stockCheckResults');
        if (resultsContainer) {
            resultsContainer.innerHTML = `<div class="alert alert-danger">${message}</div>`;
        }
    }

    getStatusClass(status) {
        const statusMap = {
            'available': 'success',
            'low': 'warning',
            'insufficient': 'danger',
            'unavailable': 'danger'
        };
        return statusMap[status] || 'secondary';
    }

    getStatusIcon(status) {
        const iconMap = {
            'available': 'fa-check-circle',
            'low': 'fa-exclamation-triangle',
            'insufficient': 'fa-times-circle',
            'unavailable': 'fa-times-circle'
        };
        return iconMap[status] || 'fa-question-circle';
    }

    onContainerRequirementChange() {
        console.log('🔍 CONTAINER TOGGLE: Requirements changed to:', this.requiresContainers);
        
        const containerCard = document.getElementById('containerManagementCard');
        if (containerCard) {
            containerCard.style.display = this.requiresContainers ? 'block' : 'none';
            console.log('🔍 CONTAINER TOGGLE: Card display set to:', this.requiresContainers ? 'block' : 'none');
        }

        if (this.requiresContainers) {
            console.log('🔍 CONTAINER TOGGLE: Fetching container plan...');
            this.fetchContainerPlan();
        } else {
            console.log('🔍 CONTAINER TOGGLE: Clearing container data');
            // Clear container results when toggled off
            this.containerPlan = null;
            const containerResults = document.getElementById('containerResults');
            if (containerResults) {
                containerResults.innerHTML = '<p class="text-muted">Container management disabled</p>';
            }
            this.clearContainerProgress();
        }
    }

    clearContainerProgress() {
        const progressBar = document.getElementById('containmentProgressBar');
        const percentSpan = document.getElementById('containmentPercent');
        const messageSpan = document.getElementById('liveContainmentMessage');
        const noContainersMsg = document.getElementById('noContainersMessage');
        const containmentIssue = document.getElementById('containmentIssue');

        if (progressBar) {
            progressBar.style.width = '0%';
            progressBar.textContent = '0%';
            progressBar.className = 'progress-bar bg-warning';
        }

        if (percentSpan) percentSpan.textContent = '0%';
        if (messageSpan) messageSpan.textContent = '';
        if (noContainersMsg) noContainersMsg.style.display = 'none';
        if (containmentIssue) containmentIssue.style.display = 'none';
    }

    async fetchContainerPlan() {
        if (!this.recipe || !this.requiresContainers) {
            console.log('🔍 CONTAINER DEBUG: Not fetching - recipe:', !!this.recipe, 'requiresContainers:', this.requiresContainers);
            return;
        }

        console.log('🔍 CONTAINER DEBUG: Fetching container plan for recipe', this.recipe.id, 'scale:', this.scale);

        try {
            const yieldAmount = this.baseYield * this.scale;
            console.log('🔍 CONTAINER DEBUG: Yield amount:', yieldAmount, this.unit);

            const response = await fetch(`/recipes/${this.recipe.id}/auto-fill-containers`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                },
                body: JSON.stringify({
                    scale: this.scale,
                    yield_amount: yieldAmount,
                    yield_unit: this.unit
                })
            });

            const result = await response.json();
            console.log('🔍 CONTAINER DEBUG: Server response:', result);

            if (response.ok && result.success) {
                this.containerPlan = result;
                this.displayContainerPlan();
                this.updateContainerProgress();
            } else {
                console.error('🚨 CONTAINER ERROR:', result.error || response.statusText);
                this.displayContainerError(result.error || 'Failed to load containers');
            }
        } catch (error) {
            console.error('🚨 CONTAINER NETWORK ERROR:', error);
            this.displayContainerError('Network error while loading containers');
        }
    }

    displayContainerPlan() {
        const containerResults = document.getElementById('containerResults');
        const containerRowsContainer = document.getElementById('containerSelectionRows');
        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;

        if (!containerResults) {
            console.error('🚨 CONTAINER DISPLAY: containerResults element not found');
            return;
        }

        if (!this.containerPlan?.success) {
            console.log('🔍 CONTAINER DISPLAY: No valid container plan:', this.containerPlan);
            containerResults.innerHTML = '<p class="text-muted">No container plan available</p>';
            if (containerRowsContainer) {
                containerRowsContainer.innerHTML = '';
            }
            return;
        }

        const { container_selection, containment_percentage } = this.containerPlan;
        console.log('🔍 CONTAINER DISPLAY: Displaying', container_selection?.length || 0, 'containers');

        if (!container_selection || container_selection.length === 0) {
            containerResults.innerHTML = '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> No suitable containers found</div>';
            if (containerRowsContainer) {
                containerRowsContainer.innerHTML = '';
            }
            return;
        }

        if (autoFillEnabled) {
            // Show auto-fill results in table format
            let html = '<div class="table-responsive"><table class="table table-sm">';
            html += '<thead><tr><th>Container</th><th>Capacity</th><th>Quantity Needed</th><th>Total Volume</th></tr></thead><tbody>';

            container_selection.forEach(container => {
                html += `
                    <tr>
                        <td>${container.name || 'Unknown Container'}</td>
                        <td>${container.capacity || 0} ${container.unit || 'ml'}</td>
                        <td>${container.quantity || 0}</td>
                        <td>${(container.capacity || 0) * (container.quantity || 0)} ${container.unit || 'ml'}</td>
                    </tr>
                `;
            });

            html += '</tbody></table></div>';
            html += `<div class="mt-2"><small class="text-muted">Fill efficiency: ${(containment_percentage || 0).toFixed(1)}%</small></div>`;
            containerResults.innerHTML = html;

            // Clear manual rows when auto-fill is enabled
            if (containerRowsContainer) {
                containerRowsContainer.innerHTML = '';
            }
        } else {
            // Hide auto-fill results when in manual mode
            containerResults.innerHTML = '<p class="text-muted">Manual container selection mode</p>';
        }
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

    updateContainerProgress() {
        if (!this.containerPlan?.success) return;

        // Calculate containment from manual rows if auto-fill is disabled
        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
        let containment_percentage = 0;

        if (!autoFillEnabled) {
            // Calculate from manual container rows
            const projectedYield = this.baseYield * this.scale;
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
        
        // Update progress bar
        const progressBar = document.getElementById('containmentProgressBar');
        const percentSpan = document.getElementById('containmentPercent');
        const messageSpan = document.getElementById('liveContainmentMessage');

        if (progressBar) {
            progressBar.style.width = `${containment_percentage}%`;
            progressBar.textContent = `${containment_percentage.toFixed(1)}%`;
            progressBar.className = `progress-bar ${containment_percentage >= 100 ? 'bg-success' : 'bg-warning'}`;
        }

        if (percentSpan) {
            percentSpan.textContent = `${containment_percentage.toFixed(1)}%`;
        }

        if (messageSpan) {
            if (containment_percentage >= 100) {
                messageSpan.textContent = 'Full containment achieved';
                messageSpan.className = 'form-text text-success mt-1';
            } else if (containment_percentage > 0) {
                const remaining = this.baseYield * this.scale - (this.containerPlan.total_capacity || 0);
                messageSpan.textContent = `${remaining.toFixed(2)} ${this.unit} will be uncontained (batch can still proceed)`;
                messageSpan.className = 'form-text text-warning mt-1';
            } else {
                messageSpan.textContent = 'No containers - full manual containment required (batch can still proceed)';
                messageSpan.className = 'form-text text-warning mt-1';
            }
        }

        // Show/hide warnings
        const noContainersMsg = document.getElementById('noContainersMessage');
        const containmentIssue = document.getElementById('containmentIssue');

        if (noContainersMsg) {
            noContainersMsg.style.display = (!this.containerPlan.container_selection || this.containerPlan.container_selection.length === 0) ? 'block' : 'none';
        }

        if (containmentIssue) {
            if (containment_percentage < 100 && this.containerPlan.container_selection?.length > 0) {
                containmentIssue.style.display = 'block';
                document.getElementById('containmentIssueText').textContent = 'Insufficient containers for full containment';
            } else {
                containmentIssue.style.display = 'none';
            }
        }
    }

    async autoFillContainers() {
        await this.fetchContainerPlan();
    }

    addContainerRow() {
        const autoFillEnabled = document.getElementById('autoFillEnabled')?.checked;
        if (autoFillEnabled) {
            alert('Please uncheck Auto-Fill to add containers manually.');
            return;
        }

        if (!this.containerPlan?.container_selection || this.containerPlan.container_selection.length === 0) {
            alert('No containers available for this recipe.');
            return;
        }

        const rowsContainer = document.getElementById('containerSelectionRows');
        if (!rowsContainer) return;

        const rowIndex = rowsContainer.children.length;
        const rowHtml = this.createContainerRowHTML(rowIndex);
        
        const rowDiv = document.createElement('div');
        rowDiv.innerHTML = rowHtml;
        rowsContainer.appendChild(rowDiv.firstElementChild);

        // Bind events for the new row
        this.bindContainerRowEvents(rowIndex);
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
                    <label class="form-label small">Available Stock</label>
                    <div class="badge bg-info fs-6 available-stock" data-row="${index}">-</div>
                </div>
                <div class="col-md-1">
                    <label class="form-label small">&nbsp;</label>
                    <button type="button" class="btn btn-danger btn-sm d-block remove-container-btn" 
                            data-row="${index}">
                        <i class="fas fa-times"></i>
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

        // Initial update
        this.updateContainerRow(rowIndex);
    }

    updateContainerRow(rowIndex) {
        const row = document.querySelector(`[data-container-row="${rowIndex}"]`);
        if (!row) return;

        const select = row.querySelector('.container-select');
        const quantityInput = row.querySelector('.container-quantity');
        const stockBadge = row.querySelector('.available-stock');

        if (!select || !quantityInput || !stockBadge) return;

        const selectedId = select.value;
        if (!selectedId) {
            stockBadge.textContent = '-';
            return;
        }

        // Find container details
        const container = this.containerPlan?.container_selection?.find(c => c.id == selectedId);
        if (!container) {
            stockBadge.textContent = '-';
            return;
        }

        // Calculate available stock (considering other rows using same container)
        let usedQuantity = 0;
        document.querySelectorAll('.container-select').forEach((otherSelect, idx) => {
            if (idx !== rowIndex && otherSelect.value == selectedId) {
                const otherQuantityInput = document.querySelector(`[data-row="${idx}"] .container-quantity`);
                if (otherQuantityInput) {
                    usedQuantity += parseInt(otherQuantityInput.value) || 0;
                }
            }
        });

        const availableStock = Math.max(0, (container.quantity || 0) - usedQuantity);
        stockBadge.textContent = availableStock;

        // Adjust quantity if it exceeds available stock
        const currentQuantity = parseInt(quantityInput.value) || 1;
        if (currentQuantity > availableStock) {
            quantityInput.value = Math.max(1, availableStock);
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

    validateForm() {
        const startBatchBtn = document.getElementById('startBatchBtn');
        if (!startBatchBtn) return;

        let isValid = true;
        let reasons = [];
        let warnings = [];

        console.log('🔍 VALIDATION: Checking form validity...');

        // Check batch type - REQUIRED
        if (!this.batchType) {
            isValid = false;
            reasons.push('Select batch type');
        }

        // Check stock availability - REQUIRED
        if (this.stockCheckResults && !this.stockCheckResults.all_available) {
            isValid = false;
            reasons.push('Insufficient ingredients');
        }

        // Container validation - allows bypass with warnings
        if (this.requiresContainers) {
            if (!this.containerPlan?.success) {
                // No containers found - allow bypass with warning
                warnings.push('No containers available - product will be uncontained');
                console.log('🔍 VALIDATION: Container requirement set but no containers available - allowing bypass');
            } else if (this.containerPlan.containment_percentage < 100) {
                // Partial containment - allow bypass with warning
                const uncontained = this.baseYield * this.scale - (this.containerPlan.total_capacity || 0);
                warnings.push(`Incomplete containment: ${uncontained.toFixed(2)} ${this.unit} will be uncontained`);
                console.log('🔍 VALIDATION: Incomplete containment - allowing bypass with warning:', this.containerPlan.containment_percentage + '%');
            }
        }

        console.log('🔍 VALIDATION: Valid:', isValid, 'Reasons:', reasons, 'Warnings:', warnings);

        // Only disable button for critical validation failures
        startBatchBtn.disabled = !isValid;

        // Update button appearance based on validation state
        if (isValid) {
            if (warnings.length > 0) {
                startBatchBtn.textContent = 'Start Batch (with containment issues)';
                startBatchBtn.classList.remove('btn-secondary', 'btn-success');
                startBatchBtn.classList.add('btn-warning');
                startBatchBtn.title = 'Warning: ' + warnings.join('; ');
            } else {
                startBatchBtn.textContent = 'Start Batch';
                startBatchBtn.classList.remove('btn-secondary', 'btn-warning');
                startBatchBtn.classList.add('btn-success');
                startBatchBtn.title = '';
            }
        } else {
            startBatchBtn.textContent = `Cannot Start: ${reasons[0]}`;
            startBatchBtn.classList.remove('btn-success', 'btn-warning');
            startBatchBtn.classList.add('btn-secondary');
            startBatchBtn.title = 'Required: ' + reasons.join('; ');
        }
    }

    async startBatch() {
        if (!this.recipe) return;

        try {
            const productQuantity = this.baseYield * this.scale;

            const response = await fetch('/api/batches/api-start-batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('input[name="csrf_token"]').value
                },
                body: JSON.stringify({
                    recipe_id: this.recipe.id,
                    product_quantity: productQuantity
                })
            });

            const result = await response.json();

            if (result.success) {
                // Show success message
                const successDiv = document.createElement('div');
                successDiv.className = 'alert alert-success';
                successDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${result.message}`;

                const mainContent = document.querySelector('.container-fluid');
                mainContent.insertBefore(successDiv, mainContent.firstChild);

                // Redirect to batch view after short delay
                setTimeout(() => {
                    window.location.href = `/batches/${result.batch_id}`;
                }, 2000);
            } else {
                // Show error message
                const errorDiv = document.createElement('div');
                errorDiv.className = 'alert alert-danger';
                errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${result.message}`;

                const mainContent = document.querySelector('.container-fluid');
                mainContent.insertBefore(errorDiv, mainContent.firstChild);
            }
        } catch (error) {
            console.error('Start batch error:', error);
            alert('Error starting batch. Please try again.');
        }
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    new PlanProductionManager();
});