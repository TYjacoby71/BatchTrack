
// Stock Check Management Module
export class StockChecker {
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
        const stockResults = document.getElementById('stockCheckResults');
        if (stockResults) {
            stockResults.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-circle"></i> ${message}
                </div>
            `;
        }

        const statusElement = document.getElementById('stockCheckStatus');
        if (statusElement) {
            statusElement.className = 'alert alert-danger';
            statusElement.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
        }
    }

    clearStockResults() {
        const stockResults = document.getElementById('stockCheckResults');
        const statusElement = document.getElementById('stockCheckStatus');
        
        if (stockResults) {
            stockResults.innerHTML = '<p class="text-muted">Stock check will appear here</p>';
        }
        
        if (statusElement) {
            statusElement.className = 'alert alert-info';
            statusElement.innerHTML = '<i class="fas fa-info-circle"></i> Ready for stock check';
        }
    }
}
