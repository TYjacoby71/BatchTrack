// Stock Check Management Module
export class StockCheckManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.stockCheckResults = null;
    }

    bindEvents() {
        const stockCheckBtn = document.getElementById('checkStockBtn');
        if (stockCheckBtn) {
            stockCheckBtn.addEventListener('click', () => this.fetchStockCheck());
        }
    }

    async fetchStockCheck() {
        if (!this.main.recipe) return;

        try {
            // Assuming the original API call structure is intended, with a potential correction to the endpoint or payload.
            // Based on the provided changes, a new endpoint '/recipes/:id/check-stock' and 'yield_amount' might be intended.
            // However, to maintain the original structure as much as possible and address the user's error about the card not opening,
            // I will proceed with the original method's logic but ensure it's correctly exported as a module.
            // The user's mention of "container management card is not opening with the require container toggle" suggests a UI event
            // or a dependency that is not directly visible in this code snippet. This fix focuses on the module and export errors.

            this.stockCheckResults = await this.main.apiCall('/api/stock-check', {
                recipe_id: this.main.recipe.id,
                scale: this.main.scale
            });

            this.displayStockResults();
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
        resultsContainer.innerHTML = html;

        // Update overall status
        const statusElement = document.getElementById('stockCheckStatus');
        if (statusElement) {
            statusElement.className = `alert ${all_available ? 'alert-success' : 'alert-warning'}`;
            statusElement.innerHTML = all_available
                ? '<i class="fas fa-check-circle"></i> All ingredients available'
                : '<i class="fas fa-exclamation-triangle"></i> Some ingredients unavailable';
        }

        // The original code called this.main.validationManager.validateForm();
        // Assuming validationManager is part of the mainManager and has a validateForm method.
        // If the error relates to container management, this might be where a validation or state update occurs.
        if (this.main && this.main.validationManager && typeof this.main.validationManager.validateForm === 'function') {
            this.main.validationManager.validateForm();
        } else {
            console.warn("ValidationManager or validateForm method not available on mainManager.");
        }
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
}