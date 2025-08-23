// Stock Check Management Module
export class StockCheckManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.stockCheckResults = null;
    }

    bindEvents() {
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        if (stockCheckBtn) {
            stockCheckBtn.addEventListener('click', () => this.performStockCheck());
        }
    }

    async performStockCheck() {
        if (!this.main.recipe) {
            console.warn('🔍 STOCK CHECK: No recipe available');
            return;
        }

        console.log('🔍 STOCK CHECK: Starting stock check for recipe', this.main.recipe.id, 'scale:', this.main.scale);

        try {
            this.stockCheckResults = await this.main.apiCall('/api/stock-check', {
                recipe_id: this.main.recipe.id,
                scale: this.main.scale
            });

            console.log('🔍 STOCK CHECK: Results received:', this.stockCheckResults);

            if (this.stockCheckResults.success) {
                this.displayStockResults();
            } else {
                this.displayStockError(this.stockCheckResults.error || 'Stock check failed');
            }
        } catch (error) {
            console.error('🚨 STOCK CHECK ERROR:', error);
            this.displayStockError('Network error during stock check');
        }
    }

    displayStockResults() {
        const stockResults = document.getElementById('stockCheckResults');
        if (!stockResults || !this.stockCheckResults?.success) {
            return;
        }

        const { ingredients, all_available } = this.stockCheckResults;

        let html = '<div class="table-responsive"><table class="table table-sm">';
        html += '<thead><tr><th>Ingredient</th><th>Required</th><th>Available</th><th>Status</th></tr></thead><tbody>';

        ingredients.forEach(ingredient => {
            const status = ingredient.available >= ingredient.required ? 'Available' : 'Low Stock';
            const statusClass = ingredient.available >= ingredient.required ? 'text-success' : 'text-warning';

            html += `
                <tr>
                    <td>${ingredient.name}</td>
                    <td>${ingredient.required} ${ingredient.unit}</td>
                    <td>${ingredient.available} ${ingredient.unit}</td>
                    <td class="${statusClass}">${status}</td>
                </tr>
            `;
        });

        html += '</tbody></table></div>';
        stockResults.innerHTML = html;

        const statusElement = document.getElementById('stockCheckStatus');
        if (statusElement) {
            statusElement.className = `alert ${all_available ? 'alert-success' : 'alert-warning'}`;
            statusElement.innerHTML = all_available
                ? '<i class="fas fa-check-circle"></i> All ingredients available'
                : '<i class="fas fa-exclamation-triangle"></i> Some ingredients unavailable';
        }

        if (this.main && this.main.validationManager && typeof this.main.validationManager.validateForm === 'function') {
            this.main.validationManager.validateForm();
        } else {
            console.warn("ValidationManager or validateForm method not available on mainManager.");
        }
    }

    displayStockError(message) {
        const stockResults = document.getElementById('stockResults');
        if (!stockResults) {
            console.error('stockResults element not found');
            return;
        }
        const statusElement = document.getElementById('stockCheckStatus');
        if (!statusElement) {
            console.error('stockCheckStatus element not found');
            return;
        }

        stockResults.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-circle"></i> ${message}
            </div>
        `;

        console.error('Stock error:', message);
        statusElement.innerHTML = `<div class="alert alert-danger"><i class="fas fa-exclamation-circle"></i> ${message}</div>`;
    }
}

// Export alias for backward compatibility
export { StockCheckManager as StockChecker };