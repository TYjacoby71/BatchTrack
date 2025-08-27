// Stock Check Management Module
export class StockCheckManager {
    constructor() {
        this.stockCheckResults = null;
        this.bindEvents();
    }

    bindEvents() {
        console.log('🔍 STOCK CHECK DEBUG: Binding events...');
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        if (stockCheckBtn) {
            console.log('🔍 STOCK CHECK DEBUG: Stock check button found:', true);
            stockCheckBtn.addEventListener('click', () => this.performStockCheck());
            console.log('🔍 STOCK CHECK DEBUG: Event listener added successfully');
        } else {
            console.log('🔍 STOCK CHECK DEBUG: Stock check button not found');
        }
    }

    async performStockCheck() {
        console.log('🔍 STOCK CHECK: Starting stock check...');
        const stockCheckBtn = document.getElementById('stockCheckBtn');
        const originalText = stockCheckBtn ? stockCheckBtn.innerHTML : '';

        try {
            // Show loading state
            if (stockCheckBtn) {
                stockCheckBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
                stockCheckBtn.disabled = true;
            }

            // Get recipe and scale data
            const recipeData = window.planProductionApp?.recipeData;
            const scaleInput = document.getElementById('scale');
            const scale = scaleInput ? parseFloat(scaleInput.value) || 1 : 1;

            if (!recipeData) {
                throw new Error('Recipe data not available');
            }

            console.log('🔍 STOCK CHECK: Recipe ID:', recipeData.id, 'Scale:', scale);

            // Make API call
            const response = await fetch('/api/stock-check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
                },
                body: JSON.stringify({
                    recipe_id: recipeData.id,
                    scale: scale
                })
            });

            const data = await response.json();
            console.log('🔍 STOCK CHECK: Response received:', data);

            if (data.success) {
                this.stockCheckResults = data;
                this.displayStockResults(data);
            } else {
                this.displayStockError(data.error || 'Stock check failed');
            }

        } catch (error) {
            console.error('🔍 STOCK CHECK ERROR:', error);
            this.displayStockError(`Network error during stock check: ${error.message}`);
        } finally {
            // Restore button state
            if (stockCheckBtn) {
                stockCheckBtn.innerHTML = originalText;
                stockCheckBtn.disabled = false;
            }
        }
    }

    displayStockResults(stockCheckResults) {
        console.log('🔍 DISPLAY RESULTS: Starting with:', stockCheckResults);

        const resultsContainer = document.getElementById('stockCheckResults');
        if (!resultsContainer) {
            console.error('🔍 DISPLAY RESULTS: Results container not found');
            return;
        }

        if (stockCheckResults.stock_check) {
            this.handleConversionErrors(stockCheckResults.stock_check);
        }

        // Check if there are missing ingredients or insufficient stock
        const hasMissing = stockCheckResults.missing_ingredients && stockCheckResults.missing_ingredients.length > 0;
        const hasInsufficient = stockCheckResults.insufficient_stock && stockCheckResults.insufficient_stock.length > 0;

        if (!hasMissing && !hasInsufficient) {
            resultsContainer.innerHTML = `
                <div class="alert alert-success">
                    <i class="fas fa-check-circle"></i>
                    <strong>Stock Check Passed!</strong> All ingredients are available in sufficient quantities.
                </div>
            `;
            return;
        }

        let html = '<div class="stock-check-results">';

        if (hasMissing) {
            html += this.renderMissingIngredients(stockCheckResults.missing_ingredients);
        }

        if (hasInsufficient) {
            html += this.renderInsufficientStock(stockCheckResults.insufficient_stock);
        }

        html += '</div>';
        resultsContainer.innerHTML = html;
    }

    handleConversionErrors(stockCheckData) {
        if (!stockCheckData) return;

        const conversionErrors = [];

        // Check for conversion errors in ingredients
        if (stockCheckData.ingredients) {
            stockCheckData.ingredients.forEach(ingredient => {
                if (ingredient.conversion_details && !ingredient.conversion_details.success) {
                    conversionErrors.push({
                        name: ingredient.name,
                        error: ingredient.conversion_details.error_code || 'Unknown conversion error',
                        details: ingredient.conversion_details.error_data
                    });
                }
            });
        }

        if (conversionErrors.length > 0) {
            console.warn('🔍 CONVERSION ERRORS:', conversionErrors);
            this.displayConversionErrors(conversionErrors);
        }
    }

    displayConversionErrors(errors) {
        const errorContainer = document.getElementById('stockCheckResults');
        if (!errorContainer) return;

        let html = '<div class="alert alert-warning mb-3">';
        html += '<h6><i class="fas fa-exclamation-triangle"></i> Conversion Issues</h6>';
        html += '<ul class="mb-0">';

        errors.forEach(error => {
            html += `<li><strong>${error.name}:</strong> ${error.error}`;
            if (error.details && error.details.message) {
                html += ` - ${error.details.message}`;
            }
            html += '</li>';
        });

        html += '</ul></div>';
        errorContainer.innerHTML = html + errorContainer.innerHTML;
    }

    renderMissingIngredients(missingIngredients) {
        let html = `
            <div class="alert alert-danger">
                <h6><i class="fas fa-times-circle"></i> Missing Ingredients</h6>
                <ul class="mb-0">
        `;

        missingIngredients.forEach(ingredient => {
            html += `<li>${ingredient.name} (needed: ${ingredient.needed_amount} ${ingredient.needed_unit})</li>`;
        });

        html += '</ul></div>';
        return html;
    }

    renderInsufficientStock(insufficientStock) {
        let html = `
            <div class="alert alert-warning">
                <h6><i class="fas fa-exclamation-triangle"></i> Insufficient Stock</h6>
                <div class="row">
        `;

        insufficientStock.forEach(ingredient => {
            const needed = ingredient.needed_amount || 0;
            const available = ingredient.available_quantity || 0;
            const shortage = needed - available;

            html += `
                <div class="col-md-6 mb-2">
                    <div class="card">
                        <div class="card-body p-2">
                            <h6 class="card-title mb-1">${ingredient.name}</h6>
                            <div class="text-small">
                                <div>Needed: <strong>${needed} ${ingredient.needed_unit}</strong></div>
                                <div>Available: <span class="text-warning">${available} ${ingredient.available_unit || ingredient.needed_unit}</span></div>
                                <div>Short: <span class="text-danger">${shortage.toFixed(2)} ${ingredient.needed_unit}</span></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div></div>';
        return html;
    }

    displayStockError(errorMessage) {
        console.error('🔍 STOCK ERROR:', errorMessage);
        const resultsContainer = document.getElementById('stockCheckResults');
        if (resultsContainer) {
            resultsContainer.innerHTML = `
                <div class="alert alert-danger">
                    <i class="fas fa-exclamation-triangle"></i>
                    <strong>Stock Check Error:</strong> ${errorMessage}
                </div>
            `;
        }
    }
}

// Export for use in other modules
window.StockCheckManager = StockCheckManager;