
// Container Management Module
export class ContainerManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.containerPlan = null;
    }

    bindEvents() {
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
                if (e.target.checked && this.main.requiresContainers) {
                    this.fetchContainerPlan();
                }
            });
        }
    }

    onContainerRequirementChange() {
        console.log('🔍 CONTAINER TOGGLE: Requirements changed to:', this.main.requiresContainers);
        
        const containerCard = document.getElementById('containerManagementCard');
        if (containerCard) {
            containerCard.style.display = this.main.requiresContainers ? 'block' : 'none';
        }

        if (this.main.requiresContainers) {
            this.fetchContainerPlan();
        } else {
            this.containerPlan = null;
            this.clearContainerResults();
        }
    }

    async fetchContainerPlan() {
        if (!this.main.recipe || !this.main.requiresContainers) return;

        console.log('🔍 CONTAINER DEBUG: Fetching container plan for recipe', this.main.recipe.id, 'scale:', this.main.scale);

        try {
            const yieldAmount = this.main.baseYield * this.main.scale;

            this.containerPlan = await this.main.apiCall(`/recipes/${this.main.recipe.id}/auto-fill-containers`, {
                scale: this.main.scale,
                yield_amount: yieldAmount,
                yield_unit: this.main.unit
            });

            console.log('🔍 CONTAINER DEBUG: Server response:', this.containerPlan);

            if (this.containerPlan.success) {
                this.displayContainerPlan();
                this.updateContainerProgress();
            } else {
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

        if (!containerResults || !this.containerPlan?.success) {
            this.clearContainerResults();
            return;
        }

        const { container_selection } = this.containerPlan;

        if (!container_selection || container_selection.length === 0) {
            containerResults.innerHTML = '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> No suitable containers found</div>';
            return;
        }

        if (autoFillEnabled) {
            this.displayAutoFillResults(containerResults, container_selection);
        } else {
            containerResults.innerHTML = '<p class="text-muted">Manual container selection mode</p>';
        }
    }

    displayAutoFillResults(container, containers) {
        let html = '<div class="table-responsive"><table class="table table-sm">';
        html += '<thead><tr><th>Container</th><th>Capacity</th><th>Quantity Needed</th><th>Total Volume</th></tr></thead><tbody>';

        containers.forEach(container => {
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
        html += `<div class="mt-2"><small class="text-muted">Fill efficiency: ${(this.containerPlan.containment_percentage || 0).toFixed(1)}%</small></div>`;
        container.innerHTML = html;
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

        this.updateContainerRow(rowIndex);
    }

    updateContainerRow(rowIndex) {
        const row = document.querySelector(`[data-container-row="${rowIndex}"]`);
        if (!row) return;

        const select = row.querySelector('.container-select');
        const stockBadge = row.querySelector('.available-stock');

        if (!select || !stockBadge) return;

        const selectedId = select.value;
        if (!selectedId) {
            stockBadge.textContent = '-';
            return;
        }

        const container = this.containerPlan?.container_selection?.find(c => c.id == selectedId);
        if (!container) {
            stockBadge.textContent = '-';
            return;
        }

        stockBadge.textContent = container.quantity || 0;
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
