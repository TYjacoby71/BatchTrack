// Stock Check Management Module
export class StockCheckManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.stockCheckResults = null;
        this.processedResults = null; // Added to store processed data for downloads
    }

    bindEvents() {
        console.log('🔍 STOCK CHECK DEBUG: Binding events...');
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        console.log('🔍 STOCK CHECK DEBUG: Stock check button found:', !!stockCheckBtn);

        if (stockCheckBtn) {
            stockCheckBtn.addEventListener('click', () => {
                console.log('🔍 STOCK CHECK DEBUG: Button clicked!');
                this.performStockCheck();
            });
            console.log('🔍 STOCK CHECK DEBUG: Event listener added successfully');
        } else {
            console.error('🚨 STOCK CHECK ERROR: Stock check button not found in DOM');
        }
    }

    async performStockCheck() {
        console.log('🔍 STOCK CHECK DEBUG: performStockCheck called');

        if (!this.main.recipe) {
            console.warn('🔍 STOCK CHECK: No recipe available');
            alert('No recipe loaded');
            return;
        }

        console.log('🔍 STOCK CHECK: Starting stock check for recipe', this.main.recipe.id, 'scale:', this.main.scale);

        // Show loading state
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        const originalText = stockCheckBtn.innerHTML;
        stockCheckBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
        stockCheckBtn.disabled = true;

        try {
            // Use the recipe plan route which includes stock checking
            const response = await fetch(`/recipes/${this.main.recipe.id}/plan`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.main.getCSRFToken()
                },
                body: JSON.stringify({
                    scale: this.main.scale,
                    check_containers: false
                })
            });

            console.log('🔍 STOCK CHECK: Response status:', response.status);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.stockCheckResults = await response.json();
            console.log('🔍 STOCK CHECK: Results received:', this.stockCheckResults);

            if (this.stockCheckResults.success) {
                this.displayStockResults();
            } else {
                this.displayStockError(this.stockCheckResults.error || 'Stock check failed');
            }
        } catch (error) {
            console.error('🚨 STOCK CHECK ERROR:', error);
            this.displayStockError(`Network error during stock check: ${error.message}`);
        } finally {
            // Restore button state
            stockCheckBtn.innerHTML = originalText;
            stockCheckBtn.disabled = false;
        }
    }

    displayStockResults() {
        console.log('🔍 STOCK CHECK: Displaying results');
        const stockResults = document.getElementById('stockCheckResults');
        if (!stockResults) {
            console.warn('🔍 STOCK CHECK: No results element found');
            return;
        }

        console.log('🔍 STOCK CHECK: Full results object:', this.stockCheckResults);

        // Handle the actual structure from the production planning service
        const stockData = this.stockCheckResults.stock_results || [];
        const allAvailable = this.stockCheckResults.all_available || this.stockCheckResults.feasible || false;

        console.log('🔍 STOCK CHECK: Stock data:', stockData);
        console.log('🔍 STOCK CHECK: All available:', allAvailable);

        // Filter for ingredients only
        const ingredientData = stockData.filter(item =>
            !item.category || item.category === 'ingredient' || item.category === 'INGREDIENT'
        );

        if (!ingredientData || ingredientData.length === 0) {
            stockResults.innerHTML = '<div class="alert alert-info">No ingredients found for this recipe.</div>';
            this.main.stockChecked = true;
            this.main.stockCheckPassed = true;  // No ingredients means no stock issues
            this.main.updateValidation();
            return;
        }

        let html = '<div class="table-responsive"><table class="table table-sm table-striped">';
        html += '<thead><tr><th>Ingredient</th><th>Required</th><th>Available</th><th>Unit</th><th>Status</th></tr></thead><tbody>';

        let allIngredientsAvailable = true;

        ingredientData.forEach(result => {
            const needed = result.needed_amount || result.needed_quantity || result.quantity_needed || 0;
            const available = result.available_quantity || 0;
            const isAvailable = result.is_available !== false && available >= needed;

            if (!isAvailable) {
                allIngredientsAvailable = false;
            }

            const status = isAvailable ? 'OK' : 'NEEDED';
            const statusClass = isAvailable ? 'bg-success' : 'bg-danger';

            html += `<tr>
                <td>${result.ingredient_name || result.item_name || 'Unknown'}</td>
                <td>${needed.toFixed(2)}</td>
                <td>${available.toFixed(2)}</td>
                <td>${result.unit || result.needed_unit || result.available_unit || ''}</td>
                <td><span class="badge ${statusClass}">${status}</span></td>
            </tr>`;
        });

        html += '</tbody></table></div>';

        // Add action buttons
        html += `
            <div class="d-flex gap-2 mt-3">
                <button type="button" class="btn btn-outline-secondary btn-sm" onclick="stockChecker.downloadCSV()">
                    <i class="fas fa-download"></i> Download CSV
                </button>
                <button type="button" class="btn btn-outline-primary btn-sm" onclick="stockChecker.downloadShoppingList()">
                    <i class="fas fa-shopping-cart"></i> Shopping List
                </button>
            </div>
        `;

        stockResults.innerHTML = html;

        // Update the main status
        this.main.stockChecked = true;
        this.main.stockCheckPassed = allIngredientsAvailable;
        this.main.updateValidation();

        // Store processed results for CSV/shopping list
        this.processedResults = ingredientData.map(result => ({
            ingredient: result.ingredient_name || result.item_name || 'Unknown',
            needed: result.needed_amount || result.needed_quantity || result.quantity_needed || 0,
            available: result.available_quantity || 0,
            unit: result.unit || result.needed_unit || result.available_unit || '',
            status: (result.is_available !== false && (result.available_quantity || 0) >= (result.needed_amount || result.needed_quantity || result.quantity_needed || 0)) ? 'OK' : 'NEEDED'
        }));
    }

    displayStockError(message) {
        console.error('🚨 STOCK CHECK ERROR: Displaying error:', message);

        const stockResults = document.getElementById('stockCheckResults');
        if (!stockResults) {
            console.error('🚨 STOCK CHECK ERROR: stockCheckResults element not found');
            return;
        }

        const statusElement = document.getElementById('stockCheckStatus');
        if (!statusElement) {
            console.error('🚨 STOCK CHECK ERROR: stockCheckStatus element not found');
            return;
        }

        stockResults.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-circle"></i> ${message}
            </div>
        `;

        statusElement.innerHTML = `
            <div class="alert alert-danger">
                <i class="fas fa-exclamation-circle"></i> Stock check failed: ${message}
            </div>
        `;
    }

    downloadCSV() {
        if (!this.processedResults?.length) return;

        let csv = "Ingredient,Required,Available,Unit,Status\n";
        this.processedResults.forEach(row => {
            csv += `${row.ingredient},${row.needed.toFixed(2)},${row.available.toFixed(2)},${row.unit},${row.status}\n`;
        });

        const blob = new Blob([csv], { type: 'text/csv' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'stock_check_report.csv';
        link.click();
    }

    downloadShoppingList() {
        if (!this.processedResults?.length) return;

        const needed = this.processedResults.filter(item => item.status === 'NEEDED');
        if (!needed.length) {
            alert('No items need restocking!');
            return;
        }

        let text = "Shopping List\n=============\n\n";
        needed.forEach(item => {
            const missing = Math.max(0, item.needed - item.available);
            text += `${item.ingredient}: ${missing.toFixed(2)} ${item.unit}\n`;
        });

        const blob = new Blob([text], { type: 'text/plain' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = 'shopping_list.txt';
        link.click();
    }
}

// Export alias for backward compatibility
export { StockCheckManager as StockChecker };