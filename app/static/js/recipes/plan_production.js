
// Plan Production Main Script
console.log('Plan production JavaScript loaded');

class PlanProductionApp {
    constructor() {
        this.recipe = null;
        this.scale = 1.0;
        this.baseYield = 0;
        this.unit = '';
        this.batchType = '';
        this.requiresContainers = false;
        this.containerPlan = null;
        this.stockCheckResults = null;
        
        this.init();
    }

    init() {
        console.log('🔍 INIT: Starting plan production app');
        this.loadRecipeData();
        this.bindEvents();
        this.updateValidation();
    }

    loadRecipeData() {
        // Get recipe data from template
        const recipeData = window.recipeData;
        if (recipeData) {
            this.recipe = recipeData;
            this.baseYield = parseFloat(recipeData.yield_amount) || 0;
            this.unit = recipeData.yield_unit || '';
            console.log('🔍 RECIPE: Loaded recipe data:', this.recipe);
            // Update initial projected yield
            this.updateProjectedYield();
        }
    }

    bindEvents() {
        // Scale input
        const scaleInput = document.getElementById('batchScale');
        if (scaleInput) {
            scaleInput.addEventListener('input', () => {
                this.scale = parseFloat(scaleInput.value) || 1.0;
                this.updateProjectedYield();
                if (this.requiresContainers) {
                    this.fetchContainerPlan();
                }
            });
        }

        // Batch type select
        const batchTypeSelect = document.getElementById('batchType');
        if (batchTypeSelect) {
            batchTypeSelect.addEventListener('change', () => {
                this.batchType = batchTypeSelect.value;
                this.updateValidation();
            });
        }

        // Container requirement toggle
        const containerToggle = document.getElementById('requiresContainers');
        if (containerToggle) {
            containerToggle.addEventListener('change', () => {
                this.requiresContainers = containerToggle.checked;
                this.onContainerRequirementChange();
            });
        }

        // Auto-fill toggle
        const autoFillToggle = document.getElementById('autoFillEnabled');
        if (autoFillToggle) {
            autoFillToggle.addEventListener('change', (e) => {
                console.log('🔍 AUTO-FILL TOGGLE:', e.target.checked);
                this.toggleManualContainerSection(!e.target.checked);
                if (e.target.checked && this.requiresContainers) {
                    this.fetchContainerPlan();
                } else if (!e.target.checked) {
                    // Clear auto-fill results when switching to manual
                    const autoFillResults = document.getElementById('autoFillResults');
                    if (autoFillResults) {
                        autoFillResults.style.display = 'none';
                    }
                }
            });
        }

        // Add container button
        const addContainerBtn = document.getElementById('addContainerBtn');
        if (addContainerBtn) {
            addContainerBtn.addEventListener('click', () => this.addContainerRow());
        }

        // Form submission
        const form = document.getElementById('planProductionForm');
        if (form) {
            form.addEventListener('submit', (e) => this.handleFormSubmit(e));
        }
    }

    updateProjectedYield() {
        const projectedYield = this.baseYield * this.scale;
        const yieldDisplay = document.getElementById('projectedYield');
        if (yieldDisplay) {
            yieldDisplay.textContent = projectedYield.toFixed(2) + ' ' + this.unit;
        }
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
            this.containerPlan = null;
            this.clearContainerResults();
        }
        
        this.updateValidation();
    }

    async fetchContainerPlan() {
        if (!this.recipe || !this.requiresContainers) return;

        const yieldAmount = this.baseYield * this.scale;
        console.log('🔍 CONTAINER DEBUG: Fetching container plan for recipe', this.recipe.id, 'scale:', this.scale);
        console.log('🔍 CONTAINER DEBUG: Yield amount:', yieldAmount, this.unit);

        try {
            const response = await fetch('/api/container-plan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    recipe_id: this.recipe.id,
                    yield_amount: yieldAmount,
                    yield_unit: this.unit
                })
            });

            const data = await response.json();
            console.log('🔍 CONTAINER DEBUG: Server response:', data);

            if (data.success) {
                this.containerPlan = data;
                this.displayContainerResults(data);
            } else {
                this.displayContainerError(data.message || 'Failed to get container plan');
            }
        } catch (error) {
            console.error('Container plan fetch error:', error);
            this.displayContainerError('Error fetching container plan');
        }
    }

    displayContainerResults(data) {
        const autoFillResults = document.getElementById('autoFillResults');
        const containerResults = document.getElementById('containerResults');
        
        if (!containerResults) return;

        console.log('🔍 CONTAINER DISPLAY: Displaying', data.container_selection?.length || 0, 'containers');

        if (data.container_selection && data.container_selection.length > 0) {
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

    displayContainerError(message) {
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
        if (noContainersMsg) {
            noContainersMsg.style.display = 'block';
        }
    }

    updateContainmentProgress(percentage) {
        const progressBar = document.getElementById('containmentProgressBar');
        const percentSpan = document.getElementById('containmentPercent');
        const messageSpan = document.getElementById('liveContainmentMessage');

        if (progressBar) {
            progressBar.style.width = percentage + '%';
            progressBar.textContent = percentage + '%';
            
            if (percentage >= 100) {
                progressBar.className = 'progress-bar bg-success';
            } else if (percentage > 0) {
                progressBar.className = 'progress-bar bg-warning';
            } else {
                progressBar.className = 'progress-bar bg-danger';
            }
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
                messageSpan.textContent = 'No containers - manual containment required (batch can still proceed)';
                messageSpan.className = 'form-text text-warning mt-1';
            }
        }

        // Show/hide containment issue alert
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
        
        console.log('🔍 TOGGLE MANUAL SECTION:', show);
        if (manualSection) {
            manualSection.style.display = show ? 'block' : 'none';
            console.log('🔍 MANUAL SECTION display:', show ? 'block' : 'none');
        }
        if (autoFillSection) {
            autoFillSection.style.display = show ? 'none' : 'block';
            console.log('🔍 AUTO-FILL SECTION display:', show ? 'none' : 'block');
        }
    }

    addContainerRow() {
        // Check if auto-fill is enabled and prevent manual addition
        const autoFillToggle = document.getElementById('autoFillEnabled');
        if (autoFillToggle && autoFillToggle.checked) {
            alert('Please uncheck Auto-Fill to add containers manually.');
            return;
        }

        // Check if we have container data available
        if (!this.containerPlan || !this.containerPlan.container_selection || this.containerPlan.container_selection.length === 0) {
            alert('No containers available for this recipe.');
            return;
        }

        const containerRows = document.getElementById('containerSelectionRows');
        if (!containerRows) return;

        const rowIndex = containerRows.children.length;
        const availableContainers = this.containerPlan.container_selection;
        
        // Create options HTML
        let optionsHTML = '<option value="">Select Container</option>';
        availableContainers.forEach(container => {
            optionsHTML += `<option value="${container.id}">${container.name} (${container.capacity} ${container.unit})</option>`;
        });

        // Create row HTML
        const rowHTML = `
            <div class="row mb-2 align-items-center" data-container-row="${rowIndex}">
                <div class="col-md-5">
                    <select class="form-select container-select">
                        ${optionsHTML}
                    </select>
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

        // Add the row
        const rowDiv = document.createElement('div');
        rowDiv.innerHTML = rowHTML;
        const newRow = rowDiv.firstElementChild;
        containerRows.appendChild(newRow);

        // Bind events to the new row
        this.bindContainerRowEvents(rowIndex);
    }

    bindContainerRowEvents(rowIndex) {
        const row = document.querySelector(`[data-container-row="${rowIndex}"]`);
        if (!row) return;

        const select = row.querySelector('.container-select');
        const quantityInput = row.querySelector('.container-quantity');
        const removeBtn = row.querySelector('.remove-container-btn');

        if (select) {
            select.addEventListener('change', () => this.updateContainerRowStock(rowIndex));
        }

        if (quantityInput) {
            quantityInput.addEventListener('input', () => this.updateManualContainerProgress());
        }

        if (removeBtn) {
            removeBtn.addEventListener('click', () => {
                row.remove();
                this.updateManualContainerProgress();
            });
        }

        this.updateContainerRowStock(rowIndex);
    }

    updateContainerRowStock(rowIndex) {
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
        if (container) {
            stockBadge.textContent = container.quantity || 0;
        } else {
            stockBadge.textContent = '-';
        }

        this.updateManualContainerProgress();
    }

    updateManualContainerProgress() {
        // This would calculate progress from manual container rows
        // Implementation depends on available container data
    }

    clearContainerResults() {
        const containerResults = document.getElementById('containerResults');
        const containerRows = document.getElementById('containerSelectionRows');
        const noContainersMsg = document.getElementById('noContainersMessage');
        
        if (containerResults) {
            containerResults.innerHTML = '<p class="text-muted">Container management disabled</p>';
        }
        
        if (containerRows) {
            containerRows.innerHTML = '';
        }

        if (noContainersMsg) {
            noContainersMsg.style.display = 'none';
        }
        
        this.updateContainmentProgress(0);
    }

    updateValidation() {
        console.log('🔍 VALIDATION: Checking form validity...');
        
        const reasons = [];
        const warnings = [];
        
        if (!this.batchType) {
            reasons.push('Select batch type');
        }
        
        const isValid = reasons.length === 0;
        console.log('🔍 VALIDATION: Valid:', isValid, 'Reasons:', reasons, 'Warnings:', warnings);
        
        // Update submit button state
        const submitBtn = document.getElementById('submitBtn');
        if (submitBtn) {
            submitBtn.disabled = !isValid;
        }
    }

    handleFormSubmit(e) {
        e.preventDefault();
        
        if (!this.batchType) {
            alert('Please select a batch type');
            return;
        }
        
        // Continue with form submission logic
        console.log('Form submitted with data:', {
            scale: this.scale,
            batchType: this.batchType,
            requiresContainers: this.requiresContainers
        });
    }

    getCSRFToken() {
        return document.querySelector('meta[name="csrf-token"]')?.content || 
               document.querySelector('input[name="csrf_token"]')?.value;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.planProductionApp = new PlanProductionApp();
});
