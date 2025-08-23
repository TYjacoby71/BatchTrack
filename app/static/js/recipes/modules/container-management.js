
// Container Management Module
export class ContainerManager {
    constructor(mainApp) {
        this.main = mainApp;
        this.containerPlan = null;
    }

    bindEvents() {
        const addContainerBtn = document.getElementById('addContainerBtn');
        if (addContainerBtn) {
            addContainerBtn.addEventListener('click', () => this.addContainerRow());
        }

        const autoFillToggle = document.getElementById('autoFillEnabled');
        if (autoFillToggle) {
            autoFillToggle.addEventListener('change', (e) => {
                this.toggleManualContainerSection(!e.target.checked);
                if (e.target.checked && this.main.requiresContainers) {
                    this.fetchContainerPlan();
                } else if (!e.target.checked) {
                    this.clearAutoFillResults();
                }
            });
        }
    }

    onContainerRequirementChange() {
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

        const yieldAmount = this.main.baseYield * this.main.scale;
        
        try {
            const response = await fetch('/api/container-plan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    recipe_id: this.main.recipe.id,
                    yield_amount: yieldAmount,
                    yield_unit: this.main.unit
                })
            });

            const data = await response.json();
            
            if (data.success) {
                this.containerPlan = data;
                this.displayContainerResults(data);
            } else {
                this.displayError(data.message || 'Failed to get container plan');
            }
        } catch (error) {
            console.error('Container plan fetch error:', error);
            this.displayError('Error fetching container plan');
        }
    }

    displayContainerResults(data) {
        const containerResults = document.getElementById('containerResults');
        if (!containerResults) return;

        if (data.container_selection?.length > 0) {
            let html = '<div class="row g-3">';
            
            data.container_selection.forEach(container => {
                html += `
                    <div class="col-md-6">
                        <div class="card border-primary">
                            <div class="card-body">
                                <h6 class="card-title">${container.name}</h6>
                                <p class="card-text">
                                    <strong>Quantity:</strong> ${container.quantity}<br>
                                    <strong>Capacity:</strong> ${container.capacity} ${container.unit} each<br>
                                    <strong>Total:</strong> ${(container.capacity * container.quantity)} ${container.unit}
                                </p>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            containerResults.innerHTML = html;
            this.updateContainmentProgress(data.containment_percentage || 0);
        } else {
            this.displayNoContainersMessage();
        }
    }

    addContainerRow() {
        const autoFillToggle = document.getElementById('autoFillEnabled');
        if (autoFillToggle?.checked) {
            alert('Please uncheck Auto-Fill to add containers manually.');
            return;
        }

        if (!this.containerPlan?.container_selection?.length) {
            alert('No containers available for this recipe.');
            return;
        }

        const containerRows = document.getElementById('containerSelectionRows');
        if (!containerRows) return;

        const rowIndex = containerRows.children.length;
        const availableContainers = this.containerPlan.container_selection;
        
        let optionsHTML = '<option value="">Select Container</option>';
        availableContainers.forEach(container => {
            optionsHTML += `<option value="${container.id}">${container.name} (${container.capacity} ${container.unit})</option>`;
        });

        const rowHTML = `
            <div class="row mb-2 align-items-center" data-container-row="${rowIndex}">
                <div class="col-md-5">
                    <select class="form-select container-select">${optionsHTML}</select>
                </div>
                <div class="col-md-3">
                    <input type="number" class="form-control container-quantity" min="1" placeholder="Qty">
                </div>
                <div class="col-md-2">
                    <span class="badge bg-light text-dark available-stock">-</span>
                </div>
                <div class="col-md-2">
                    <button type="button" class="btn btn-danger btn-sm remove-container-btn">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;

        const rowDiv = document.createElement('div');
        rowDiv.innerHTML = rowHTML;
        const newRow = rowDiv.firstElementChild;
        containerRows.appendChild(newRow);

        this.bindRowEvents(newRow, rowIndex);
    }

    bindRowEvents(row, rowIndex) {
        const select = row.querySelector('.container-select');
        const quantityInput = row.querySelector('.container-quantity');
        const removeBtn = row.querySelector('.remove-container-btn');

        if (select) {
            select.addEventListener('change', () => this.updateRowStock(row));
        }

        if (quantityInput) {
            quantityInput.addEventListener('input', () => this.updateManualProgress());
        }

        if (removeBtn) {
            removeBtn.addEventListener('click', () => {
                row.remove();
                this.updateManualProgress();
            });
        }

        this.updateRowStock(row);
    }

    updateRowStock(row) {
        const select = row.querySelector('.container-select');
        const stockBadge = row.querySelector('.available-stock');

        if (!select || !stockBadge) return;

        const selectedId = select.value;
        if (!selectedId) {
            stockBadge.textContent = '-';
            return;
        }

        const container = this.containerPlan?.container_selection?.find(c => c.id == selectedId);
        stockBadge.textContent = container ? (container.quantity || 0) : '-';
        this.updateManualProgress();
    }

    updateContainmentProgress(percentage) {
        const progressBar = document.getElementById('containmentProgressBar');
        const percentSpan = document.getElementById('containmentPercent');
        const messageSpan = document.getElementById('liveContainmentMessage');

        if (progressBar) {
            progressBar.style.width = percentage + '%';
            progressBar.textContent = percentage + '%';
            progressBar.className = percentage >= 100 ? 'progress-bar bg-success' : 
                                   percentage > 0 ? 'progress-bar bg-warning' : 'progress-bar bg-danger';
        }

        if (percentSpan) percentSpan.textContent = percentage + '%';

        if (messageSpan) {
            if (percentage >= 100) {
                messageSpan.textContent = 'Full containment achieved';
                messageSpan.className = 'form-text text-success mt-1';
            } else if (percentage > 0) {
                messageSpan.textContent = 'Partial containment (batch can still proceed)';
                messageSpan.className = 'form-text text-warning mt-1';
            } else {
                messageSpan.textContent = 'No containers - manual containment required';
                messageSpan.className = 'form-text text-warning mt-1';
            }
        }

        this.updateContainmentIssue(percentage);
    }

    updateContainmentIssue(percentage) {
        const containmentIssue = document.getElementById('containmentIssue');
        if (containmentIssue) {
            if (percentage < 100 && percentage > 0) {
                const issueText = document.getElementById('containmentIssueText');
                if (issueText) {
                    issueText.textContent = `Only ${percentage}% of yield can be contained. Remaining product will need manual handling.`;
                }
                containmentIssue.style.display = 'block';
            } else {
                containmentIssue.style.display = 'none';
            }
        }
    }

    toggleManualContainerSection(show) {
        const manualSection = document.getElementById('manualContainerSection');
        const autoFillSection = document.getElementById('autoFillResults');
        
        if (manualSection) manualSection.style.display = show ? 'block' : 'none';
        if (autoFillSection) autoFillSection.style.display = show ? 'none' : 'block';
    }

    clearAutoFillResults() {
        const autoFillResults = document.getElementById('autoFillResults');
        if (autoFillResults) autoFillResults.style.display = 'none';
    }

    clearContainerResults() {
        const containerResults = document.getElementById('containerResults');
        const containerRows = document.getElementById('containerSelectionRows');
        const noContainersMsg = document.getElementById('noContainersMessage');
        
        if (containerResults) {
            containerResults.innerHTML = '<p class="text-muted">Container management disabled</p>';
        }
        
        if (containerRows) containerRows.innerHTML = '';
        if (noContainersMsg) noContainersMsg.style.display = 'none';
        
        this.updateContainmentProgress(0);
    }

    displayError(message) {
        const containerResults = document.getElementById('containerResults');
        if (containerResults) {
            containerResults.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle"></i> ${message}
                </div>
            `;
        }
    }

    displayNoContainersMessage() {
        const noContainersMsg = document.getElementById('noContainersMessage');
        if (noContainersMsg) noContainersMsg.style.display = 'block';
    }

    updateManualProgress() {
        // Calculate progress from manual container rows
        if (!this.containerPlan?.success) return;

        const projectedYield = this.main.baseYield * this.main.scale;
        let totalContained = 0;

        document.querySelectorAll('[data-container-row]').forEach(row => {
            const select = row.querySelector('.container-select');
            const quantityInput = row.querySelector('.container-quantity');
            
            if (select?.value && quantityInput) {
                const container = this.containerPlan?.container_selection?.find(c => c.id == select.value);
                if (container) {
                    const quantity = parseInt(quantityInput.value) || 0;
                    totalContained += container.capacity * quantity;
                }
            }
        });

        const percentage = projectedYield > 0 ? Math.min(100, Math.round((totalContained / projectedYield) * 100)) : 0;
        this.updateContainmentProgress(percentage);
    }

    getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || 
               document.querySelector('input[name="csrf_token"]')?.value;
    }
}
