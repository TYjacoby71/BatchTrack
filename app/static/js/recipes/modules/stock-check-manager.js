
/**
 * Stock Check Manager - Handles all stock checking functionality
 * 
 * Completely separated from container management to avoid conflicts
 */
export class StockCheckManager {
    constructor(mainManager) {
        this.main = mainManager;
        this.stockCheckResults = null;
        this.processedResults = null;
    }

    bindEvents() {
        console.log('🔍 STOCK CHECK DEBUG: Binding events...');
        
        const bindStockCheckButton = () => {
            const stockCheckBtn = document.getElementById('stockCheckBtn');
            console.log('🔍 STOCK CHECK DEBUG: Stock check button found:', !!stockCheckBtn);

            if (stockCheckBtn) {
                // Remove any existing listeners
                stockCheckBtn.removeEventListener('click', this.handleStockCheckClick);
                
                // Bind the click handler
                this.handleStockCheckClick = () => {
                    console.log('🔍 STOCK CHECK DEBUG: Button clicked!');
                    this.performStockCheck();
                };
                
                stockCheckBtn.addEventListener('click', this.handleStockCheckClick);
                console.log('🔍 STOCK CHECK DEBUG: Event listener added successfully');
            } else {
                console.error('🚨 STOCK CHECK ERROR: Stock check button not found in DOM');
                setTimeout(bindStockCheckButton, 100);
            }
        };

        bindStockCheckButton();
    }

    async performStockCheck() {
        console.log('🔍 STOCK CHECK DEBUG: performStockCheck called');

        if (!this.main.recipe) {
            console.warn('🔍 STOCK CHECK: No recipe available');
            alert('No recipe loaded');
            return;
        }

        console.log('🔍 STOCK CHECK: Starting stock check for recipe', this.main.recipe.id, 'scale:', this.main.scale);

        const stockCheckBtn = document.getElementById('stockCheckBtn');
        const originalText = stockCheckBtn.innerHTML;
        stockCheckBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
        stockCheckBtn.disabled = true;

        try {
            const response = await fetch('/recipes/stock/check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.main.getCSRFToken()
                },
                body: JSON.stringify({
                    recipe_id: this.main.recipe.id,
                    scale: this.main.scale
                })
            });

            console.log('🔍 STOCK CHECK: Response status:', response.status);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            this.stockCheckResults = await response.json();
            console.log('🔍 STOCK CHECK: Results received:', this.stockCheckResults);

            if (this.stockCheckResults.drawer_payload) {
                console.log('🔍 STOCK CHECK: Drawer payload detected, delegating to universal protocol');

                const retryCallback = () => {
                    console.log('🔍 STOCK CHECK: Retrying after drawer resolution');
                    this.performStockCheck();
                };

                window.dispatchEvent(new CustomEvent('openDrawer', {
                    detail: {
                        ...this.stockCheckResults.drawer_payload,
                        retry_callback: retryCallback
                    }
                }));

                this.displayStockResults(this.stockCheckResults);
                return;
            }

            this.displayStockResults(this.stockCheckResults);
        } catch (error) {
            console.error('🚨 STOCK CHECK ERROR:', error);
            this.displayStockError(error.message);
        } finally {
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

        const stockData = this.stockCheckResults.stock_check || [];
        const allAvailable = this.stockCheckResults.status === 'ok';

        const ingredientData = stockData;

        if (!ingredientData || ingredientData.length === 0) {
            stockResults.innerHTML = '<div class="alert alert-warning"><i class="fas fa-exclamation-triangle"></i> There are no ingredients selected in this recipe. Please edit your recipe and add ingredients.</div>';
            if (this.main) {
                this.main.stockChecked = true;
                this.main.stockCheckPassed = true;
                this.main.updateValidation();
            }
            return;
        }

        let html = '<div class="table-responsive"><table class="table table-sm table-striped">';
        html += '<thead><tr><th>Ingredient</th><th>Required</th><th>Available</th><th>Unit</th><th>Status</th></tr></thead><tbody>';

        let allIngredientsAvailable = true;

        ingredientData.forEach(result => {
            const needed = result.needed_amount || result.needed_quantity || result.quantity_needed || 0;
            const available = result.raw_stock !== undefined ? result.raw_stock : (result.available_quantity || 0);

            let status, statusClass, displayAvailable, displayNeeded;

            displayNeeded = result.formatted_needed || `${needed.toFixed(2)} ${result.needed_unit || ''}`;

            if (result.conversion_details?.error_code) {
                status = 'CONVERSION ERROR';
                statusClass = 'bg-warning';
                displayAvailable = result.formatted_available || 'Fix Conversion';
                allIngredientsAvailable = false;
            } else {
                const isAvailable = result.is_available !== false && available >= needed;
                if (!isAvailable) {
                    allIngredientsAvailable = false;
                }
                status = isAvailable ? 'OK' : 'NEEDED';
                statusClass = isAvailable ? 'bg-success' : 'bg-danger';
                displayAvailable = result.formatted_available || `${available.toFixed(2)} ${result.stock_unit || result.available_unit || ''}`;
            }

            const displayUnit = result.available_unit || result.needed_unit || result.unit || '';

            html += `<tr>
                <td>${result.ingredient_name || result.item_name || 'Unknown'}</td>
                <td>${displayNeeded}</td>
                <td>${displayAvailable}</td>
                <td>${displayUnit}</td>
                <td><span class="badge ${statusClass}">${status}</span></td>
            </tr>`;
        });

        html += '</tbody></table></div>';

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

        if (this.main) {
            this.main.stockChecked = true;
            this.main.stockCheckPassed = allIngredientsAvailable;
            this.main.updateValidation();
        }

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

export { StockCheckManager as StockChecker };
