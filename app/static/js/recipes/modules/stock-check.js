
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

        this.main.validationManager.validateForm();
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
