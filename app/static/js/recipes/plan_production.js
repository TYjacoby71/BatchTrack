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

        // Auto-fill containers button
        const autoFillBtn = document.getElementById('autoFillContainers');
        if (autoFillBtn) {
            autoFillBtn.addEventListener('click', () => this.autoFillContainers());
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
        const containerCard = document.getElementById('containerManagementCard');
        if (containerCard) {
            containerCard.style.display = this.requiresContainers ? 'block' : 'none';
        }

        if (this.requiresContainers) {
            this.fetchContainerPlan();
        } else {
            // Clear container results when toggled off
            const containerResults = document.getElementById('containerResults');
            if (containerResults) {
                containerResults.innerHTML = '';
            }
        }
    }

    async fetchContainerPlan() {
        if (!this.recipe || !this.requiresContainers) return;

        try {
            const yieldAmount = this.baseYield * this.scale;

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

            if (response.ok) {
                this.containerPlan = await response.json();
                this.displayContainerPlan();
            } else {
                console.error('Container planning failed:', response.statusText);
            }
        } catch (error) {
            console.error('Container planning error:', error);
        }
    }

    displayContainerPlan() {
        const containerResults = document.getElementById('containerResults');
        if (!containerResults || !this.containerPlan?.success) return;

        const { container_selection, total_capacity, containment_percentage } = this.containerPlan;

        let html = '<div class="table-responsive"><table class="table table-sm">';
        html += '<thead><tr><th>Container</th><th>Capacity</th><th>Quantity Needed</th><th>Total Volume</th></tr></thead><tbody>';

        container_selection.forEach(container => {
            html += `
                <tr>
                    <td>${container.name}</td>
                    <td>${container.capacity} ${container.unit}</td>
                    <td>${container.quantity}</td>
                    <td>${container.capacity * container.quantity} ${container.unit}</td>
                </tr>
            `;
        });

        html += '</tbody></table></div>';
        html += `<div class="mt-2"><small class="text-muted">Fill efficiency: ${containment_percentage.toFixed(1)}%</small></div>`;

        containerResults.innerHTML = html;
    }

    async autoFillContainers() {
        await this.fetchContainerPlan();
    }

    validateForm() {
        const startBatchBtn = document.getElementById('startBatchBtn');
        if (!startBatchBtn) return;

        let isValid = true;
        let reasons = [];

        // Check batch type
        if (!this.batchType) {
            isValid = false;
            reasons.push('Select batch type');
        }

        // Check stock availability
        if (this.stockCheckResults && !this.stockCheckResults.all_available) {
            isValid = false;
            reasons.push('Insufficient ingredients');
        }

        // Check containers if required
        if (this.requiresContainers && !this.containerPlan?.success) {
            isValid = false;
            reasons.push('No suitable containers');
        }

        startBatchBtn.disabled = !isValid;

        // Update button text with reasons
        if (isValid) {
            startBatchBtn.textContent = 'Start Batch';
            startBatchBtn.classList.remove('btn-secondary');
            startBatchBtn.classList.add('btn-success');
        } else {
            startBatchBtn.textContent = `Cannot Start: ${reasons[0]}`;
            startBatchBtn.classList.remove('btn-success');
            startBatchBtn.classList.add('btn-secondary');
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